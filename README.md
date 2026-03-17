# aibots

## Linux自律型AIエージェント構成仕様書

1. システム概要
Ubuntu 24.04上で動作し、OllamaベースのLLMがシェルコマンドを介してシステムを自律操作する実験的フレームワーク。

### 主要機能
* 権限: Linux管理者権限（sudoパスワードレス推奨）の行使。
* 思考ループ: 提案(Plan) → 壁打ち(Reflection) → 実行(Act) → 観察(Observe) のサイクル。
* 記憶構造:
  * 短期: Ollama Contextによる対話履歴。
  * 中期: 各ターンの詳細ログ（JSON形式）。
  * 長期: 自己反省を含む日記（Markdown形式）。
* 自律性: 定期的な日記の読み込みと、独創的な「新目的（NEW_OBJECTIVE）」の自己生成。
* 日記を定期的にSlack APIを使用してSlackに書き込む。

## フォルダ構成案
/ai-agent
├── main.py          # エージェント実行スクリプト
├── logs/            # 実行結果のRAWデータ（Turn毎のJSON）
└── memory/          # 長期記憶
    └── diary-yyyyMMdd-hhmmss.md     # AI自身が執筆する活動記録と次の方針
└── tools/           # エージェントが保存・実行できる補助スクリプト（ツール）


### Geminiによる提案実装
Ubuntu 24.04上で動作する、自律型エージェントの最小構成サンプル（MVP）を作成しました。
このコードは、OllamaのAPI（デフォルト：localhost:11434）を利用し、シェルコマンドの実行結果を次の思考にフィードバックするループ構造を持っています。

[!CAUTION]
非常に強力で危険なツールです。 > ホワイトリストなしでLLMに管理者権限を渡すため、意図しないシステム破壊やデータの消失が起こり得ます。必ず実験用環境（VMや隔離されたコンテナなど）で実行してください。

事前準備
Ollamaの起動: ollama serve が実行され、モデル（例: llama3 や gemma2）がプルされていること。

ライブラリ: `pip install requests pyyaml`

ディレクトリ作成: `mkdir -p logs memory`