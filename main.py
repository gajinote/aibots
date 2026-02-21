import os
import json
import subprocess
import requests
from datetime import datetime
import time

# --- 設定 ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3"  # または使用中のモデル名
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

class AutonomousAgent:
    def __init__(self):
        self.context = ""  # 短期記憶（対話履歴）
        self.current_objective = "システムの状態を調査し、改善点を見つける"
        
    def query_llm(self, prompt, system_prompt=""):
        full_prompt = f"{system_prompt}\n\nContext:\n{self.context}\n\nUser: {prompt}"
        payload = {
            "model": MODEL_NAME,
            "prompt": full_prompt,
            "stream": False,
            "format": "json" # JSONレスポンスを強制
        }
        try:
            response = requests.post(OLLAMA_URL, json=payload)
            result = response.json()
            return json.loads(result['response'])
        except Exception as e:
            return {"error": str(e)}

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

    def run_cycle(self):
        print(f"\n--- Starting Cycle: {self.current_objective} ---")
        
        system_prompt = """
        You are an autonomous AI Agent on Ubuntu 24.04. 
        You must output ONLY a JSON object with these keys: 
        "plan": "what to do", 
        "reflection": "why/safety check", 
        "act": "linux shell command", 
        "new_objective": "updated goal if needed"
        """

        # 1. Plan & Reflection & Act (LLMに思考させる)
        thought = self.query_llm(f"Current Objective: {self.current_objective}. What is your next move?", system_prompt)
        
        if "act" in thought:
            # 2. Act & Observe
            observation = self.execute_command(thought["act"])
            
            # 3. Memory (JSONログ)
            turn_data = {
                "thought": thought,
                "observation": observation,
                "timestamp": datetime.now().isoformat()
            }
            self.save_log(turn_data)
            
            # コンテキスト（短期記憶）の更新
            self.context += f"\nCommand: {thought['act']}\nOutput: {observation['stdout']}"
            
            # 新しい目的の更新
            if thought.get("new_objective"):
                self.current_objective = thought["new_objective"]
                
            return turn_data
        return None

# --- メイン実行 ---
if __name__ == "__main__":
    agent = AutonomousAgent()
    
    # 実験的に3サイクル回す
    history = []
    for i in range(3):
        result = agent.run_cycle()
        if result:
            history.append(result)
        time.sleep(2) # 負荷軽減
    
    # 最後に日記を書いてSlackへ
    summary = "Completed 3 autonomous cycles. Checked system status and logged results."
    agent.write_diary(summary)