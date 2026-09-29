# Cerebras Agent接続・並列評価

## 概要

OpenAI Agents SDKのChat Completionsアダプタを使い、Cerebrasへ直接接続します。
接続先は`https://api.cerebras.ai/v1/`、キーは`CEREBRAS_API_KEY`です。
OpenAI・AnthropicのキーやOpenAIのbase URL・組織設定を流用しません。
Function Tool / MCP両経路を利用でき、MCP子プロセスにはAPIキーを転送しません。
依存追加はありません。Tracingと互換APIクライアントの自動再試行は無効です。

## 準備

```bash
mise exec -- uv sync --frozen
./scripts/validate.sh
```

既存の`.env`をエディタで開き、`CEREBRAS_API_KEY`を追加してください。
bootstrapは既存`.env`を上書きしません。キーをGitやチャットへ貼らないでください。
モデルIDは利用アカウントでアクセス可能なものを指定します。
以下の`qwen-3.8-27b`は公式ドキュメントの例で、当プロジェクトでの実API検証は未実施です。

## Cerebras単独でFunction / MCPを検証

以下は有料APIを明示的に実行します。OpenAI・Anthropicキーは不要です。

```bash
(
  set -a
  source .env
  set +a
  unset OPENAI_API_KEY ANTHROPIC_API_KEY
  export AGENT_PROVIDER=cerebras
  export AGENT_MODEL=qwen-3.8-27b
  mise exec -- uv run --frozen pytest -m live --run-live -v --maxfail=1
)
```

期待値はlive 2件の成功です。通常検証ではliveはスキップされます。
単独CLIは`--provider cerebras --model qwen-3.8-27b --no-tracing`で選択できます。
設定優先順位はCLI > 環境変数 > 明示TOML > 既定値です。

## 3モデル同時実行

3つのAPIキーを`.env`に設定します。選択した全サービスでAPI料金が発生します。

```bash
(
  set -a
  source .env
  set +a
  mise exec -- uv run --frozen agent-lab-compare-models \
    --openai-model gpt-5-mini \
    --anthropic-model claude-sonnet-4-6 \
    --cerebras-model qwen-3.8-27b \
    --tool-mode function \
    --arguments '{"source":["A","B","B"],"baseline":["B","C"]}'
)
```

`--tool-mode mcp`へ変更すると専用Serverを3つ起動し、終了時に回収します。
任意の2つのモデル引数だけ指定する比較も可能です。未選択providerのキーは不要です。

入力はsource / baselineの文字列配列です。stdoutへ結果JSON、stderrへメタデータログを出します。
合格条件は全体とruns内の全statusがsuccess、results_matchがtrueです。
期待Tool結果はsame=[B]、source_only=[A]、baseline_only=[C]です。
各Agentのrun_idは別々です。最終応答の文面の一致は要求しません。

キー不足・入力不備はAPI実行前に終了コード2で停止します。
開始後のAPI失敗・timeoutは他のAgentを止めず、成功分を含むJSONと終了コード1を返します。
Ctrl+Cでは全タスクを中断して接続を閉じます（部分JSONは保存しません）。
詳細は[並列比較仕様](mixed-models.md)を参照してください。

## 互換範囲と注意点

- テキスト入力とTool callingの評価用です。画像・Streaming・handoffは追加していません。
- Qwen 3.8のstrict tool schemaはminLength / maxLengthを受け付けません。
  CerebrasのFunction Toolではstrictをfalseにし、長さ・型・件数は既存Pythonドメイン関数で検証します。
  MCPのToolもSDK既定の非strictで動作し、Server側で同じ検証を行います。
- `qwen-3.8-27b`は`reasoning_effort=none`を送ります。
  現アダプタはCerebras固有のreasoning履歴再送を実装していないためです。
  他のモデルにはこの値を強制しません。別モデルの互換性はlive検証が必要です。
- Toolとresponse_formatの同時指定は行いません。最終応答のJSON化はアプリ側レポートです。
- 401/403はキー・アクセス権、404はモデルID、429は利用枠を確認してください。
  timeout時は`--run-timeout`を調整できます。API例外本文は秘密情報保護のためログに出しません。
- モデル提供状況・料金・制限は変動します。計測時間はネットワークとMCP起動を含みます。

## 検証範囲

API不要のテストで接続URL・キー分離、Tool往復、クライアント終了、
2〜3Agentの並列性、第三モデルの失敗・結果不一致、MCPプロセス回収を確認します。
HTTPモックによる成功は実APIの互換性やアカウントのモデル利用権を保証しません。
実APIの最終確認は上記liveテストと並列CLIで行ってください。

## 簡易チェックリスト

- `.env`にCerebrasキーを追加する。
- 通常検証を実行する。
- Cerebras単独live 2件を確認する。
- 3モデルのFunction / MCPを実行し、全statusとresults_matchを確認する。

## 公式資料（2026-09-28確認）

- [OpenAI互換API](https://inference-docs.cerebras.ai/resources/openai)
- [Tool calling](https://inference-docs.cerebras.ai/capabilities/tool-use)
- [Reasoning](https://inference-docs.cerebras.ai/capabilities/reasoning)
