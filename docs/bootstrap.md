# 環境構築の自動化（Step 10）

## これだけ覚えればOK

GitとmiseがあるUbuntu 24.04で、取得済みのリポジトリから実行します。
APIキーは不要です。パッケージのダウンロードにはネットワークが必要です。

```bash
./scripts/bootstrap.sh --setup --check
./scripts/bootstrap.sh --setup
```

`--setup`を必ず指定してください。引数なしの既存bootstrapは、ディレクトリ名を
使ってプロジェクト名・Pythonパッケージ名を変更する別機能です。
名前変更機能の再設計・再利用検証は今回の対象外です。
従来の `./scripts/setup.sh` も同じ環境構築を実行します。

## 新しいUbuntuへの導入

1. Git・miseを管理者の運用手順で導入し、PATHから実行できる状態にします。
   スクリプトはsudo、OSパッケージ導入、シェル設定変更を行いません。
2. リポジトリをcloneします。SSH認証済み環境の例です。

   ```bash
   git clone git@github.com:koura718/agent-lab.git
   cd agent-lab
   ```

3. `mise.toml`の内容を確認し、初回にmiseが信頼を求める場合は自身で許可します。
   非対話環境で必要な場合も、確認済みのファイルに対して実行します。

   ```bash
   mise trust mise.toml
   ./scripts/bootstrap.sh --setup --check
   ./scripts/bootstrap.sh --setup
   ```

既存環境でも同じコマンドを再実行できます。実行位置が別ディレクトリでも
スクリプト自身からリポジトリを解決します。Windowsネイティブは未対応です。

## 入力と処理順序

| 入力 | 用途 |
|---|---|
| mise.toml | Python・uv・Node・pnpmの固定バージョン |
| pyproject.toml / uv.lock | Python依存。lock欠落時は停止 |
| .env.example | 空のAPIキー欄を持つ設定雛形 |
| .gitignore | .envがGit管理対象外であることを確認 |

1. 必須ファイル・コマンド・.envの除外・雛形のキー欄を確認。
2. `mise install`でユーザーのmise管理領域にランタイムを導入。
3. `mise exec -- uv sync --frozen`でプロジェクトの`.venv`を同期。
4. 未作成の場合のみ`.env`を権限600で作成。既存ファイルは内容・権限を保持。
5. `validate.sh`でlint・format・通常テスト・compile・Git検証。

`.env`を読み込んだり、APIキーを入力させたり、Agentを実APIで起動したりしません。
`.env`のシンボリックリンク・ディレクトリは拒否します。
`PYTEST_ADDOPTS`を子プロセス内で解除し、通常検証へのlive指定混入を防ぎます。
Tracingも無効化します。CIは同じbootstrapを使い、JUnitを従来どおり保存します。

`--check`はインストール前の前提確認だけです。ランタイム導入済み・テスト成功を
意味しません。ファイル作成やmise実行は行いません。

## 出力と検証

- `.venv/`、未作成なら`.env`、`reports/pytest.xml`、各ツールのキャッシュ。
- setupログはUTC時刻・レベル付きstderr。下位コマンドは自身の出力形式。
- 成功0、不正オプション2、前提不備1。下位処理失敗はその終了コードを返します。
- エラー時は`stage=install/sync/environment/validation`等で失敗位置を表示。
- 通常テストではlive 2件をスキップ。API不要のCLI確認は次のとおりです。

```bash
mise exec -- uv run --frozen agent-lab --no-tracing \
  --compare-json '{"source":["A","B"],"baseline":["B","C"]}'
mise exec -- uv run --frozen agent-lab-mcp-client --no-tracing list-tools
```

比較結果は `same=["B"], source_only=["A"], baseline_only=["C"]` です。
実LLM検証は別途[テスト手順](testing.md)から明示的に実行します。

## 障害対応と受入条件

| 症状 | 対応 |
|---|---|
| git/miseなし | PATHと導入状況を確認後、--checkを再実行 |
| mise信頼エラー | 設定内容を確認してmise trust mise.toml |
| install/sync失敗 | 接続・プロキシ・空き容量を確認し同じコマンドを再実行 |
| uv.lockなし | Gitから復元。bootstrapはlockを新規生成しない |
| .env除外エラー | 追跡状態と.gitignoreを確認。キーをログへ貼らない |
| validation失敗 | 最初の失敗とreports/pytest.xmlを確認。CI手順も参照 |

途中失敗時に、導入済みツールや`.venv`を自動削除しません。原因を修正して再実行します。
既存`.env`が600以外なら警告し、必要に応じ自身で`chmod 600 .env`を実行します。

- [ ] 初回セットアップと再実行が成功
- [ ] 既存.envが保持され、Git差分に秘密情報がない
- [ ] API不要テスト成功、live 2件skip、JUnit生成
- [ ] 不正設定やインストール失敗で後続処理が停止

シェル制御のテストは隔離Gitリポジトリと偽miseで行い、ダウンロードを発生させません。
実mise経由の構築はUbuntu CIと利用環境で確認します。
