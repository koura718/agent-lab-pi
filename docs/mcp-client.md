# MCP Client（Step 5）

Step 4のServerを別プロセスで起動し、stdioで接続します。
比較本体と入力契約は変更せず、Function Tool経路も引き続き使用できます。

## API不要の診断CLI

Ubuntu 24.04のリポジトリルートで実行します。

```bash
mise exec -- uv sync --frozen
mise exec -- uv run --frozen agent-lab-mcp-client list-tools
mise exec -- uv run --frozen agent-lab-mcp-client call compare_lists \
  --arguments '{"source":["A","B","B"],"baseline":["B","C"]}'
```

比較結果のstdout:

```json
{"same": ["B"], "source_only": ["A"], "baseline_only": ["C"]}
```

`python -m agent_lab.mcp.client` も同じ入口です。APIキー・モデル呼出しは不要です。
list-toolsは `{"tools": [...]}` を返し、名前・説明・入出力schemaを確認できます。
各コマンドはServer起動・初期化・要求・接続終了を行い、子プロセスの終了を待ちます。
未知のToolや入力契約違反はServerが拒否します。

| 終了コード | 意味 |
|---|---|
| 0 | 正常終了 |
| 1 | 接続・通信・timeout・Toolエラー・応答契約違反 |
| 2 | CLI・JSON形式・設定不正 |
| 130 | ユーザー中断 |

結果はstdout、ログはstderrです。Toolエラーは汎用のerror JSONを返します。
通信失敗時はstdoutに結果を出さず、stderrに例外の型を記録します。
入力値・秘密値・例外メッセージはClientのログに出しません。

## Agentからの接続（任意・API課金あり）

```bash
(
  set -a
  source .env
  set +a
  mise exec -- uv run --frozen agent-lab --tool-mode mcp \
    --prompt 'compare_listsを使いsource=["A","B","B"]とbaseline=["B","C"]を比較してください。'
)
```

OpenAI Agents SDKのMCPServerStdioをAgentに渡します。MCPモードではFunction Toolを
登録せず、Serverから取得したcompare_listsだけを使用します。
`--tool-mode function` が既定値です。`--compare-json` はfunction専用です。
診断CLIは設定内のtool_modeにかかわらずMCPを使用します。
tracingは既定で無効です。Agentは--tracingで有効化できます（[Tracing手順](tracing.md)）。Tool呼出しの自動再試行は無効です。

## 設定

CLI > 環境変数 > `--config` で指定したTOML > 既定値の順です。
TOMLと.envは自動読込みしません。設定ファイルには秘密情報を保存しません。
指定された各設定層を検証するため、下位層の不正値を上位層で隠すことはできません。
不明なTOMLセクション・項目もエラーです。

```bash
mise exec -- uv run --frozen agent-lab-mcp-client \
  --config config/agent.toml --connect-timeout 10 --call-timeout 10 list-tools
```

診断CLIの共通オプションは `list-tools` / `call` より前に指定します。

| CLI | 環境変数 | TOML | 既定値 |
|---|---|---|---|
| --tool-mode | AGENT_TOOL_MODE | agent.tool_mode | function |
| --model | AGENT_MODEL | agent.model | SDK既定 |
| --max-turns | AGENT_MAX_TURNS | agent.max_turns | 5 |
| --run-timeout | AGENT_RUN_TIMEOUT_SECONDS | agent.run_timeout_seconds | 60秒 |
| --connect-timeout | MCP_CONNECT_TIMEOUT_SECONDS | mcp.connect_timeout_seconds | 10秒 |
| --call-timeout | MCP_CALL_TIMEOUT_SECONDS | mcp.call_timeout_seconds | 10秒 |
| --log-level | AGENT_LOG_LEVEL | logging.level | INFO |

timeoutは有限の正数、最大3600秒。max_turnsは整数1〜100です。
ログレベルはINFO / WARNING / ERRORです。model / max_turnsは診断CLIでは使用しません。
接続timeoutは起動・初期化、呼出しtimeoutはMCP要求待ち、全体timeoutは実行全体に適用します。
SDKの要求timeoutは初期化時にも適用されます。終了待ちはtimeout後にも必要なため、
実際のコマンド終了までには子プロセス回収の時間が加わることがあります。
Clientのログレベルは起動するServerにも引き継ぎます。

## プロセスと終了処理

- `sys.executable -m agent_lab.mcp.server` をshellなしで起動します。
- 任意の外部コマンド・リモートURL設定は今回の対象外です。
- cwdは実行時ディレクトリの絶対パスです。インストール済みPython packageを使うため、別ディレクトリからの起動もテストします。
- 子環境はMCP SDKのOS用allowlist、PYTHONIOENCODING、生成した実行IDとログレベルのみ。親の環境を丸ごと渡さず、APIキーをServerへ転送しません。
- 接続を所有する専用asyncioタスクでSDKの開始・終了を対にします。呼出し元がキャンセルされても、そのタスクで終了処理を行います。
- compare_listsは読み取り専用で、ファイル操作や外部ネットワーク通信を行いません。

## API不要の検証

```bash
./scripts/validate.sh
mise exec -- uv run --frozen pytest -m integration -v
```

既存のFunction Tool / Serverテストに加え、次を検証します。

- TOML・環境変数・CLIの優先順位、設定とJSONの不正値。
- 実Serverからの一覧取得・呼出し・入力エラー。
- ScriptedModel → Runner → 実MCP Server → 比較結果 → 最終応答。
- Toolの二重登録防止、APIキーを子環境に渡さないこと。
- 接続timeout・呼出しtimeout・キャンセル・Agent全体timeout後の子プロセス回収。

Step 6でliveテストの明示ゲートを追加しました。[テスト運用手順](testing.md)を参照してください。
