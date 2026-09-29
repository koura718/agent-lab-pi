# AI Agent Lab

OpenAI Agents SDKとMCPを使い、Toolの実装・接続・テスト・運用を学び、拡張するためのPythonプロジェクトです。
この派生版にはPiとCerebrasのQwen3.8 27Bを使う実行環境も追加しています。
OpenAI・Anthropic（Claude評価用互換API）・Cerebrasのモデルを切り替え、同じプロセス内で並列に比較できます。
文字列配列を比較する`compare_lists`を、Function Toolと別プロセスのMCP Serverから利用できます。
Ubuntu 24.04を基準に、API不要の検証、実LLMの明示的な検証、CI、ログ、Tracing、環境構築を実装しています。

GitHub Template Repositoryとして再利用できます。ライセンスは[MIT](LICENSE)です。
CodexとClaude Codeは開発支援ツールで、アプリケーションの実行に必須ではありません。

## まず使うコマンド

Gitとmiseが利用可能なUbuntu 24.04で実行します。

```bash
git clone git@github.com:koura718/agent-lab-pi.git
cd agent-lab-pi
```

[mise.toml](mise.toml)の内容を確認し、信頼を許可してセットアップします。

```bash
mise trust mise.toml
./scripts/bootstrap.sh --setup --check &&
./scripts/bootstrap.sh --setup
```

`--check`は前提条件だけを確認します。通常の`--setup`はツール導入、固定依存の同期、
未作成の`.env`の作成、lint・テスト等の検証まで実行します。
既存の`.env`は上書きせず、内容も読み込みません。APIキーは不要ですが、依存のダウンロードには通信が必要です。

**環境構築には必ず`--setup`を付けてください。** 引数なしの`bootstrap.sh`は、
ディレクトリ名に基づくプロジェクト名・Pythonパッケージ名変更の別機能です。
従来の`./scripts/setup.sh`も同じ環境構築を実行します。

APIなしで比較します。

```bash
mise exec -- uv run --frozen agent-lab --tool-mode function --no-tracing \
  --compare-json '{"source":["A","B","B"],"baseline":["B","C"]}'
```

```json
{"same": ["B"], "source_only": ["A"], "baseline_only": ["C"]}
```

日常の変更後の検証は次のコマンドです。

```bash
./scripts/validate.sh
```

### Pi + Cerebras を追加する

上記のPython環境のセットアップが完了した後、Piをリポジトリ内に固定バージョンで導入します。

```bash
./scripts/setup-pi.sh
```

`.env`の`CEREBRAS_API_KEY=`にCerebras Cloudのキーを設定して起動します。

```bash
mise exec -- pnpm pi
```

起動、MCP接続、確認方法と記事との対応は[Pi + Cerebras手順](docs/pi-cerebras.md)を参照してください。

詳しい導入・再実行・障害対応は[bootstrap手順](docs/bootstrap.md)を参照してください。

## 実装済みの機能

| Step | 項目 | 現在の実装 |
|---|---|---|
| 1 | Setup | miseのツール導入、固定依存の同期、.env作成、検証 |
| 2 | Validation | Ruff、pytest、compile、Git差分・秘密情報の基本確認 |
| 3 | Function Tool | compare_lists、厳密な入力検証、Agentへの登録 |
| 4 | MCP Server | 比較本体を共有し、stdioでTool一覧・呼出しを公開 |
| 5 | MCP Client | 診断CLI、Agent接続、timeout、子プロセス終了処理 |
| 6 | Integration Tests | 両経路の一致、異常系、キャンセル、実LLMの明示ゲート |
| 7 | CI | Ubuntu検証、JUnit保存14日、失敗時の調査手順 |
| 8 | Tracing | 明示有効化、メタデータのみ送信、ログのrun_idとの対応 |
| 9 | Application Logging | 共通stderrログ、実行ID、処理時間、エラー分類 |
| 10 | Bootstrap | --setup入口、前提確認、再実行、既存.env保持、CI経由の検証 |

2モデル並列対応（PR #13）のUbuntu検証結果は **189 passed, 2 skipped** です。
2件のskipは明示実行しなかったliveテストです。別途、`gpt-5-mini`でFunction / MCPのlive 2件成功と、
MCP経路のTraceのDashboard表示を確認しています。`claude-sonnet-4-6`もFunction / MCPのlive 2件成功を確認済みです。実LLMの結果はモデル・接続環境に依存します。

## 環境と前提

| 項目 | 基準・役割 |
|---|---|
| OS | Ubuntu 24.04。Windowsネイティブのスクリプト実行は未検証 |
| Python | 3.14.7。アプリ本体・テストを実行 |
| uv | 0.12.12。Python依存管理 |
| Node.js / pnpm | 24.21.0 / 12.3.4。開発環境の共通ツール |
| mise | 基準環境で2026.9.5。事前導入が必要 |
| Git | clone・差分検証に必要 |
| GitHub CLI | PR・CI等をCLIから操作する場合のみ必要 |
| OpenAI APIキー | 実LLMを呼ぶ場合のみ必要 |

ツールの固定値は[mise.toml](mise.toml)、Python依存の解決結果は[uv.lock](uv.lock)を正とします。
アプリ本体はPythonで動作し、NodeサービスやDockerコンテナは起動しません。
bootstrapはGit・miseのOS導入、sudo操作、シェル設定変更、開発支援CLIのインストールを行いません。

手動で同期する場合もlockを使用します。lockが欠落した場合はGitから復元してください。

```bash
mise install
mise exec -- uv sync --frozen
./scripts/validate.sh
```

## 比較処理とToolの使い方

`compare_lists`は`source`と`baseline`を集合として比較します。
入力を変更せず、ファイル操作・DB更新・外部通信も行いません。

| 契約 | 内容 |
|---|---|
| 入力 | source / baselineの2配列が必須。空配列可、各1,000要素以下 |
| 要素 | 文字列のみ、各1〜256文字。自動型変換なし |
| 比較 | 重複を除去。大小文字・空白・Unicode表記は保持して区別 |
| 結果 | same / source_only / baseline_onlyをPython文字列の標準順序でソート |
| 不正入力 | 成功結果へ変換せず拒否。ローカルCLIはerror JSONと終了コード2 |

[Tool契約](docs/tool-contract.md)に境界値とエラー形式を記載しています。

### MCP診断CLI（API不要）

```bash
mise exec -- uv run --frozen agent-lab-mcp-client --no-tracing list-tools

mise exec -- uv run --frozen agent-lab-mcp-client --no-tracing \
  call compare_lists --arguments '{"source":["A","B","B"],"baseline":["B","C"]}'
```

ClientがローカルServerを起動し、初期化・要求・接続終了・子プロセス回収を行います。
`list-tools`は名前・説明・入出力schema等を含む`{"tools": [...]}`、`call`は比較結果JSONを返します。
共通オプションは`list-tools` / `call`より前に指定します。

Serverをstdioクライアントから直接起動するときの入口は次のとおりです。
単体実行はプロトコル入力待ちになるため、手動確認には診断CLIを使用してください。

```bash
mise exec -- uv run --frozen agent-lab-mcp
```

Serverは`python -m agent_lab.mcp.server`、Clientは`python -m agent_lab.mcp.client`でも起動できます。
HTTP公開、任意の外部Serverコマンド、リモートURL接続の設定は現在の対象外です。

### 実LLMからToolを使う（任意・API課金あり）

bootstrapで作成した`.env`に、自分の`OPENAI_API_KEY`を設定してください。
`.env.example`にはキーの値を保存しません。`ANTHROPIC_API_KEY`欄はClaudeモデルで検証する場合に使用します。

自分で管理する`.env`をサブシェルで読み込み、モデルを指定して実行します。
`gpt-5-mini`はこのプロジェクトでの検証済み例です。利用可能なモデルに合わせて変更できます。

```bash
(
  set -a
  source .env
  set +a
  export AGENT_PROVIDER=openai
  export AGENT_MODEL=gpt-5-mini
  mise exec -- uv run --frozen agent-lab --tool-mode function --no-tracing \
    --prompt 'compare_listsを使いsource=["A","B","B"]とbaseline=["B","C"]を比較してください。'
)
```

`--tool-mode mcp`に変更すると、Agentが別プロセスのServerから同じToolを使います。
MCPモードではFunction Toolを二重登録しません。MCP Tool呼出しの自動再試行は無効です。

`agent-lab`と`python -m agent_lab.main`は同じCLIです。
**引数なし実行も実LLM APIを呼びます。** API不要の確認には`--compare-json`または診断CLIを使用してください。

### Claudeで同じToolを検証する

`--provider anthropic --model claude-sonnet-4-6 --no-tracing`でAnthropicの評価用互換APIを使えます。
`ANTHROPIC_API_KEY`が必要で、OpenAIキーは不要です。Function / MCPの両経路に対応します。
準備・liveテスト・互換範囲は[Claude検証手順](docs/claude.md)を参照してください。

### GPT・Claude・Cerebrasを並列に比較する

`agent-lab-compare-models`で同じ入力を選択した2〜3モデルへ同時に渡せます。
選択したproviderのAPIキーを読み込んだシェルで実行してください（API課金あり）。

```bash
mise exec -- uv run --frozen agent-lab-compare-models \
  --openai-model gpt-5-mini --anthropic-model claude-sonnet-4-6 \
  --cerebras-model qwen-3.8-27b \
  --tool-mode function \
  --arguments '{"source":["A","B","B"],"baseline":["B","C"]}'
```

`--tool-mode mcp`なら各Agentが専用Serverを使います。実行ID・所要時間・最終応答・Tool結果を
JSONで返し、片側のAPI失敗でも他方の結果を保持します。Tracingはすべて無効です。
この専用CLIは`AGENT_PROVIDER`や`AGENT_MODEL`ではなく個別引数で設定します。
[並列比較の設定・レポート・終了コード](docs/mixed-models.md)を参照してください。

Cerebrasを使わない従来の2モデル実行も維持しています。任意の2 providerも選択できます。
単独実行は`agent-lab --provider cerebras --model qwen-3.8-27b --no-tracing`です。
`CEREBRAS_API_KEY`の設定、live検証、互換制約は[Cerebras手順](docs/cerebras.md)を参照してください。
Cerebrasの実API検証は未実施です。Qwenのreasoningは本評価経路では無効化します。

## 設定

以下は単一providerのAgent / MCP診断CLIの設定です。

優先順位は **CLI > 環境変数 > 明示したTOML > 既定値** です。
`.env`と`config/agent.toml`は自動読込みしません。
各層で値を検証するため、下位層の不正値を上位層で隠すことはできません。

| CLI | 環境変数 | TOML | 既定値 |
|---|---|---|---|
| --provider | AGENT_PROVIDER | agent.provider | openai |
| --tool-mode | AGENT_TOOL_MODE | agent.tool_mode | function |
| --model | AGENT_MODEL | agent.model | SDK既定 |
| --max-turns | AGENT_MAX_TURNS | agent.max_turns | 5 |
| --run-timeout | AGENT_RUN_TIMEOUT_SECONDS | agent.run_timeout_seconds | 60秒 |
| --connect-timeout | MCP_CONNECT_TIMEOUT_SECONDS | mcp.connect_timeout_seconds | 10秒 |
| --call-timeout | MCP_CALL_TIMEOUT_SECONDS | mcp.call_timeout_seconds | 10秒 |
| --log-level | AGENT_LOG_LEVEL | logging.level | INFO |
| --tracing / --no-tracing | AGENT_TRACING_ENABLED | tracing.enabled | false |

TOMLを使う例です。

```bash
mise exec -- uv run --frozen agent-lab-mcp-client \
  --config config/agent.toml --no-tracing --call-timeout 15 list-tools
```

timeoutは有限の正数で最大3,600秒、最大ターン数は1〜100、ログレベルはINFO / WARNING / ERRORです。
終了時の子プロセス回収やTrace送信待ちがあるため、設定秒数がCLI全体の厳密な終了期限になるわけではありません。
詳細は[MCP Client手順](docs/mcp-client.md)を参照してください。

## 構成

| パス | 責務 |
|---|---|
| src/agent_lab/domain/list_comparison.py | SDK非依存の入力検証・比較処理 |
| src/agent_lab/tools/list_tools.py | JSON境界・Function Toolアダプタ |
| src/agent_lab/agent_factory.py | Function / MCPのAgent生成 |
| src/agent_lab/main.py | ローカル比較・実LLM AgentのCLI |
| src/agent_lab/mcp/ | stdio Server・診断Client・接続ライフサイクル |
| src/agent_lab/model_comparison.py | GPT / Claude / Cerebrasの並列実行・Tool契約検証・結果レポート |
| src/agent_lab/model_provider.py | provider選択・Anthropic / Cerebras互換APIクライアントの生成と終了 |
| src/agent_lab/config.py | CLI・環境変数・TOMLの設定と検証 |
| src/agent_lab/logging_config.py | 共通ログ・実行ID・処理時間・エラー分類 |
| src/agent_lab/tracing_config.py | 明示的なTracing・送信項目の制限 |
| config/agent.toml | 秘密情報を含まない設定例 |
| tests/unit/・tests/test_smoke.py | 比較・設定・CLI・bootstrap等の検証 |
| tests/integration/ | 実MCP子プロセス・経路一致・終了処理等の検証 |
| tests/live/ | 実LLMの明示実行テスト |
| tests/fixtures/ | 遅延・異常終了を再現するテスト専用Server |
| scripts/ | bootstrap・setup・validate |
| .github/workflows/validate.yml | Ubuntu CI・JUnit保存 |
| docs/ | 設計・契約・操作・障害対応手順 |

Function ToolとMCP Serverは同じドメイン関数を呼びます。
診断ClientはLLMを経由せずMCPを確認でき、AgentはFunction / MCPのいずれか一方を利用します。
MCPは現在のPython環境で`shell`を介さず起動し、APIキーを子プロセスへ転送しません。
[アーキテクチャ](docs/architecture.md)と[Step 3〜6の設計記録](docs/next-steps-3-6.md)も参照できます。

## テストとCI

`validate.sh`はRuff lint・format、pytest、Python compile、Git whitespace、
`.env`のGit除外、`.env.example`のAPIキー欄を確認します。
テストまで到達すると`reports/pytest.xml`を生成します。通常はlive 2件をスキップします。

```bash
# 全体検証
./scripts/validate.sh

# 実MCPプロセスを含む統合テストだけ
mise exec -- uv run --frozen pytest -m integration -v

# lint / formatの個別確認
mise exec -- uv run --frozen ruff check .
mise exec -- uv run --frozen ruff format --check .
```

通常テストはScriptedModelやモックを使い、モデルAPI・実Tracing endpointを呼びません。
ネットワーク禁止fixtureは親テストプロセスに適用され、OSの通信隔離を提供するものではありません。
Tracingテストではメモリ内sinkやHTTPモックで送信内容を検証します。

実LLMのFunction / MCP両経路を検証するときだけ、次を実行します。

```bash
(
  set -a
  source .env
  set +a
  export AGENT_PROVIDER=openai
  export AGENT_MODEL=gpt-5-mini
  mise exec -- uv run --frozen pytest -m live --run-live -v --maxfail=1
)
```

`--run-live`、選択providerのAPIキー、`AGENT_MODEL`が必要です。
既定はOpenAIです。`AGENT_PROVIDER=anthropic`なら`ANTHROPIC_API_KEY`を使います。
明示実行時のキー・モデル不足は設定エラー、API失敗はテスト失敗になります。
liveテストもTracingは無効です。詳細は[テスト手順](docs/testing.md)を参照してください。

GitHub Actionsはmain向けPRとmainへのpushで、Ubuntu 24.04上のbootstrapを実行します。
JUnitは`pytest-results-RUN_ID-ATTEMPT`というArtifact名で14日保存し、結果をSummaryに出します。
XML未生成の失敗ではArtifactはありません。

2026-09-28確認時点で、`protect-main` rulesetは有効です。
PR経由・`Validate repository`成功・最新baseへの追従を必須とし、force push・削除を禁止しています。
必須承認人数は0、bypass設定はありません。テンプレートから作成した別リポジトリでは別途設定が必要です。

```bash
gh run list --workflow validate.yml --limit 5
```

失敗ログ・Artifactの取得方法は[CI運用手順](docs/ci.md)を参照してください。

## LoggingとTracing

アプリのログはstderr、比較JSONやAgentの最終応答はstdoutです。
MCP Serverのstdoutはプロトコル通信専用です。

```text
[2026-09-28T00:00:00Z] [INFO] run_id=0123456789abcdef0123456789abcdef event=mcp_tool_completed duration_ms=0.266 error_kind=none completed
```

UTC時刻、実行ID、イベント、処理時間、エラー分類を出力します。
ClientとServerでrun_idを共有し、timeout・cancelled・invalid_input等を分類します。
入力配列・プロンプト・APIキー・例外本文はアプリのイベントログに記録しません。
ファイル保存・ローテーションは自動では行いません。詳しくは[Logging手順](docs/logging.md)を参照してください。

Tracingは既定で無効です。実LLMの実行例の`--no-tracing`を`--tracing`へ変更すると有効になります。
TraceにはID・処理種別・開始終了時刻・一般化したエラー等のメタデータだけを送ります。
プロンプト・モデル応答・Tool入出力はTraceへ送らず、custom spanで階層と時間を確認できます。
この本文除外はTraceの設定であり、モデルAPIのResponsesログとは別です。

ログの`trace_id=trace_<run_id>`を、[OpenAI Platform](https://platform.openai.com/traces)の
Agents SDKのTrace画面で確認します。`trace_enabled`は有効化の記録で、送信到達の保証ではありません。
`OPENAI_AGENTS_DISABLE_TRACING=true`または`1`がある場合、有効化は設定エラーになります。
ローカル比較・診断CLIはTracingを受け付けません。[Tracing手順](docs/tracing.md)を参照してください。

## 開発と再利用

[AGENTS.md](AGENTS.md)・[CLAUDE.md](CLAUDE.md)を確認し、ブランチで変更してPRを作成します。
Python依存はuv、Node関連はpnpm、ランタイムはmiseで管理します。
変更後は`./scripts/validate.sh`と`git diff --check`で確認してください。
実APIテストは日常検証とは別に、必要な場合だけ実行します。

このリポジトリはGitHubのTemplate Repositoryとして有効化済みです（2026-09-28確認）。
GitHub CLIで別リポジトリを作る例です。

```bash
gh repo create my-agent --private --template koura718/agent-lab --clone
cd my-agent
mise trust mise.toml
./scripts/bootstrap.sh --setup
```

テンプレートをコピーしてもPythonパッケージ名`agent_lab`やCLI名`agent-lab`はそのままです。
既存の名前変更機能は`bootstrap.sh --project-name ... --package-name ...`ですが、
Step 10で検証したのは環境構築の`--setup`です。名前変更後の再利用検証は未完了です。
利用する場合は専用ブランチで`--dry-run`から確認し、import・CLI・lock・文書をレビューしてください。

今後の拡張候補は、新しいTool、アプリ側の構造化された最終応答、Agent間の役割分担・連携、外部API / DB連携です。
現在のMCP構造化Tool結果と、将来のAgent最終応答の構造化は別の機能です。

## 秘密情報とバックアップ

`.env`、APIキー、OAuthトークン、SSH秘密鍵はGitへ保存しません。
bootstrapは新規`.env`を権限600で作成し、既存ファイルは保持します。
既存権限が600以外なら警告するため、必要に応じて自分で修正してください。

```bash
git check-ignore -v .env
```

Git履歴をbundleで保管する場合、作業ツリーの外へ保存できます。

```bash
git bundle create ../agent-lab-backup.bundle --all
git bundle verify ../agent-lab-backup.bundle
```

bundleには未コミットの変更やGit管理外の`.env`は含まれません。
秘密情報は別途管理してください。OS設定・sudo・削除等の操作は影響範囲を確認して実施します。

## 困ったとき

| 症状 | 確認・対応 |
|---|---|
| miseがない / 信頼エラー | PATH・導入状況・mise.tomlの内容と信頼設定を確認 |
| CLIや依存が古い | ブランチを確認し`mise exec -- uv sync --frozen` |
| APIキー未設定 | 実LLMなら自分の.envを読み込む。ローカル比較なら--compare-json |
| 通常テストで2 skipped | live未指定時の正常動作 |
| --compare-jsonが拒否される | --tool-mode functionと--no-tracing、設定値の型を確認 |
| MCP呼出し失敗 | run_id・error_kind、接続/呼出しtimeout、Server終了ログを確認 |
| Traceがない | 対象プロジェクト・Trace ID・有効化設定・export警告を確認 |
| CIでXMLがない | テスト以前のセットアップ・lint等の最初の失敗を確認 |

環境診断には`mise doctor`と`mise current`を使用します。
詳細な実行方法と終了コードは[運用手順](docs/runbook.md)、Server契約は[MCP Server手順](docs/mcp-server.md)にあります。
`docs/next-steps-3-6.md`等のStep別文書には実装当時の計画・検証履歴も含まれます。
現状の入口と完了状況はこのREADME、設定・動作の正確な定義は実装とテストを参照してください。

## License

本プロジェクトは[MIT License](LICENSE)の下で公開しています。

Copyright (c) 2026 Masaaki Koura

依存ライブラリには、それぞれのライセンスが適用されます。
