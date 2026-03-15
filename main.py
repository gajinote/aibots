import os
import subprocess
import json
import requests
from datetime import datetime
import time
import yaml

class AutonomousAgent:
    def __init__(self):
        # 設定読み込み
        with open('config/setting.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.ollama_url = self.config['ollama']['url']
        self.model_name = self.config['ollama']['model']
        self.slack_webhook_url = self.config['slack']['webhook_url']
        self.blacklist_commands = self.config.get('blacklist_commands', [])
        
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
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False,
        }
        if force_json:
            payload["format"] = "json"

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=60)
            result = response.json()
            raw_response = result['response']
            return json.loads(raw_response) if force_json else raw_response
        except Exception as e:
            return {"error": f"LLM query failed: {str(e)}"}

    def execute_command(self, command):
        """Act: シェルコマンドを実行し、Observe: 結果を返す"""
        # ブラックリストチェック
        for banned in self.blacklist_commands:
            if banned in command:
                return {"error": f"Command is blacklisted: {banned}"}
        
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
        
        # 最新のdiary-*.mdファイルを探して読み込む
        latest_diary_content = ""
        memory_dir = "memory"
        if os.path.exists(memory_dir):
            diary_files = [f for f in os.listdir(memory_dir) if f.startswith("diary-") and f.endswith(".md")]
            if diary_files:
                # タイムスタンプでソート（降順で最新を取得）
                diary_files.sort(reverse=True)
                latest_diary = os.path.join(memory_dir, diary_files[0])
                try:
                    with open(latest_diary, 'r') as f:
                        latest_diary_content = f.read()
                except Exception as e:
                    print(f"Warning: Failed to read latest diary file: {str(e)}")
        
        # 最新の日記内容を含める
        content = f"# Diary {timestamp}\n\n## Objective\n{self.current_objective}\n\n## Activity\n{activity_summary}\n"
        if latest_diary_content:
            content += f"\n## Previous Diary\n{latest_diary_content}\n"
        
        path = f"memory/diary-{timestamp}.md"
        with open(path, 'w') as f:
            f.write(content)
        
        self.post_to_slack(content)
        return content

    def create_markdown_summary(self):
        """history配列を全て取り出してLLMに要約をさせ、MarkDown書式で保存"""
        # historyを全て結合
        history_text = "\n\n".join(self.history)
        
        # LLMに要約を依頼
        prompt = f"Summarize the following history of actions and observations in a concise Markdown format:\n\n{history_text}"
        summary = self.query_llm(prompt, system_prompt="You are a helpful assistant that summarizes technical logs.", force_json=False)
        
        # Markdown形式で保存
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        content = f"# Activity Summary {timestamp}\n\n{summary}\n"
        
        path = f"memory/diary-{timestamp}.md"
        with open(path, 'w') as f:
            f.write(content)
        
        # summary_context_mdを更新
        self.summary_context_md = content
        
        # historyをクリア
        self.history = []
        
        print(f"[\033[92mSUMMARY\033[0m] Created summary: {path}")

    def post_to_slack(self, text):
        if self.slack_webhook_url == "YOUR_WEBHOOK_URL": return
        payload = {"text": f"🤖 *AI Agent Diary Update*\n{text}"}
        requests.post(self.slack_webhook_url, json=payload)

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
        system_prompt = f"""You are an autonomous agent on Ubuntu 24.04.
Context:{self.summary_context_md}
History:{current_history_text}
IMPORTANT: You MUST respond with a JSON object that includes these fields:
- "thought": Your reasoning and plan
- "act": A shell command (System Command) to execute. This field is REQUIRED.
- "new_objective": (Optional) Updated objective if needed"""
        
        thought = self.query_llm(f"Current Objective: {self.current_objective}. Next move?", system_prompt)
        
        # エラーチェック
        if "error" in thought:
            print(f"[\033[91mERROR\033[0m] LLM query failed: {thought['error']}")
            return None
        
        if "act" not in thought:
            print(f"[\033[91mERROR\033[0m] LLM response missing 'act' field (System Command). Response: {thought}")
            return None
        
        if "act" in thought:
            # 2. 実行フェーズ (Act & Observe)
            system_command = thought["act"]
            print(f"[\033[94mTHOUGHT\033[0m] {thought.get('thought', '')}")
            print(f"[\033[94mSYSTEM COMMAND\033[0m] {system_command}")
            
            observation = self.execute_command(system_command)
            
            # --- 異常検知 & 自己修復パス ---
            if observation.get("exit_code") != 0:
                # 失敗した場合、深掘り分析を実行
                failure_analysis = self.analyze_failure(system_command, observation)
                
                # 履歴には「コマンド＋エラー＋分析結果」をセットで入れる
                log_entry = (
                    f"FAILED System Command: {system_command}\n"
                    f"Error: {observation.get('stderr')}\n"
                    f"Analysis & Fix: {failure_analysis}"
                )
                print(f"[\033[93mANALYSIS\033[0m]: {failure_analysis}")
            else:
                # 成功した場合は通常通り
                log_entry = f"System Command: {system_command}\nOutput: {observation.get('stdout', '')[:300]}"
            
            # 短期記憶にこの知見を保存
            self.history.append(log_entry)

            # このターンのログをファイルにも保存
            turn_data = {
                "turn": self.turn_count,
                "objective": self.current_objective,
                "command": thought.get("act"),
                "log_entry": log_entry,
                "observation": observation,
            }
            self.save_log(turn_data)
            
            # 5ターンごとの要約（ここで失敗の分析も圧縮される）
            if len(self.history) >= self.max_turns_before_summary:
                self.create_markdown_summary()
                self.write_diary(self.summary_context_md) #  要約を日記にも書く
                
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
    