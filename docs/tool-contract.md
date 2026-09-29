# compare_lists — Step 3

## 概要

2つの文字列配列を集合として比較する、副作用のないFunction Toolです。
ファイル読書き・ネットワーク通信・DB更新は行いません。
通常のPython関数とAgents SDKアダプタを分離し、後続のMCP Serverからも
同じドメイン関数を再利用できる構成です。

## 入出力

入力はsourceとbaselineだけを持つJSONオブジェクトです。

```json
{"source":["A","B","B"],"baseline":["B","C"]}
```

成功結果:

```json
{"same":["B"],"source_only":["A"],"baseline_only":["C"]}
```

| 条件 | 契約 |
|---|---|
| 配列 | 両方必須、空配列可、各1,000要素以下 |
| 要素 | 文字列のみ、1〜256文字（Pythonのlen基準） |
| 重複 | 上限検証後に除去 |
| 並び順 | Python文字列の標準順序 |
| 大小文字・前後空白 | 保持して区別。空白のみの文字列も有効 |
| Unicode | 正規化しない |
| 不正型 | 数値・bool・null・文字列以外を拒否。自動変換しない |
| JSON | 不明なキー・重複キー・NaN/Infinityを拒否 |

失敗結果は成功結果とは別形式です。

```json
{"error":{"code":"INVALID_INPUT","message":"Provide exactly source and baseline fields."}}
```

入力値やスタックトレースをエラーメッセージへ含めません。
ドメイン関数の入力不正はComparisonInputError、アダプタでは上記JSONに変換します。
予期しない内部例外は成功結果へ変換せず、実行を失敗させます。

## 実装境界

| ファイル | 責務 |
|---|---|
| domain/list_comparison.py | SDK非依存の検証・比較・結果型 |
| tools/list_tools.py | JSON検証、FunctionTool、エラー変換、最小ログ |
| agent_factory.py | 新しいAgentとToolを生成。import時にAgentを生成しない |
| main.py | CLI、API不要の比較、任意の実モデル実行 |

FunctionToolを直接生成し、JSON Schemaを明示しています。
型変換や不明なキーの扱いをSDKデコレータのデフォルトに依存させず、
同じ制約定数をschemaと実行時検証で共有します。
schemaと入力境界、Runner経由での結果受渡しをテストします。

## テスト

```bash
uv run --frozen pytest -v
```

通常テストではAPIキーを除去し、socket接続・名前解決を禁止します。
トレースはHTTP exporterを登録しないproviderで無効化します。
SDK 0.22.2のScriptedModelで、Tool要求→実Tool実行→結果受渡し→最終応答を確認します。
これは決定的なローカル検証で、実モデルが適切にToolを選ぶかの評価ではありません。
Step 4のMCP Serverとローカル統合テストは実装済みです。[MCP契約](mcp-server.md)を参照してください。
Agent側MCP接続とliveテストは後続工程です。
