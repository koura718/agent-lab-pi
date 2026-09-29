# Claudeモデルでの検証

## 対象

既存のOpenAI Agents SDKのRunner・Function Tool・ローカルMCP Serverを使い、
モデルだけをAnthropicのClaudeへ切り替えて比較します。Claude Codeによるコードレビューとは別です。

`--provider anthropic`はAnthropic公式のOpenAI互換Chat Completions APIへ接続します。
追加のLiteLLM・プロキシ・Anthropic SDKは使用しません。既存のopenai依存を使用します。
公式にはモデル評価向けの互換機能であり、Claudeの全機能を使う本番向け構成ではありません。
`strict`はAPI側で無視されるため、比較処理の既存の厳密な入力検証を維持します。
Prompt caching、Claude固有のthinking、画像・PDF、リモートMCPはこの検証の対象外です。

## 設定

| 項目 | OpenAI | Anthropic |
|---|---|---|
| --provider / AGENT_PROVIDER / agent.provider | openai（既定） | anthropic |
| モデル指定 | --model / AGENT_MODEL、未指定はSDK既定 | --model / AGENT_MODELを必ず指定 |
| キー | OPENAI_API_KEY | ANTHROPIC_API_KEY |
| モデルAPI | SDKのOpenAI既定経路 | https://api.anthropic.com/v1/chat/completions |
| Tracing | 従来どおり明示有効化可能 | 今回は無効のみ。有効化は設定エラー |

CLI > 環境変数 > 明示TOML > 既定値です。.envは自動で読み込みません。
`config/agent.toml`のprovider既定はopenaiです。診断MCP CLIとローカル比較はモデルを呼びません。
Anthropicクライアントは呼出しごとに作成・終了し、SDKのグローバル設定を書き換えません。
OpenAIのキー・base URL・組織/プロジェクト設定をAnthropicクライアントへ引き継ぎません。
今回のAnthropicクライアントはHTTP自動リトライ0、timeoutはAgent全体設定を使用します。
Server子プロセスにはどちらのAPIキーも渡しません。

## Ubuntuでの準備

対象ブランチ取得後、通常検証を先に実行します。

```bash
mise exec -- uv sync --frozen
./scripts/validate.sh
```

自身の`.env`の既存の`ANTHROPIC_API_KEY=`欄に、Claude APIのキーを設定してください。
キーの値をチャット・ログ・Gitへ貼らないでください。ClaudeアプリやClaude Codeのログインではなく、
Claude APIを利用可能なキーとAPI利用枠が必要です。
ここでは通常のワークスペース用APIキーを想定しています。複数ワークスペースを選択する追加ヘッダー設定は未対応です。

## Function Tool経由（実API通信あり）

モデルIDは利用可能なClaudeモデルに合わせて指定します。次は`claude-sonnet-4-6`を使う例です。
このモデルでの実API成功はユーザー環境で確認します。

```bash
(
  set -a
  source .env
  set +a
  unset OPENAI_API_KEY
  export AGENT_PROVIDER=anthropic
  export AGENT_MODEL=claude-sonnet-4-6
  mise exec -- uv run --frozen agent-lab --tool-mode function --no-tracing \
    --prompt 'compare_listsを使いsource=["A","B","B"]とbaseline=["B","C"]を比較してください。'
)
```

`--tool-mode mcp`に変更すると、実LLM → Agent → stdio Server → 比較関数の経路になります。
期待する比較値は`same=["B"] / source_only=["A"] / baseline_only=["C"]`です。
最終文章の表現はモデルに依存します。

## Function / MCP両経路のliveテスト

```bash
(
  set -a
  source .env
  set +a
  unset OPENAI_API_KEY
  export AGENT_PROVIDER=anthropic
  export AGENT_MODEL=claude-sonnet-4-6
  mise exec -- uv run --frozen pytest -m live --run-live -v --maxfail=1
)
```

2件の既存liveテストを選択providerで実行します。OpenAIとClaudeを同時に呼ぶテストではありません。
実Tool呼出しと比較結果を検証し、成功時は2 passedです。
provider不正・対応するキー未設定・モデル未設定は実行前に終了コード4で停止します。
通常CIは引き続き実APIを呼ばずlive 2件をスキップします。

OpenAIへ戻す場合はサブシェル内で`AGENT_PROVIDER=openai`、`AGENT_MODEL=gpt-5-mini`を指定し、
OpenAIキーを用意してください。上の例はサブシェルなので親シェルの設定は変更しません。

## 失敗時

| 症状 | 対応 |
|---|---|
| ANTHROPIC_API_KEY is required | 自分の.envを読み込んだシェルとキー欄を確認 |
| explicit --model / AGENT_MODEL | ClaudeモデルIDを明示 |
| requires --no-tracing | --no-tracingを指定。ClaudeからOpenAIへのTrace送信は今回行わない |
| AuthenticationError / PermissionDeniedError | Claude APIキー、権限、ワークスペースを確認 |
| NotFoundError / BadRequestError | 利用可能モデルID・API互換範囲を確認 |
| RateLimitError | API利用枠・レート制限を確認 |
| Tool契約エラー | モデルがToolへ渡した入力形式を検証。成功扱いにしない |

CLIは例外本文を伏せ、型と一般化した分類をログに出します。キーや生のHTTP要求を共有しないでください。
実API検証は利用料金が発生します。通常のAPI不要テスト成功は実Claude接続成功を意味しません。

## API不要の追加検証

設定の優先順位、キーの分離、モデル必須、Tracing拒否、provider別liveゲートをテストします。
HTTPモックで実OpenAIChatCompletionsModelとRunnerを通し、Tool呼出しID・JSON結果・API送信先を確認します。
MCP側は実子プロセスを起動します。例外・キャンセル時のHTTPクライアント終了も検証します。

参考:
- https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk
- https://platform.claude.com/docs/en/about-claude/models/overview
