```instructions
* tab=2 python3.12
* Use the latest library version (as of 2026/01/01)
* Reusable format
*   Attempt to restart operations even if errors occur.
*   Output error messages when errors occur, but continue operation.
*   Use Japanese for comments. Use English for error messages.
*   Use Snail Case for variable names according to their purpose.
```

# Copilot / AI エージェント向け指示（リポジトリ固有）

概要
- このリポジトリは実験的な自律型 AI エージェントフレームワークです。高レベル設計は `README.md` を参照してください。基本構成は Ollama ベースの LLM がシェル操作を駆使して動作し、ターン毎のログと長期日記を記録します。

主要ルール（削除しないこと）
- 実行環境: `python3.12` を想定し、タブ幅は 2。
- コメント: インラインコメントは日本語。エラーメッセージや CLI 出力は英語。
- 変数命名: スネイルケース（例: `current_state`, `next_objective`）。
- 信頼性: 一時的な失敗はリトライし、未処理例外で落とさず `ai-agent/logs/` へ構造化ログを残すこと。

リポジトリ固有ガイド
- エントリポイント: `ai-agent/main.py` を探してください。実行例:

```bash
python3.12 ai-agent/main.py
```

- データ配置: `ai-agent/logs/` にターン毎の JSON ログ、`ai-agent/memory/` に日記（`diary-YYYYMMDD-hhmmss.md`）を置きます。
- 実行サイクル: Plan → Reflection → Act → Observe のループを踏襲します。各ターンでは `plan` と `observation` を `logs/` に記録してください。
- 統合点: ローカルの Ollama ランタイムと Slack への日記投稿を想定しています。ネットワーク操作前にエンドポイントと必要な環境変数が設定されているか検証してください。

コーディングパターンと具体例
- 変更の提案/適用: システム設定を変更する場合は、まず「シミュレーション」や「予測結果」を `logs/` に書き出し、その後実行（commit）して結果を再度ログに残すワークフローを使ってください。
- 推奨ログスキーマ: `turn_id`, `timestamp`, `plan`, `actions`, `observation`, `reflection` を含めること。
- 日記ファイル: フロントマター（短いメタ情報）と振り返り要約を含む Markdown とし、既存のファイル命名規則に従って `ai-agent/memory/` に追加してください。

実務ワークフロー（エージェントが従うべきこと）
- プレフライトチェック: Ollama 到達性、必要な環境変数（例: Slack トークン）、およびファイルパスの存在を検証してから外部操作を行うこと。
- 特権操作: sudo 権限が必要な操作は人間に確認を取り、自動でエスカレーションを試みないこと（パスワードレス sudo を仮定しない）。
- テスト/例が欠けている場合: `ai-agent/examples/` に小さな再現スクリプトを作成し、`README.md` に実行コマンドを 1 行追記してください。

統合ポイントと確認事項
- Ollama: ローカルの Ollama エンドポイント（CLI または HTTP）に接続できるかを確認し、到達不可の場合は英語で明確なエラーメッセージを出すこと。
- Slack: 必要な環境変数が揃っているか検出してから投稿を行う。資格情報はコードに埋め込まないこと。

人間に確認すべきケース
- エントリポイントや `ai-agent` フォルダ構成が見つからない場合。
- Slack / Ollama の設定や認証情報が不明確な場合。

編集／マージ方針
- ファイル冒頭の指示ブロック（インタプリタ、タブ、コメント言語ルール）は保持すること。
- このファイル自体を肥大化させず、振る舞いの変更は `README.md` や `ai-agent/` 内の実装・例に追記すること。

メンテナ向けの次の確認事項
- 本文を日本語にして問題ないか確認してください（インラインコメントは引き続き日本語でOKです）。
* tab=2 python3.12
* Use the latest library version (as of 2026/01/01)
* Reusable format
*   Attempt to restart operations even if errors occur.
*   Output error messages when errors occur, but continue operation.
*   Use Japanese for comments. Use English for error messages.
*   Use Snail Case for variable names according to their purpose.