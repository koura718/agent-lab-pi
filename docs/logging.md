# Application Logging（Step 9）

## 概要

全CLIのログ設定をlogging_config.pyへ集約しました。比較本体・stdoutの結果JSON・
終了コード・MCP通信契約は維持します。Tracingは既定で無効です。Step 8で明示指定時のメタデータ送信を追加しました。[Tracing手順](tracing.md)を参照してください。

```text
[2026-09-27T10:00:00Z] [INFO] run_id=0123456789abcdef0123456789abcdef event=mcp_request_completed duration_ms=850.321 error_kind=none completed
```

| 項目 | 意味 |
|---|---|
| 時刻 | UTC、秒単位。末尾Zで明示（日本時間は+9時間） |
| run_id | CLI実行ごとに生成するUUIDの32桁小文字hex |
| event | 操作名_started / _completed / _failed。既存メッセージはmessage |
| duration_ms | perf_counterによる処理時間。終了イベント以外は `-` |
| error_kind | 下表の分類。通常はnone |

Agent、MCP診断要求、Server稼働、MCP Tool、Function比較を計測します。
Clientの要求時間にはServer起動・接続終了待ちを含みます。
Server稼働時間は接続中の全期間です。各Toolの時間は個別に計測します。
入れ子イベントの時間は重複するため、単純合算しないでください。

## 実行IDと設定

CLI実行で生成したIDをasyncioタスクとMCP子プロセスへ引き継ぎます。
並列実行にはContextVarを使用し、処理後に前のコンテキストへ戻します。
run_agent / execute等を直接呼ぶ場合も、外側にIDがなければ操作開始時に生成します。
独立した複数操作をまとめたい場合はPython側でrun_context()を使えます。

既存の --log-level / AGENT_LOG_LEVEL / logging.level（TOML）を使用します。
CLI > 環境変数 > 明示TOML > 既定INFOの優先順位を維持します。
WARNINGまたはERRORでは正常系の開始・完了ログを抑制します。

MCP Serverには専用のAGENT_LAB_RUN_ID / AGENT_LAB_SERVER_LOG_LEVELだけを追加で渡します。
IDは32桁小文字hexのみ許可し、不正値なら新規生成します。
ServerのログレベルはINFO / WARNING / ERRORのみ許可し、不正値はINFOへ戻します。
親の環境変数全体やAPIキーは渡しません。
Server単体起動時もIDを生成します。専用環境変数は内部の引継ぎ用で、認証や監査の証明には使いません。

## エラー分類

| 分類 | 対象 |
|---|---|
| none | 正常 |
| invalid_input | Function比較の入力不正、ValueError |
| configuration_error | CLI設定不正、APIキー未設定 |
| timeout | PythonのTimeoutError |
| cancelled | asyncioキャンセル、ユーザー中断 |
| transport_error | ConnectionError / OSError |
| mcp_error | MCPError、EndOfStream、ClosedResourceError |
| tool_error | MCP Toolがerror結果を返した場合 |
| execution_error | その他の実行エラー、異なる分類を含むExceptionGroup |

SDKがMCPErrorとして通知する要求timeoutはmcp_errorです。
API認証・利用上限等のSDK例外は今回execution_errorにまとめます。
分類は監視用の大分類であり、stdoutの既存error.codeとは別です。
例外のメッセージ・tracebackはアプリの終了ログに出しません。
CLI引数の構文エラーはargparseの既存の説明形式を維持します。

## API不要の動作確認

```bash
mise exec -- uv run --frozen agent-lab-mcp-client call compare_lists \
  --arguments '{"source":["A","B","B"],"baseline":["B","C"]}'

mise exec -- uv run --frozen agent-lab-mcp-client --log-level WARNING \
  call compare_lists --arguments '{"source":[],"baseline":[]}'
```

最初の実行はClient / Serverの同じrun_idを確認します。
2回目は正常系ログを出さず、stdoutに比較JSONだけを出します。

```bash
mise exec -- uv run --frozen agent-lab --compare-json '{}'
```

最後は意図的な不正入力です。stderrにinvalid_input、stdoutに既存error JSON、終了コード2になります。

## 出力と秘密情報

ログはstderr、CLI結果とMCPプロトコルはstdoutです。アプリのhandlerはagent_labのログのみを出力します。
プロンプト・入力配列・Tool出力・APIキーをイベントに記録しません。
依存SDKのログはこのhandlerでは出力しません。埋込み先が独自handlerを設定した場合、その出力方針は埋込み先で管理してください。
この仕組みは任意のメッセージを自動マスキングするものではありません。
今後のログ追加でも生の入力や例外メッセージを渡さないでください。

ファイル保存・ローテーション・JSONログ形式は今回追加しません。
必要な場合はstderrを明示的に保存できます。保存先logs/はGit管理対象外です。

## 検証

通常テストで、重複handler防止、レベル、並列ID分離、例外後の復元、不正な引継ぎID拒否、
実Client / ServerのID一致、入力値・ダミー秘密値がstderrに出ないことを検証します。
既存のMCP異常系・キャンセル・回収テストも維持します。実LLMは使いません。

- [ ] validate成功
- [ ] stdoutの比較結果が従来どおり
- [ ] Client / Serverのrun_id一致
- [ ] WARNING時の正常ログ抑制
- [ ] 不正入力でerror_kind=invalid_input

## これだけ覚えればOK

障害時はstderrのrun_idとerror_kindを確認します。通常の確認はvalidate.shです。
