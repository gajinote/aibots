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
        self.history = []
        self.summary_context_md = "# Activity Summary (Initial)\nNo previous activity."
        self.turn_count = 0
        self.max_turns_before_summary = 5
        self.current_objective = "システムの状態を調査し、改善点を見つける"
    
    def query_llm(self, prompt, system_prompt="", force_json=True):
        """Ollamaへの問い合わせ汎用メソッド"""
        payload = {
            "model": MODEL_NAME, # 環境に合わせて変更してください
            "prompt": f"{system_prompt}\n\n{prompt}",
            "stream": False,
        }
        if force_json:
            payload["format"] = "json"
            
        try:
            response = requests.post(OLLAMA_URL, json=payload)
            res_json = response.json()
            return json.loads(res_json['response']) if force_json else res_json['response']
        except Exception as e:
            return {"error": str(e)}

    def post_to_slack(self, title, message):
        """Slackにメッセージを投稿する"""
        if not SLACK_WEBHOOK_URL or "XXXX" in SLACK_WEBHOOK_URL:
            print("[\033[93mWARN\033[0m] Slack Webhook URLが設定されていないため、投稿をスキップします。")
            return

        # Slack向けのペイロード作成
        payload = {
            "text": f"*{title}*\n{message}"
        }
        
        try:
            response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
            if response.status_code == 200:
                print("[\033[92mINFO\033[0m] Slackに要約を投稿しました。")
            else:
                print(f"[\033[91mERROR\033[0m] Slack投稿失敗: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[\033[91mERROR\033[0m] Slack接続エラー: {e}")

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

    def create_markdown_summary(self):
        """5ターンの履歴をMarkdown形式の要約に変換し、Slackへ投稿する"""
        print("[\033[94mINFO\033[0m] 要約を作成中...")
        
        history_text = "\n".join(self.history)
        prompt = f"""
        以下の履歴を元に、現在の状況をMarkdown形式で短く要約してください。
        ## 直近5ターンの実行履歴:
        {history_text}
        """
        
        # Ollamaに要約を依頼 (force_json=False)
        summary_md = self.query_llm(prompt, system_prompt="You are a professional logger.", force_json=False)
        
        # 内部メモリ（要約コンテキスト）の更新
        self.summary_context_md = summary_md
        self.history = [] # 履歴をリセット
        
        # --- Slackへ投稿 ---
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.post_to_slack(
            title=f"🤖 AI Agent Report ({now})",
            message=summary_md
        )

        # ファイルとしても保存
        with open(f"memory/summary-{datetime.now().strftime('%H%M%S')}.md", "w") as f:
            f.write(self.summary_context_md)
        
    def run_cycle(self):
        self.turn_count += 1
        print(f"\n--- Cycle {self.turn_count}: {self.current_objective} ---")

        # プロンプトの構築（要約された文脈 + 直近の履歴）
        current_history_text = "\n".join(self.history) if self.history else "None"
        
        system_prompt = f"""
        You are an autonomous AI Agent on Ubuntu 24.04.
        
        # Current Context (Summary):
        {self.summary_context_md}
        
        # Recent History (Last {len(self.history)} turns):
        {current_history_text}

        Output ONLY JSON: {{"plan": "...", "reflection": "...", "act": "...", "new_objective": "..."}}
        """

        # LLMから次のアクションを取得
        thought = self.query_llm(f"Current Objective: {self.current_objective}. Next move?", system_prompt)
        
        if "act" in thought:
            # コマンド実行 (execute_command関数は以前のコードと同様と想定)
            observation = self.execute_command(thought["act"])
            
            # 結果の整形と保存
            result_str = f"Command: {thought['act']}\nOutput: {observation.get('stdout', '')[:300]}"
            self.history.append(result_str)
            
            # 5ターンごとに要約・圧縮を実行
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
    length = 10
    for i in range(length):
        result = agent.run_cycle()
        if result:
            history.append(result)
        time.sleep(2) # 負荷軽減
    
    # 最後に日記を書いてSlackへ
    # summary = "Completed 3 autonomous cycles. Checked system status and logged results."
    # agent.write_diary(summary)