# Agent Lab Pi

**Pi + Cerebrasを対話型Agentの実行環境にし、Python製のTool・MCPと組み合わせて開発・検証するリポジトリです。**

[koura718/agent-lab](https://github.com/koura718/agent-lab)を基に、Piのローカルインストール、Cerebrasへの接続、既存の`compare_lists`を呼び出す拡張、Skill、検証手順を追加しています。基準OSはUbuntu 24.04です。

- **Pi経路**：ターミナルからCerebrasの`qwen-3.8-27b`と対話し、Pi拡張を通じてPython MCPを利用します。
- **Python経路**：OpenAI Agents SDKでFunction Tool / MCPを実行し、OpenAI・Anthropic・Cerebrasの2〜3モデルを並列評価できます。
- **API不要の経路**：ローカルCLI、MCP診断CLI、Python・Nodeテストで動作を確認できます。

> 2026-09-30時点でPiの追加は[PR #1](https://github.com/koura718/agent-lab-pi/pull/1)の`feature/pi-cerebras-harness`ブランチにあります。以下の初回導入例は、このブランチを明示して取得します。`main`へのマージ前は、`main`に`setup-pi.sh`はありません。

## 実装済みの機能と現在の範囲

| 項目 | 現在の実装 |
|---|---|
| Pi | `@earendil-works/pi-coding-agent` **0.99.1**をpnpmワークスペース内に固定 |
| Cerebras接続 | 起動スクリプトでprovider=`cerebras`、model=`qwen-3.8-27b`、thinking=`off`を指定 |
| Pi拡張Tool | `compare_lists`を登録し、PythonのMCP診断CLIへ委譲 |
| Skill | `independent-checks`。独立した確認の並列化と、変動する情報の再確認を指示 |
| Python Tool | 同じ比較処理をFunction Tool / MCP Serverから利用 |
| Pythonモデル比較 | 選択した2〜3providerの同時実行、Tool結果検証、JSONレポート |
| 設定・ログ | Python側のCLI・環境変数・TOML設定、run_id・処理時間・エラー分類 |
| Tracing | Python側で明示的に有効化。PiのMCP診断経路では無効 |
| CI | Ubuntu 24.04でPython検証、Pi依存導入、Nodeテスト、JUnit保存 |

**トレーディングカード調査は設計段階です。** 楽天・Yahoo!・PSA等の接続、カード識別、価格取得、SQLite履歴、ブラウザ操作、Web確認の並列実行は未実装です。Skillは手順を示すもので、外部サービスへの接続や並列実行機構を追加するものではありません。

## 環境と依存管理

| 項目 | 固定値・用途 |
|---|---|
| OS | Ubuntu 24.04。Windowsネイティブ実行は未検証 |
| Node.js | 24.21.0。Pi・起動スクリプト・Nodeテスト |
| pnpm | 12.3.4。Node依存管理 |
| Python | 3.14.7。比較処理・MCP・Agents SDK・Pythonテスト |
| uv | 0.12.12。Python依存管理 |
| Pi | 0.99.1。対話型Agent |
| mise / Git | 事前導入が必要 |

ランタイムは[mise.toml](mise.toml)、Python依存は[uv.lock](uv.lock)、Node依存は[pnpm-lock.yaml](pnpm-lock.yaml)で管理します。Piの固定バージョンは[apps/pi-assistant/package.json](apps/pi-assistant/package.json)にあります。

ローカルGPUやDockerは不要です。モデル推論はCerebras APIで実行します。Codex・Claude Codeは開発支援に利用できますが、このアプリの起動に必須ではありません。セットアップスクリプトはGit・miseのOS導入やsudo操作を行いません。

## 初回セットアップ

### 1. リポジトリとPython基盤を準備

GitHubへのSSH接続とmiseが利用可能な状態で実行します。

```bash
git clone git@github.com:koura718/agent-lab-pi.git
cd agent-lab-pi

mise trust mise.toml
./scripts/bootstrap.sh --setup --check &&
./scripts/bootstrap.sh --setup
```

`mise trust`の前に`mise.toml`を確認してください。`--check`は前提条件の確認のみです。通常の`--setup`はツール導入、Python固定依存の同期、未作成の`.env`の作成、Python検証を行います。既存の`.env`は保持します。

**`bootstrap.sh`には必ず`--setup`を付けてください。** 引数なしはテンプレート名・Pythonパッケージ名を変更する別機能です。この派生版でもPythonパッケージは`agent_lab`、CLIは`agent-lab`のままです。

### 2. Piを追加

```bash
./scripts/setup-pi.sh
```

このスクリプトは次の処理を実行します。APIキーは不要ですが、初回の依存取得には通信が必要です。

1. `uv sync --frozen`でPython依存を同期。
2. `pnpm install --frozen-lockfile --ignore-scripts`でPi依存を同期。
3. `pnpm test:pi`でNodeテストを実行。

Piをグローバルにはインストールしません。詳細は[bootstrap手順](docs/bootstrap.md)と[Pi + Cerebras手順](docs/pi-cerebras.md)を参照してください。

### 3. Cerebrasキーを設定

[Cerebras Cloud](https://cloud.cerebras.ai/)で発行したキーを、既存の`.env`の`CEREBRAS_API_KEY=`へ設定します。値をGitやチャットへ貼り付けないでください。

```bash
chmod 600 .env
```

Pi起動にはCerebrasキーを使います。OpenAI・Anthropicのキーは、対応するPython版Agentを利用する場合に設定します。

## Piの起動と動作確認

```bash
mise exec -- pnpm pi
```

起動時に`AGENTS.md`、`independent-checks`、`extension.mjs`が読み込まれ、モデル欄に`qwen-3.8-27b`と`thinking off`が表示されます。

**入力欄は、画面下部の横線に囲まれた空白部分です。** 次の文章を入力し、Enterで送信してください。この操作はCerebrasの実APIを利用します。

```text
compare_lists ツールを使って source=["A","B","B"] と baseline=["B","C"] を比較してください。
```

期待するTool結果は次のとおりです。モデルが返す説明文は実行ごとに変わることがあります。

```json
{"same":["B"],"source_only":["A"],"baseline_only":["C"]}
```

Piの使用モデルは`/model`、推論設定は`/thinking`で確認できます。終了する際は入力を空にしてCtrl+Dを押し、通常のシェルプロンプトに戻ったことを確認します。

### PiからPython MCPまでの経路

Pi自身がCerebrasとの対話を管理します。PythonのAgents SDKをPiの内部で動かす構成ではありません。

| 順序 | 処理 |
|---|---|
| 1 | PiがCerebrasへ問い合わせ、モデルが`compare_lists`を選択 |
| 2 | `extension.mjs`がPi Toolとして呼び出される |
| 3 | `mcp-bridge.mjs`が`uv run --frozen agent-lab-mcp-client --no-tracing call compare_lists ...`を実行 |
| 4 | Python診断Clientがローカルのstdio MCP Serverを起動して呼び出す |
| 5 | Serverが共通ドメイン関数で比較し、結果がPi・モデルへ戻る |

現在は**Tool呼び出しごとに診断CLIとMCP Serverを起動する方式**です。Pi 0.99系のネイティブMCP接続やcodemodeを使う構成への移行は、この実装には含めていません。

ブリッジはシェルを介さず子プロセスを実行し、20秒のプロセスタイムアウトと64 KiBの出力バッファ上限を設定します。受け取ったJSONのフィールドと型を検証し、不正な結果や子プロセス失敗をToolエラーにします。この上限はPython側のTool入力上限とは別です。

### Piの設定・保存先

| 項目 | 実装上の扱い |
|---|---|
| 起動入口 | `scripts/run-pi.mjs` |
| 作業ディレクトリ | 呼び出し元にかかわらずリポジトリ直下 |
| Cerebrasキー | 非空の環境変数`CEREBRAS_API_KEY`を優先し、なければルート`.env`の該当行を読む |
| `.env`読み込み | シェルとして実行せず、Cerebrasキーの行だけを解析。Python版CLIとは扱いが異なる |
| Piへの環境変数 | 継承環境から`OPENAI_API_KEY`・`ANTHROPIC_API_KEY`を除外 |
| MCP診断CLIへの環境変数 | 上記2キーと`CEREBRAS_API_KEY`を除外し、Tracingを無効化 |
| Piの設定・セッション | `PI_CODING_AGENT_DIR`を`.local/pi/`に固定。Git管理外 |
| 追加引数 | `pnpm pi`に渡した引数をPi CLIへ転送 |

これは資格情報をすべて隔離するサンドボックスではありません。Piの標準ファイル・シェルToolはローカルユーザー権限で動作します。外部調査専用の読み取り制限は今後の設計対象です。

### Piの更新

Piを終了してから、現在の追跡ブランチを更新します。

```bash
git status --short --branch
git pull --ff-only
./scripts/setup-pi.sh
mise exec -- pnpm --dir apps/pi-assistant exec pi --version
mise exec -- pnpm pi
```

この版では`0.99.1`が表示されます。Pi画面に更新通知が出ても、リポジトリで管理する更新は`package.json`とロックファイルをセットで変更し、検証してから取り込みます。`.env`と`.local/pi/`は保持されます。

## API不要の比較とMCP診断

`compare_lists`は文字列配列を集合として比較し、重複を除いた`same`・`source_only`・`baseline_only`を返します。大小文字・空白・Unicode表記は区別し、各結果をPythonの文字列順でソートします。入力は各1,000要素以下、各文字列1〜256文字で、空配列は有効です。

```bash
# Python内のFunction Tool経路
mise exec -- uv run --frozen agent-lab --tool-mode function --no-tracing \
  --compare-json '{"source":["A","B","B"],"baseline":["B","C"]}'

# MCP Tool一覧
mise exec -- uv run --frozen agent-lab-mcp-client --no-tracing list-tools

# 実MCP子プロセス経由の比較
mise exec -- uv run --frozen agent-lab-mcp-client --no-tracing \
  call compare_lists --arguments '{"source":["A","B","B"],"baseline":["B","C"]}'
```

これらはモデルAPIを呼びません。診断ClientがServerを起動・終了します。Serverの単体入口は`agent-lab-mcp`ですが、stdioプロトコルの入力待ちになるため、手動確認には診断CLIを使ってください。

詳細：[Tool契約](docs/tool-contract.md)、[MCP Server](docs/mcp-server.md)、[MCP Client](docs/mcp-client.md)。

## Python版Agentと複数モデル比較

Python版のCLIは`.env`を自動では読みません。自分で管理する`.env`をサブシェルで読み込んで実行します。以下は実APIを利用します。

```bash
(
  set -a
  source .env
  set +a
  mise exec -- uv run --frozen agent-lab \
    --provider cerebras --model qwen-3.8-27b --tool-mode mcp --no-tracing \
    --prompt 'compare_listsを使いsource=["A","B","B"]とbaseline=["B","C"]を比較してください。'
)
```

`--tool-mode function`なら同一プロセスのToolを使用します。`agent-lab`の引数なし実行もモデルAPIを呼ぶため、API不要の確認には前節の明示コマンドを使ってください。

OpenAI・Anthropic・Cerebrasの同時比較例です。選択したすべてのproviderのキーが必要です。

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

モデル引数を2つだけ指定する比較も可能です。各AgentのTool結果、実行ID、所要時間、最終応答、失敗情報をJSONで返します。`--tool-mode mcp`なら各Agentが専用Serverを使います。全体の`status=success`と`results_match=true`を確認してください。

これは同じ比較タスクを複数モデルで評価する機能であり、外部Webサイトを並列に調べる機能とは別です。モデルIDは利用アカウントでアクセス可能なものを指定します。

詳細：[並列比較](docs/mixed-models.md)、[CerebrasのPython接続](docs/cerebras.md)、[Claude接続](docs/claude.md)。

## Python設定・ログ・Tracing

単一Agent / MCP診断CLIの設定優先順位は**CLI > 環境変数 > 明示したTOML > 既定値**です。`config/agent.toml`も自動では読みません。

| 主なCLI引数 | 環境変数 | 既定値 |
|---|---|---|
| `--provider` | `AGENT_PROVIDER` | `openai` |
| `--tool-mode` | `AGENT_TOOL_MODE` | `function` |
| `--model` | `AGENT_MODEL` | SDK既定 |
| `--max-turns` | `AGENT_MAX_TURNS` | 5 |
| `--run-timeout` | `AGENT_RUN_TIMEOUT_SECONDS` | 60秒 |
| `--connect-timeout` | `MCP_CONNECT_TIMEOUT_SECONDS` | 10秒 |
| `--call-timeout` | `MCP_CALL_TIMEOUT_SECONDS` | 10秒 |
| `--log-level` | `AGENT_LOG_LEVEL` | `INFO` |
| `--tracing / --no-tracing` | `AGENT_TRACING_ENABLED` | 無効 |

複数モデル比較CLIには別の引数・既定値があり、上表の`AGENT_MODEL`等を使いません。Piのprovider・model指定もこのPython設定とは独立です。

Pythonアプリのログはstderr、結果JSONはstdout、MCP Serverのstdoutはプロトコル専用です。UTC時刻・run_id・処理時間・エラー分類を記録し、入力配列・プロンプト・キーをアプリのイベントログへ出しません。

TracingはPython側で明示的に有効化します。Piのブリッジは`--no-tracing`を指定するため、この経路からAgents SDKのTraceは送信しません。Pythonのログ・Traceの本文除外ルールは、Pi自身のセッション保存には適用されません。

詳細：[設定例](config/agent.toml)、[Logging](docs/logging.md)、[Tracing](docs/tracing.md)、[運用手順](docs/runbook.md)。

## テストとCI

日常の確認はPythonとPiの両方を実行します。

```bash
./scripts/validate.sh
mise exec -- pnpm test:pi
git diff --check
```

| 確認 | 内容 |
|---|---|
| `validate.sh` | Ruff lint・format、pytest、compile、Git whitespace、`.env`除外、キーの基本チェック |
| `pnpm test:pi` | Tool登録、MCP診断CLIへの委譲・キー除外、不正レスポンス拒否の3件 |
| MCP診断CLI | 実際のローカルClient / Server通信。モデルAPI不要 |
| Pi対話による確認 | Cerebrasの実APIとTool往復を手動確認 |
| Python liveテスト | `--run-live`で明示実行する実LLMテスト。通常はスキップ |

`validate.sh`単体にはNodeテストは含まれません。通常テストはモデルAPIを呼びませんが、依存が未導入の場合はダウンロード通信が発生します。Nodeの3件は実Cerebras接続を検証するテストではありません。

2026-09-30までの確認結果：

- Python通常検証：**215 passed / 2 skipped**。skipは明示実行していないliveテスト。
- Pi拡張テスト：**3 passed**。
- Pi 0.99.1 + Cerebras `qwen-3.8-27b` + `compare_lists`：Ubuntu環境で利用者が実API・Tool往復の成功を確認。
- Pi 0.99.1更新コミットの[GitHub Actions](https://github.com/koura718/agent-lab-pi/actions/runs/36681493456)：成功。

Pi経路の成功は、Python Agents SDKのCerebras用liveテストや3モデル比較を実APIで検証したことを意味しません。これらの実行方法は[テスト手順](docs/testing.md)とprovider別文書を参照してください。

[CI](.github/workflows/validate.yml)は`main`向けPRと`main`へのpushで動作します。Ubuntu 24.04でPython bootstrapとPi依存導入・Nodeテストを実行し、Python JUnitを14日保存します。リポジトリのブランチ保護・テンプレート設定は、このworkflowとは別のGitHub設定です。

## ファイル構成

| パス | 役割 |
|---|---|
| `apps/pi-assistant/package.json` | Pi・TypeBoxの固定依存 |
| `apps/pi-assistant/extension.mjs` | Piの`compare_lists` Tool登録 |
| `apps/pi-assistant/mcp-bridge.mjs` | Python診断CLIの実行、結果検証、エラー処理 |
| `apps/pi-assistant/skills/independent-checks/SKILL.md` | 再利用する確認手順 |
| `apps/pi-assistant/test/` | Pi拡張・ブリッジのNodeテスト |
| `scripts/run-pi.mjs` | キー読み込み・Pi起動 |
| `scripts/setup-pi.sh` | 固定依存の同期・Nodeテスト |
| `package.json`・`pnpm-workspace.yaml`・`pnpm-lock.yaml` | Nodeワークスペース・コマンド・解決済み依存 |
| `src/agent_lab/domain/list_comparison.py` | SDK非依存の比較本体・入力検証 |
| `src/agent_lab/tools/`・`src/agent_lab/mcp/` | Function Tool・MCP Server / Client |
| `src/agent_lab/main.py`・`agent_factory.py` | Python CLI・Agent生成 |
| `src/agent_lab/model_comparison.py`・`model_provider.py` | provider接続・複数モデル評価 |
| `tests/` | Pythonの単体・統合・liveテスト |
| `scripts/setup.sh`・`bootstrap.sh`・`validate.sh` | Python基盤の導入・検証 |
| `.local/pi/` | Piの設定・セッション。Git管理外 |
| `reports/` | pytest XML等の出力。Git管理外 |
| `docs/` | 契約、設計、各実行経路の詳細手順 |

[AGENTS.md](AGENTS.md)・[CLAUDE.md](CLAUDE.md)を確認して開発してください。`docs/next-steps-3-6.md`等には元のPython基盤の実装履歴も含まれます。Piの入口はこのREADMEと[Pi手順](docs/pi-cerebras.md)を参照してください。

## 困ったとき

| 症状 | 確認・対応 |
|---|---|
| `setup-pi.sh: No such file or directory` | `git branch --show-current`を確認。マージ前は`git fetch origin`後、`git switch --track origin/feature/pi-cerebras-harness`。ローカルブランチが既にあれば`git switch feature/pi-cerebras-harness` |
| `Pi is not installed` | `./scripts/setup-pi.sh`を実行 |
| `CEREBRAS_API_KEY is missing` | ルート`.env`の該当行、または環境変数を確認 |
| `.env`を書き換えても別のキーが使われる | 環境変数が優先される。値を表示せず、必要ならシェルで`unset CEREBRAS_API_KEY`して再起動 |
| 入力欄が分からない | Pi画面下部の横線の間に入力。シェルプロンプトが見えている場合はPiを起動し直す |
| `Local MCP comparison failed` | 前述のAPI不要MCP診断CLIを実行し、Python環境・エラー分類・タイムアウトを確認 |
| 通常検証で`2 skipped` | liveテストを指定していない場合の正常動作 |
| 古いPiが起動する | グローバルの`pi`ではなく`mise exec -- pnpm pi`を使用し、固定依存を同期 |

`.env`と`.local/pi/`はGit管理外です。GitだけではAPIキーやPiの会話履歴はバックアップされません。秘密情報とセッションは必要に応じて別途保管してください。

## License

[MIT License](LICENSE)。Copyright (c) 2026 Masaaki Koura。依存ライブラリにはそれぞれのライセンスが適用されます。
