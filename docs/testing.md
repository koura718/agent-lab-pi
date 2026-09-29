# テスト運用手順（Step 6）

## 概要・前提

Ubuntu 24.04、Python 3.14.7、mise / uv.lockを使用します。
Step 3〜5で追加した検証を土台に、Function / MCP経路一致、Server異常終了、
実LLMテストの明示ゲートを追加しました。製品の比較処理は変更していません。

入力CSV等は不要です。テストデータはコード内の固定値と一時ファイルのみです。
APIキー・モデル設定はlive時だけ必要です。.envは自動読込みしません。

| 区分 | 対象 | API通信・課金 | 通常CI |
|---|---|---|---|
| unit / smoke | 比較・schema・設定・CLI・ゲート | なし | 実行 |
| integration | 実Server・stdio・ScriptedModel・終了処理 | なし | 実行 |
| live | 実モデル → Function / MCP Tool | あり | スキップ |

## 通常の確認

```bash
mise exec -- uv sync --frozen
./scripts/validate.sh
mise exec -- uv run --frozen pytest -m integration -v
```

通常のpytestはunit / integrationを実行し、live 2件をスキップします。
モデルAPIキーと設定環境変数をテストごとに除去し、親テストプロセスのsocket接続・名前解決を禁止します。
tracing exporterも無効化します。MCPはローカル子プロセスとのstdio通信です。
子プロセスはSDKの環境allowlistで起動します。
このネットワーク禁止fixtureはOSのサンドボックスではなく、任意の子プロセスの通信を強制遮断するものではありません。

区分別に実行する場合:

```bash
mise exec -- uv run --frozen pytest -m 'not integration and not live' -v
mise exec -- uv run --frozen pytest -m integration -v
mise exec -- uv run --frozen pytest -m live -v
```

最後のコマンドはliveを選択しますが、--run-liveがないため実行せずスキップします。
markerの誤記は--strict-markersでエラーにします。

## 受入条件

| ケース | 検証する内容 |
|---|---|
| 正常・空・重複・日本語・Unicode・空白 | Function / MCP結果が一致 |
| 要素数・文字数の上限 | 境界値の成功と超過の拒否 |
| 型不正・空文字・必須欠落・未知項目 | 成功結果にせず両経路で拒否 |
| ScriptedModel + 両経路 | Tool結果が次のモデル呼出しへ渡る |
| Tool一覧・schema・未知Tool | 既存Server契約を維持 |
| Server異常終了 | 実際のTool呼出し後に終了コード23、有限時間でClient失敗 |
| 接続・呼出し・全体timeout / キャンセル | 既存Step 5の回収テストが成功 |
| live未指定、ダミーキーあり | API不要のゲートテストでスキップを確認 |
| live明示、キーまたはモデル不足 | テスト開始前に設定エラー |
| live明示、ダミー設定あり | ネットワークを使わないprobeだけ実行し、ゲート解除を確認 |
| live明示時の通常テスト | 通信禁止とキー除去を維持 |

異常系Serverはtests/fixtures配下のテスト専用コードです。
ゲート検証はpytesterで隔離したpytestプロセスを起動し、実LLMを一切呼びません。

## 実モデル検証（任意・API課金あり）

通常検証が成功してから、利用可能なモデルを明示して実行します。
次のMODEL_IDを利用する実際のモデルIDに置き換えてください。

```bash
(
  set -a
  source .env
  set +a
  export AGENT_MODEL='MODEL_ID'
  mise exec -- uv run --frozen pytest -m live --run-live -v
)
```

--run-live、選択providerのAPIキー、AGENT_MODELを要求します。
AGENT_PROVIDERはopenai（既定）またはanthropicです。後者ではANTHROPIC_API_KEYを確認します。
[Claude検証手順](claude.md)を参照してください。
キーやモデルが不足した明示実行は終了コード4です。自動skipにはしません。
tests/live配下はmarkerの付け忘れがあってもliveに分類します。
API呼出しは必ずテスト関数内に置き、モジュールimport時には実行しないでください。

Function / MCPの2件を実行します。各実行は最大3ターン・全体60秒です。
接続終了には回収時間が加わり、SDKの内部API再試行が発生する場合もあります。
課金額の上限を保証する設定ではありません。

最終文章の完全一致ではなく、compare_listsが実際に呼ばれた証拠と
Tool出力の `same=["B"] / source_only=["A"] / baseline_only=["C"]` を検証します。
Tool未使用、契約違反、認証/API/timeoutエラーは失敗です。tracingはliveでも無効です。

## CIと障害対応

既存validate.yml → validate.sh → pytestの入口を再利用します。
Step 7でJUnit XMLのArtifact保存と実行サマリーを追加しました。API secretやlive workflowは追加しません。
詳細は[CI運用手順](ci.md)を参照してください。

| 症状 | 対応 |
|---|---|
| 通常実行でlive 2件がskipped | 正常。API通信を行わないため |
| --run-live requires | OPENAI_API_KEY / AGENT_MODELを実行シェルで確認。値は共有しない |
| live認証・モデルエラー | キーの権限とモデルIDを確認 |
| integrationがtimeout | 対象テストを-vで再実行し、stderrと子プロセス終了状況を確認 |
| marker不明 | integration / liveの綴りを確認 |

テスト結果は成功・失敗・skip件数と実行秒数をpytestが出力します。
カバレッジ率は今回測定していません。通常テスト成功は実LLMの動作確認を意味しません。

- [ ] 通常テストで失敗ゼロ、live 2件がスキップ
- [ ] integration全件成功
- [ ] lint / format / compileall / whitespaceチェック成功
- [ ] mainマージ後にUbuntuでvalidateを再実行

## これだけ覚えればOK

通常は `./scripts/validate.sh`。実APIを使う場合だけ、キーとモデルを設定して
`pytest -m live --run-live -v` を実行します。
