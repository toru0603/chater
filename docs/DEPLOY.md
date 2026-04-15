# デプロイガイド

chater を AWS へデプロイする手順です。インフラは AWS CDK（TypeScript）で管理しており、`scripts/deploy-cdk-with-aws-vault.sh` を使って一発デプロイできます。

## 構成

| スタック | 内容 |
|---|---|
| `ChaterApiStack` | REST API（API Gateway + Lambda）、DynamoDB ユーザーテーブル |
| `ChaterWebSocketStack` | WebSocket API（API Gateway + Lambda） |

デプロイ後のエンドポイント例:

- REST API: `https://<id>.execute-api.ap-northeast-1.amazonaws.com/<stage>/`
- WebSocket: `wss://<id>.execute-api.ap-northeast-1.amazonaws.com/<stage>`

---

## 前提条件

| ツール | 確認コマンド | 備考 |
|---|---|---|
| Node.js 18 or 20 | `node --version` | CDK の実行に必要 |
| Python 3.11+ | `python3 --version` | Lambda バンドルに必要 |
| AWS CDK CLI | `npx cdk --version` | `infra/cdk` に同梱 |
| aws-vault | `./scripts/aws-vault.sh version` | `tools/bin/aws-vault` を同梱 |
| GPG + pass | `gpg --version && pass version` | 認証情報の暗号化に使用 |

WSL 環境でのセットアップは [docs/aws-vault-pass-wsl.md](aws-vault-pass-wsl.md) を参照してください。

---

## 初回セットアップ（一度だけ）

### 1. ツールのインストール（WSL / Ubuntu）

```bash
bash scripts/install-pass-gpg.sh
```

GPG キーの生成（まだなければ）:

```bash
gpg --full-generate-key
# RSA 4096 ビット、パスフレーズを設定
```

### 2. pass の初期化

```bash
./scripts/setup-aws-vault-pass.sh
# GPG キーID を入力（gpg --list-secret-keys で確認）
```

### 3. AWS 認証情報の登録

```bash
export AWS_VAULT_BACKEND=pass
./scripts/aws-vault.sh add chater-deploy
# Access Key ID と Secret Access Key を入力
```

必要な IAM 権限:
- CloudFormation (Create/Update/Delete)
- Lambda (CreateFunction, UpdateFunctionCode)
- API Gateway
- DynamoDB (CreateTable)
- IAM (CreateRole, PassRole)
- S3 (CDK アセット用)

> 初回検証には `AdministratorAccess` が便利です。本番運用では最小権限に絞ることを推奨します。

---

## デプロイ手順

### 通常デプロイ（main ブランチ推奨）

```bash
# main を最新に
git checkout main && git pull origin main

# デプロイ実行（第2引数でステージを指定できます、デフォルトは prod）
# 例: dev ステージへデプロイする場合
# AWS_VAULT_BACKEND=pass ./scripts/deploy-cdk-with-aws-vault.sh chater-deploy dev
AWS_VAULT_BACKEND=pass ./scripts/deploy-cdk-with-aws-vault.sh chater-deploy [stage]
```

スクリプトが行うこと:
1. `infra/cdk` で `npm ci`
2. `aws sts get-caller-identity` で認証確認
3. `cdk bootstrap aws://<account>/<region>`
4. `cdk deploy ChaterApiStack`
5. `cdk deploy --all`（全スタック）

ログをファイルに保存したい場合:

```bash
AWS_VAULT_BACKEND=pass ./scripts/deploy-cdk-with-aws-vault.sh chater-deploy 2>&1 | tee deploy.log
```

### リージョン変更

```bash
AWS_VAULT_BACKEND=pass AWS_REGION=us-east-1 ./scripts/deploy-cdk-with-aws-vault.sh chater-deploy
```

---

## デプロイ後の確認

### エンドポイントの取得

デプロイ完了時の出力（Outputs）に URL が表示されます:

```
ChaterApiStack.ApiUrl = https://<id>.execute-api.ap-northeast-1.amazonaws.com/<stage>/
ChaterWebSocketStack.WsUrl = wss://<id>.execute-api.ap-northeast-1.amazonaws.com/<stage>
```

### 動作確認

```bash
# ログイン画面が返れば OK（307 → 200）
curl -I https://<api-url>/<stage>/
curl -I https://<api-url>/<stage>/login
```

### ユーザーの確認

初回デプロイ時、Lambda 起動時に DynamoDB の `ChaterUsers` テーブルへデフォルトユーザーが自動登録されます。

| 項目 | 値 |
|---|---|
| ユーザーID | `toru` |
| パスワード | `jejeje` |

> **本番環境では必ずパスワードを変更してください。** DynamoDB コンソールまたは AWS CLI から `ChaterUsers` テーブルを直接更新できます。

---

## スタックの削除（クリーンアップ）

```bash
export AWS_VAULT_BACKEND=pass
./scripts/aws-vault.sh exec chater-deploy -- \
  bash -c 'cd infra/cdk && npx cdk destroy --all --force'
```

> CDK ブートストラップで作成された S3 バケット（`cdk-hnb659fds-assets-*`）は手動で空にしてから削除してください。

---

## トラブルシュート

### GPG パスフレーズが入力できない

```bash
export GPG_TTY=$(tty)
```

`~/.gnupg/gpg-agent.conf` に `pinentry-program /usr/bin/pinentry-curses` が設定されているか確認。

### aws-vault: credentials missing

```bash
export AWS_VAULT_BACKEND=pass
./scripts/aws-vault.sh list  # プロファイル一覧を確認
./scripts/aws-vault.sh exec chater-deploy -- aws sts get-caller-identity
```

### cdk bootstrap / deploy で AccessDenied

使用している IAM ユーザー／ロールの権限を確認してください。CDK ブートストラップには `sts:AssumeRole` と `cloudformation:*` が最低限必要です。

### DynamoDB テーブルが既に存在する

CDK の `RemovalPolicy.RETAIN` により、テーブルは削除しても再作成しません。`ChaterUsers` テーブルが残っている場合はそのまま利用されます。

---

## 関連ドキュメント

- [aws-vault + pass セットアップ（WSL向け詳細）](deploy-cdk-aws-vault.md)
- [AWS OIDC ロール設定](aws-oidc-role.md)
- [インフラ設計](../architecture.md)
