# Tracing（Step 8）

## 概要

OpenAI Agents SDKのTraceを明示指定時のみ有効にします。通常のCLI・validate・CI・liveテストは
既定でTracing無効です。診断MCP CLIと--compare-jsonはTracingを受け付けません。
実モデル呼出しとTracing送信は別の外部通信です。

## 設定

CLI > 環境変数 > 明示TOML > falseの順に適用します。

| 指定方法 | 値 |
|---|---|
| CLI | --tracing / --no-tracing |
| 環境変数 | AGENT_TRACING_ENABLED=true / false（1 / 0も可） |
| TOML | [tracing] enabled = true / false（文字列不可） |

.envとconfig/agent.tomlは自動読込みしません。
OPENAI_AGENTS_DISABLE_TRACING=true（または1）が設定されている場合は、
--tracingを指定しても有効化せず設定エラーにします。明示的に無効化した環境を上書きしません。
Agent実行のAPIキーは従来どおりOPENAI_API_KEYです。

## 送信する内容

送信先はSDK標準の https://api.openai.com/v1/traces/ingest です。
workflow名はagent-lab、Trace IDはtrace_<run_id>、group_idはrun_idです。
ログのtrace_enabledイベントにTrace IDを出力します。

SDKのtrace_include_sensitive_data=Falseに加え、export前のProcessorで許可項目だけの
スナップショットを作成します。SDKの生のTrace / Spanを送信キューへ渡しません。

| 記録するもの | 記録しないもの |
|---|---|
| Trace / Span / 親SpanのID | プロンプト・モデル応答・Tool入出力 |
| 開始・終了時刻 | APIキー・モデル設定・任意metadata |
| 処理種別、compare_listsの固定名 | Response ID・任意のAgent/Tool名 |
| エラーの有無と固定メッセージ | SDKの例外本文・エラー詳細 |

Spanはメタデータ専用のcustom spanとして送信します。Dashboardで処理の順序・親子関係・
所要時間を確認できます。会話内容、Token使用量、モデル固有の詳細表示は今回の対象外です。
MCP経路はAgent側のSDK Spanを対象とします。Server内部の処理時間は共通run_idのstderrログで確認します。
ServerにTracing exporterやAPIキーを渡しません。

## Ubuntuでの実確認（任意・実API課金あり）

通常テストが成功した後、必要な場合だけ実行してください。

```bash
(
  set -a
  source .env
  set +a
  export AGENT_MODEL=gpt-5-mini
  mise exec -- uv run --frozen agent-lab --tool-mode mcp --tracing \
    --prompt 'compare_listsを使いsource=["A","B"]とbaseline=["B","C"]を比較してください。'
)
```

以前にOPENAI_AGENTS_DISABLE_TRACINGを設定している場合は、設定理由を確認してから
そのサブシェルで解除してください。通常テスト側の無効化設定を削除する必要はありません。
Function経路は--tool-mode functionに変更します。

実行後、OpenAI PlatformのTraces画面（https://platform.openai.com/traces）を開き、
APIキーと同じプロジェクトでログに出たTrace IDを探してください。
対応するrun_id、Agent/Toolの処理順、入出力本文が含まれていないことを確認します。

## 終了と失敗

CLIは実行終了時に送信処理を最大5秒待ちます。Agentの全体timeoutとは別の終了待ちです。
送信はbest effortで、trace_enabledログはDashboard到達の保証ではありません。
SDKのexport警告は本文を伏せたtrace_export_warningとして通知します。
バックグラウンドthreadの警告ではrun_idが `-` の場合があります。
送信失敗・shutdown失敗によって成功したAgent結果を失敗にはしません。
SDKは送信を中断・破棄する場合があるため、キャンセルやネットワーク断時にはTraceが不完全になり得ます。

| 症状 | 確認 |
|---|---|
| ConfigurationError | Tracing無効化環境変数、設定の型、診断CLIでの有効化を確認 |
| trace_enabledがない | --tracing / 設定の優先順位、ログレベルを確認 |
| trace_export_warning | APIキーのプロジェクト・Tracing利用可否・ネットワークを確認 |
| Dashboardで見つからない | Trace ID、対象プロジェクト、送信待ち時間を確認 |
| Toolの本文が見えない | メタデータのみを送る仕様 |

## 埋込み利用

SDKのTraceProviderはプロセス全体の設定です。CLIは一時的に専用Providerを使い、
正常・例外・timeoutのいずれでも元のProviderへ戻します。二重のruntime開始は拒否します。
他のライブラリが同時にSDK Providerを変更するプロセスへの埋込みは対象外です。

直接run_agentを呼ぶ場合、Tracing有効時は外側で一度だけ
`with tracing_runtime(True):` を使用します。その内側で複数タスクを実行できます。
run_agentの呼出しごとに通常は新しいrun_idを生成します。同じrun_contextの中で複数回呼ぶと
同じTrace IDを使うため、独立した実行には個別のrun_contextを使ってください。
SDKの一般的なset_trace_processors設定とは併用せず、このアプリの送信経路を使用してください。

## API不要の検証

```bash
./scripts/validate.sh
mise exec -- uv run --frozen pytest tests/unit/test_tracing_config.py tests/integration/test_tracing.py -v
```

通常のネットワーク禁止fixtureの下で、ScriptedModelとメモリ内sinkを使います。
両Tool経路、既定無効、設定優先順位、無効化環境変数、入力/出力/エラー本文の除去、
Trace ID対応、例外/timeout後の復元、runtime二重開始防止を検証します。
送信時のJSONはHTTPモックで確認します。実モデルや実Tracing endpointは呼びません。

- [ ] 通常validation成功、live 2件スキップ
- [ ] tracing有効のAPI不要テスト成功
- [ ] 必要な場合のみ実APIとDashboardを手動確認

## これだけ覚えればOK

通常は何も追加せず実行します。追跡が必要なAgent実行だけ--tracingを付け、
stderrのTrace IDでDashboardを確認します。--no-tracingで明示的に無効化できます。

参考: https://developers.openai.com/api/docs/guides/agents/integrations-observability
固定したopenai-agents 0.22.2のローカルソースも確認して実装しています。
