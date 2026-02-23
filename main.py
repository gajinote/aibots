import os
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
        # ターンごとの詳細な履歴を保持するリスト
        self.history = []
        # コンテキストの起点となる要約（Markdown形式）
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

    def create_markdown_summary(self):
        """5ターンの履歴をMarkdown形式の要約に変換する"""
        print("[\033[94mINFO\033[0m] 5ターンに達しました。履歴をMarkdownで要約し、コンテキストを圧縮します。")
        
        # 過去の要約と、今回の5ターン分の履歴を結合
        history_text = "\n".join(self.history)
        prompt = f"""
        以下の「これまでの要約」と「直近の実行履歴」をもとに、
        現在のシステム状態と進捗をまとめた新しいMarkdown形式の要約を作成してください。
        
        ## これまでの要約:
        {self.summary_context_md}
        
        ## 直近5ターンの実行履歴:
        {history_text}
        
        出力は、見出しやリストを用いた簡潔なMarkdown形式にしてください。
        """
        
        # 要約はJSON形式ではなく、プレーンなMarkdownとして取得
        summary_md = self.query_llm(prompt, system_prompt="You are a helpful assistant that summarizes technical logs into Markdown.", force_json=False)
        
        # メモリ（要約コンテキスト）の入れ替え
        self.summary_context_md = summary_md
        # 詳細履歴リストをクリア
        self.history = []
        
        # デバッグ用にファイルにも保存（任意）
        with open("memory/last_summary.md", "w") as f:
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
    for i in range(3):
        result = agent.run_cycle()
        if result:
            history.append(result)
        time.sleep(2) # 負荷軽減
    
    # 最後に日記を書いてSlackへ
    summary = "Completed 3 autonomous cycles. Checked system status and logged results."
    agent.write_diary(summary)