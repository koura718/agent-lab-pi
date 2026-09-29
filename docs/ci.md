# CI結果保存・障害対応・main保護（Step 7）

## 実行と保存

既存のValidate workflowがmain向けPRとmainへのpushで実行されます。
Ubuntu 24.04 / mise / uv.lockを使い、validate.shで検証します。
通常CIはAPI不要です。liveテスト2件はスキップし、API secretは追加しません。

validate.shは毎回 `reports/pytest.xml` を生成します。開始時に前回の同ファイルを
削除するため、lint失敗等でテストまで進まなかった場合に古い結果を残しません。
reportsはGit管理対象外です。テスト失敗の終了コードはそのままCI失敗になります。

| 出力 | 場所・保持 |
|---|---|
| テストごとの成功・失敗・skip | JUnit XML、reports/pytest.xml |
| CIのXML | Artifactsのpytest-results-RUN_ID-ATTEMPT、14日 |
| validation結果・XMLの有無 | Actions実行画面のSummary |
| lint・初期設定・テスト等の詳細 | Actionsの各stepログ（GitHub側の保持設定に従う） |

アップロードは成功・失敗どちらでも、XMLが存在する場合に実行します。
セットアップ失敗・強制終了等でXMLができなければArtifactはありません。
キャンセルやrunner喪失時には保存を保証できません。
アップロード対象はXML 1ファイルだけです。.envや作業ディレクトリ全体を保存しません。
JUnitの失敗詳細にはテスト入力等が含まれるため、通常テストにはダミーデータを使います。

## Ubuntuでの確認

```bash
mise exec -- uv sync --frozen
./scripts/validate.sh
ls -l reports/pytest.xml
git status --short
```

通常は110 passed, 2 skippedです。reportsはgit statusに現れません。

## CI失敗時の手順

1. PRのChecks、またはActionsのValidateを開く。
2. 最初に失敗したstepを確認する。XMLがない場合はセットアップやlintの失敗を先に確認する。
3. テスト失敗ならArtifactsからJUnit XMLをダウンロードする。
4. 同じコミット・uv.lockで対象テストを再現し、修正してpushする。
5. 通信障害等の一過性エラーのみ、原因を確認して再実行する。

GitHub CLIの場合（RUN_IDはrun listで確認した数値へ置換）:

```bash
gh run list --workflow validate.yml --limit 5
gh run view RUN_ID --log-failed
gh run download RUN_ID --dir reports/download-RUN_ID
```

再実行が必要な場合:

```bash
gh run rerun RUN_ID --failed
```

再実行回数をArtifact名に含めるため、同じrunの結果が衝突しません。

## main保護の確認結果

2026-09-27の読み取り確認:

- mainのcommit: 4be2515
- Branch API: protected=false、required_status_checksのcontextsは空
- repository rulesets一覧: []
- 詳細branch protection API: 403 Resource not accessible by integration

上記時点ではBranch APIはmainを保護対象と報告していません。
詳細取得の403そのものは「未設定」の証拠ではなく接続権限の制約です。
このPRは保護設定を変更しません。CI成功と、成功を必須にする設定は別です。

管理権限を持つGitHub CLIでの再確認（読み取りのみ）:

```bash
gh api repos/koura718/agent-lab/branches/main --jq '{protected: .protected, protection: .protection}'
gh api repos/koura718/agent-lab/branches/main/protection
gh api repos/koura718/agent-lab/rulesets
```

403は権限不足、404は未設定またはアクセス不可の可能性があります。
rulesetsが存在する場合は対象ブランチ・enforcement・bypassも確認してください。

## 保護設定の確認更新（2026-09-27 Step 9着手時）

所有者が設定したprotect-main（ID 24071453）の詳細を読み取り確認しました。
main対象、Active、bypassなし、PR必須・承認0、削除/force push禁止、
Validate repository（GitHub Actions integration_id=15368）必須、最新baseへの追従必須です。
上の未保護の記録はStep 7着手時点の履歴です。

## 推奨する保護設定（所有者が適用）

GitHubのSettings → Rules → Rulesetsでmain用Branch rulesetを作成する案です。
既存のルールがあれば重複追加せず内容を確認してください。

| 項目 | 推奨値 |
|---|---|
| 対象 | main |
| Enforcement | Active |
| Require a pull request before merging | 有効 |
| 必須status check | Validate repository（実際のCheck名を選択） |
| Require branches to be up to date | 有効 |
| Block force pushes | 有効 |
| Restrict deletions | 有効 |
| 必須承認人数 | 個人運用なら0。レビュー担当がいる場合に1以上 |
| Bypass | 必要性を確認し、常用する例外を作らない |

承認者がいない個人運用で他者の承認を必須にするとマージできなくなります。
merge queueは今回導入しません。現workflowはmerge_groupイベントに未対応です。
設定後は次のPRで必須check表示を確認し、成功前にマージできないことを確認します。

## チェックリスト

- [ ] Ubuntuでvalidate成功・JUnit XML生成
- [ ] PRのCI成功・Artifactを取得可能
- [ ] XML内のテスト数・skip数が期待どおり
- [ ] main保護の所有者確認・必要なら設定
- [ ] mainマージ後のvalidate成功

公式資料:
- https://github.com/actions/upload-artifact
- https://docs.github.com/en/rest/branches/branches
- https://docs.github.com/en/rest/branches/branch-protection
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
