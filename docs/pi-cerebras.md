# Pi + Cerebras on Ubuntu 24.04

## 目的と構成

Cerebrasの[記事](https://www.cerebras.ai/blog/the-rise-of-slow-personal-assistants)は、Piを小さなエージェント基盤にし、Cerebras上のQwen 3.8 27Bによる速い推論、独立した調査の並列化、手順の再利用を組み合わせています。予約を22秒で完了したという数値は記事の特定条件の記録であり、このリポジトリの性能目標や再現結果ではありません。

この実装ではPiの標準CLIとCerebrasモデルを使い、Piの拡張Toolから既存の`agent-lab`のPython製MCP診断CLIを呼びます。診断CLIはローカルMCPサーバーを起動します。PythonのAgent・Function Tool・比較テストはそのまま使えます。

| 要素 | 役割 |
|---|---|
| `mise.toml`、`uv.lock` | Ubuntu向けNode/Python環境とPython依存の固定 |
| `pnpm-lock.yaml`、`apps/pi-assistant/` | Pi 0.87.1とNode依存の固定 |
| `scripts/run-pi.mjs` | Cerebras/Qwenを選択し、`.env`からキーを読む起動入口 |
| `apps/pi-assistant/extension.mjs` | `compare_lists`をPiのToolとして登録 |
| `apps/pi-assistant/mcp-bridge.mjs` | モデルキーを渡さずPythonのMCP診断CLIを実行 |
| `apps/pi-assistant/skills/independent-checks/` | 独立した読み取り処理と生データ再確認の指針 |

Piの作業ディレクトリはリポジトリ直下です。既存の`AGENTS.md`、ソース、テストを読めます。Piのセッションと設定はGit管理外の`.local/pi/`に保存します。Piと拡張機能はローカルユーザー権限で動作します。MCP診断CLIはPiとは別プロセスで走ります。

## 導入

Ubuntu 24.04でGit、miseを準備し、リポジトリを取得します。`mise.toml`を確認してから信頼してください。

```bash
git clone git@github.com:koura718/agent-lab-pi.git
cd agent-lab-pi
mise trust mise.toml
./scripts/bootstrap.sh --setup --check
./scripts/bootstrap.sh --setup
./scripts/setup-pi.sh
```

`bootstrap.sh`には必ず`--setup`を付けます。引数なしはテンプレート名の変更処理です。`setup-pi.sh`は`uv.lock`と`pnpm-lock.yaml`から依存を同期し、キー不要のNodeテストを実行します。Piはシステム全体にはインストールしません。セットアップ後の更新では`mise exec -- pnpm install --frozen-lockfile --ignore-scripts`を使います。

[Cerebras Cloud](https://cloud.cerebras.ai/)で発行したAPIキーを、Git管理外の`.env`の`CEREBRAS_API_KEY=`に入れます。既存のOpenAI/AnthropicキーはPi起動時に渡しません。`.env`を共有したりコミットしたりしないでください。

```bash
chmod 600 .env
mise exec -- pnpm pi
```

環境変数`CEREBRAS_API_KEY`があれば`.env`より優先します。起動コマンドは`cerebras/qwen-3.8-27b`と`--thinking off`を明示します。PiのUIで`/model`、`/thinking`を確認できます。実際のモデル利用可能状況と料金はCerebrasのアカウントで確認してください。

## APIを使わない確認

```bash
mise exec -- pnpm test:pi
mise exec -- uv run --frozen agent-lab-mcp-client --no-tracing list-tools
mise exec -- uv run --frozen agent-lab-mcp-client --no-tracing call compare_lists \
  --arguments '{"source":["A","B","B"],"baseline":["B","C"]}'
```

最後のコマンドは`same=["B"]`、`source_only=["A"]`、`baseline_only=["C"]`を返します。Pi内では`compare_lists`を使い、同じ配列を比較するよう依頼できます。Piからのモデル呼び出しは実API利用となるため、キーと課金枠が必要です。

## 記事との対応と拡張

| 記事の要素 | この環境 | 次に追加するもの |
|---|---|---|
| 高速な推論 | Cerebras/Qwen 3.8 27BをPiで選択 | 自分のAPI環境で速度と費用を測定 |
| 独立した確認の並列化 | `independent-checks` skillが調査の手順を示す | 対象サービス向け読み取り専用ツールや並列実行コード |
| サイト手順の再利用 | 手順をskillとして追加できる構成 | 実際のサイト操作手順を検証して記述 |
| 外部サービスへの操作 | 未接続 | ブラウザ/API認証、取消し・確認フロー |

今回の構成だけで予約や購入はできません。サイト固有のツールと認証情報を追加し、現在の空席・料金などを毎回取得した上で、外部への確定操作前に内容をユーザーに提示します。`compare_lists`は最初のMCP動作確認用です。

Piの[CLI](https://pi.dev/docs/latest/cli)、[拡張機能](https://pi.dev/docs/latest/extensions)、[モデルカタログ](https://pi.dev/models/cerebras/qwen-3-8-27b)を参照してください。
