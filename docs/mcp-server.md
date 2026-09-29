# Step 4 — MCP stdio Server

## 概要

既存compare_listsをMCP SDK 2.2.0のServerから公開します。
Serverは別プロセスで動作し、モデルやAPIキーを必要としません。
stdio専用で、HTTPポートを開いたり外部APIへ接続したりしません。
AgentからのMCP接続と汎用Client CLIはStep 5で追加します。

| 構成 | 責務 |
|---|---|
| domain/list_comparison.py | 共通の比較・入力検証・入力schema |
| tools/list_tools.py | 既存Function ToolのJSON境界 |
| mcp/server.py | MCPの一覧・呼出し・stdioライフサイクル |
| tests/integration/test_mcp_stdio.py | 実SDK Clientと実子プロセスによる検証 |

MCP ServerはAgents SDKをimportしません。入力schemaはFunction Toolと共通です。
mcpを直接依存として宣言し、uv.lockに反映しています。
旧FastMCPサンプルではなく、固定SDKのServer(on_list_tools=..., on_call_tool=...)を使います。

## 起動

```bash
mise exec -- uv sync --frozen
mise exec -- uv run --frozen python -m agent_lab.mcp.server
```

同等のconsole script:

```bash
mise exec -- uv run --frozen agent-lab-mcp
```

直接起動するとstdinからのMCPメッセージ待ちになります。待機は正常です。
通常はClientが子プロセスとして起動し、stdinを閉じて終了させます。
端末から中断する場合はCtrl+C。ServerがEOFで正常終了すると終了コード0、
起動・通信処理の致命的エラーは1、キーボード中断は130です。

stdoutはMCP通信専用、時刻付きINFO / WARNING / ERRORログはstderrです。
.envは自動読込みしません。compare_listsの入力値や秘密値をログに出しません。
入出力はUTF-8で、ファイル読書きは行いません。

## 公開Tool

名前はcompare_listsだけです。readOnly / idempotentを示すannotationを付けています。
必須引数はsourceとbaseline。各配列1,000件以内、文字列1〜256文字です。
重複除去・ソート・大小文字・空白・Unicodeの扱いは[共通契約](tool-contract.md)に従います。

入力例:

```json
{"source":["A","B","B"],"baseline":["B","C"]}
```

MCP成功結果はisError=false、structuredContentに次を格納します。
contentにも同じ値のJSONテキストを入れます。

```json
{"same":["B"],"source_only":["A"],"baseline_only":["C"]}
```

| 失敗 | MCP上の表現 |
|---|---|
| 引数の型・件数・文字数・必須/不明キー違反 | isError=true、content内にINVALID_INPUT |
| 予期しない比較処理の失敗 | isError=true、content内にINTERNAL_ERROR。詳細を返さない |
| 未知Tool / 無効cursor | MCPプロトコルエラー -32602 |

エラー結果には成功用structuredContentを入れません。
JSON-RPCの構文・初期化・プロトコル交渉はSDKに任せます。
Function ToolのJSON文字列デコーダと異なり、MCPはSDKが復号した引数オブジェクトを受け取ります。

## API不要の機能テスト

```bash
mise exec -- uv run --frozen pytest -m integration -v
```

実Serverをsys.executableと固定module名で起動し、以下を検証します。

- SDK自動交渉とlegacyモードで接続し、Tool一覧とschemaを確認
- 正常・空配列・重複・日本語・境界値でFunction経路と同値
- 不正型・不明キー・上限違反をエラーとして返却
- 未知Tool後も次の正常リクエストが成功
- stderrログを有効にした状態で通信が成立
- 日本語・空白を含むcwdから起動
- 実際の子プロセスを追跡し、EOF後の終了コード0を確認
- Client側例外・キャンセル後も子プロセスが終了
- SDKの子プロセス環境にダミー秘密変数とAPIキーが渡らない

各通信は5秒、正常系全体20秒、異常終了系全体15秒のテスト上限です。
これらはハング検出用の上限であり、性能保証ではありません。
SDKのstdio Clientが環境変数を許可リスト方式で継承し、終了時の待機・強制停止を管理します。
これはStep 4の検証用Clientです。任意Server向けの設定・再接続はStep 5の対象です。

全体検証:

```bash
./scripts/validate.sh
```

既存のpytest呼出しでローカル統合テストも実行されます。実LLM APIは呼びません。
HTTP送信やToolを選ぶモデルの振る舞いは検証対象外です。

## 障害時対応と完了確認

| 症状 | 確認 |
|---|---|
| module / commandがない | 正しいブランチでuv sync --frozen |
| 起動後応答がない | 単体起動は入力待ち。pytest -m integrationで疎通確認 |
| JSON-RPC解析エラー | stdoutにprintやバナーを追加していないか |
| INVALID_INPUT | source / baselineの型・上限を確認 |
| 接続timeout | stderr・Python実行パス・SDKバージョンを確認 |

- [ ] 通常テストとローカル統合テストが成功
- [ ] stderrに開始/完了/停止ログ、stdoutへのログ混入なし
- [ ] 既存Function Toolの結果が変わらない
- [ ] 子プロセスが終了し、端末へ戻る

問題時は対象PRをrevertし、pyproject.tomlとuv.lockを一緒に戻して同期します。
データ移行はありません。stdioによるプロセス分離はOS権限を制限するsandboxではありません。

## これだけ覚えればOK

Serverを手で起動して待つより、pytest -m integrationで一覧・比較・終了まで確認できます。
この検証はAPIキー不要、課金なしです。
