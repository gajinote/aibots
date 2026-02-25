import os
import subprocess
import json
import requests
from datetime import datetime
import time

# --- 設定 ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3"  # または使用中のモデル名
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

class AutonomousAgent:
    def __init__(self):
        # 進行管理
        self.turn_count = 0 
        self.max_turns_before_summary = 5
        self.current_objective = "システムの状態を調査し、改善点を見つける"
        
        # 記憶構造 (context変数は廃止し、こちらに統一しました)
        self.history = [] 
        self.summary_context_md = "# Activity Summary (Initial)\nNo previous activity."
        
        # ログ保存用
        os.makedirs("logs", exist_ok=True)
        os.makedirs("memory", exist_ok=True)
        print("[\033[92mSYSTEM\033[0m] Agent initialized and ready.")

    def query_llm(self, prompt, system_prompt="", force_json=True):
        """Ollamaへの問い合わせ (self.contextへの参照を削除)"""
        # system_promptにすでに要約と直近履歴が入る設計にしています
        full_prompt = f"{system_prompt}\n\nUser: {prompt}"
        
        payload = {
            "model": MODEL_NAME,
            "prompt": full_prompt,
            "stream": False,
        }
        if force_json:
            payload["format"] = "json"

        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=60)
            result = response.json()
            raw_response = result['response']
            return json.loads(raw_response) if force_json else raw_response
        except Exception as e:
            return {"error": f"LLM query failed: {str(e)}"}

    def execute_command(self, command):
        """Act: シェルコマンドを実行し、Observe: 結果を返す"""
        print(f"[\033[92mACT\033[0m] Executing: {command}")
        try:
            # sudoパスワードレス設定を想定
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except Exception as e:
            return {"error": str(e)}

    def save_log(self, turn_data):
        """中期記憶: ターン毎のJSONログ保存"""
        filename = f"logs/turn-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(turn_data, f, indent=4)

    def write_diary(self, activity_summary):
        """長期記憶: 自己反省を含む日記の作成"""
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        content = f"# Diary {timestamp}\n\n## Objective\n{self.current_objective}\n\n## Activity\n{activity_summary}\n"
        
        path = f"memory/diary-{timestamp}.md"
        with open(path, 'w') as f:
            f.write(content)
        
        self.post_to_slack(content)
        return content

    def post_to_slack(self, text):
        if SLACK_WEBHOOK_URL == "YOUR_WEBHOOK_URL": return
        payload = {"text": f"🤖 *AI Agent Diary Update*\n{text}"}
        requests.post(SLACK_WEBHOOK_URL, json=payload)

    def analyze_failure(self, command, observation):
        """Actが失敗した際に、エラーの原因と対策を深く分析させる"""
        print(f"[\033[91mREPAIR\033[0m] Analyzing failure: {command}")
        
        prompt = f"""
        The following command failed. Analyze the error and suggest a fix.
        
        # Failed Command
        `{command}`
        
        # Exit Code
        {observation.get('exit_code')}
        
        # Error Output (STDERR)
        {observation.get('stderr')}
        
        # Output (STDOUT)
        {observation.get('stdout')}
        
        Explain why it failed and how to correct it in the next step.
        """
        
        # 反省（Reflection）フェーズとしてLLMに分析させる
        analysis = self.query_llm(prompt, system_prompt="You are a Linux system expert. Analyze the failure precisely.", force_json=False)
        return analysis

    def run_cycle(self):
        self.turn_count += 1
        print(f"\n--- Cycle {self.turn_count}: {self.current_objective} ---")

        # 1. 思考フェーズ (Plan & Reflection)
        current_history_text = "\n".join(self.history) if self.history else "None"
        system_prompt = f"You are an autonomous agent on Ubuntu 24.04. Context:\n{self.summary_context_md}\nHistory:\n{current_history_text}"
        thought = self.query_llm(f"Current Objective: {self.current_objective}. Next move?", system_prompt)
        
        if "act" in thought:
            # 2. 実行フェーズ (Act & Observe)
            observation = self.execute_command(thought["act"])
            
            # --- 異常検知 & 自己修復パス ---
            if observation.get("exit_code") != 0:
                # 失敗した場合、深掘り分析を実行
                failure_analysis = self.analyze_failure(thought["act"], observation)
                
                # 履歴には「コマンド＋エラー＋分析結果」をセットで入れる
                log_entry = (
                    f"FAILED Command: {thought['act']}\n"
                    f"Error: {observation.get('stderr')}\n"
                    f"Analysis & Fix: {failure_analysis}"
                )
                print(f"[\033[93mANALYSIS\033[0m]: {failure_analysis}")
            else:
                # 成功した場合は通常通り
                log_entry = f"Command: {thought['act']}\nOutput: {observation.get('stdout', '')[:300]}"
            
            # 短期記憶にこの知見を保存
            self.history.append(log_entry)
            
            # 5ターンごとの要約（ここで失敗の分析も圧縮される）
            if len(self.history) >= self.max_turns_before_summary:
                self.create_markdown_summary()
                
            if thought.get("new_objective"):
                self.current_objective = thought["new_objective"]
            
            return observation
        return None

# --- メイン実行 ---
if __name__ == "__main__":
    agent = AutonomousAgent()
    
    # 実験的に3サイクル回す
    history = []
    for i in range(10):
        result = agent.run_cycle()
        if result:
            history.append(result)
        time.sleep(2) # 負荷軽減
    
    # 最後に日記を書いてSlackへ
    summary = "Completed 10 autonomous cycles. Checked system status and logged results."
    agent.write_diary(summary)