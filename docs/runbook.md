# Function Tool / MCP 運用手順

Step 4のServerと統合テストについては[MCP Server手順](mcp-server.md)を参照してください。

Step 5の診断CLI・Agent接続・設定は[MCP Client手順](mcp-client.md)を参照してください。

## 前提

基準環境はUbuntu 24.04、ランタイムはmise.toml、依存はuv.lockを正とします。
リポジトリのルートで実行してください。Python >=3.14が必要です。
Windowsネイティブは未検証です。setup.sh / validate.shはBash用です。

```bash
mise exec -- uv sync --frozen
./scripts/validate.sh
```

## API不要の比較

```bash
mise exec -- uv run --frozen python -m agent_lab.main \
  --compare-json '{"source":["A","B","B"],"baseline":["B","C"]}'
```

標準出力:

```json
{"same":["B"],"source_only":["A"],"baseline_only":["C"]}
```

console scriptも同じ処理です。

```bash
mise exec -- uv run --frozen agent-lab \
  --compare-json '{"source":["猫"],"baseline":[]}'
```

入力ファイルは不要です。JSONをCLI引数として渡します。
大規模配列を渡す用途ではなく、シェルの引数長上限も適用されます。
秘密値を引数に入れるとシェル履歴等に残るため、検証用データを使ってください。

## 実モデルからのTool Calling（任意・API課金あり）

.envは自動で読み込みません。自分で管理する.envをBashから読み込みます。
モデル名は--model > AGENT_MODEL > 明示したTOML > SDK既定値です。

```bash
(
  set -a
  source .env
  set +a
  mise exec -- uv run --frozen agent-lab --tool-mode function \
    --prompt 'compare_listsを使い、source=["A","B","B"]、baseline=["B","C"]を比較してください。'
)
```

引数なしのpython -m agent_lab.mainも、従来のAPI接続確認プロンプトを実行します。
agent-labもこの入口に統一したため、従来の挨拶表示から実モデル実行に変わります。
APIキー未設定は終了コード2です。API不要の確認には必ず--compare-jsonを指定します。
既定値は最大5ターン、全体60秒です。Step 5でTOML・CLIによる設定とMCPモードを追加しました。
tracingは既定で無効です。明示有効化は[Tracing手順](tracing.md)を参照してください。liveテストの明示ゲートは実装済みです。[テスト運用手順](testing.md)を参照してください。

## 出力・ログ・終了コード

- stdout: オフライン比較はJSON、実モデル実行は最終応答。
- stderr: 時刻付きINFO / WARNING / ERROR。Python標準のWARNINGが設計上のWARNに対応します。
- 入力配列・キーはログへ出しません。比較結果そのものはstdoutへ出力します。

| コード | 意味 |
|---|---|
| 0 | 正常完了 |
| 1 | 実モデル実行失敗・timeout等 |
| 2 | CLI引数・比較入力不正・APIキー未設定 |
| 130 | 実モデル実行中のユーザー中断 |

## 検証・障害時対応

```bash
mise exec -- uv run --frozen pytest -v
mise exec -- uv run --frozen ruff check .
mise exec -- uv run --frozen ruff format --check .
```

| 症状 | 対応 |
|---|---|
| INVALID_INPUT | 必須2キー、型、空文字、件数・文字数上限を確認 |
| moduleがない / 古いCLI動作 | 対象ブランチを確認しuv sync --frozenを実行 |
| APIキー未設定 | .envを読んだshellで実行。API不要なら--compare-json |
| モデル/APIエラー | モデル利用権限・認証・接続を確認。キーは共有しない |
| timeout / ターン上限 | 入力と依頼を簡潔にして再実行。無限再試行しない |
| MCPモードで--compare-jsonが拒否される | API不要のMCP確認にはagent-lab-mcp-clientを使用 |

- [ ] 通常テスト成功
- [ ] API不要の比較が期待JSONを返す
- [ ] 不正入力がerrorを返し、終了コード2
- [ ] validate成功、git diff --check成功

問題時はPRの変更をrevertしてuv sync --frozenで同期します。
データ移行はありません。依存変更を含むPRではpyproject.tomlとuv.lockを一緒に戻してください。

## これだけ覚えればOK

比較確認は--compare-json、品質確認はvalidate.sh。
--promptと引数なし実行は実APIを呼びます。
