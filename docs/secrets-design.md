# シークレット設計

## 目的
本ドキュメントは、GitHub Actions と AWS（CDK/Lambda/DynamoDB）を安全に連携させるために必要なシークレット情報と保存場所、運用ルールを定義します。用途別にどこに保管し、ワークフローでどう参照するかを明確化します。

---

## 原則
- 秘密情報はコードに直接書かない。必ずシークレットストアに保存する。
- CI（GitHub Actions）には OIDC を使って AWS ロールをアサインし、長期的なアクセスキーをリポジトリに置かない。
- ランタイム（Lambda）が必要とする機密値は AWS Secrets Manager / SSM (SecureString) に保存し、IAM ロールでアクセスさせる。
- 環境（dev/stage/prod）は分離し、必要なら環境ごとに別のシークレットを持つ。
- 最小権限の原則を徹底する（ロール/ポリシー/シークレットのアクセス制御）。

---

## 保管場所の分類
- GitHub リポジトリシークレット（repo secrets）
  - CI 用の短期的/設定値（例: OIDC 用の Role ARN、デプロイ先リージョン等）
  - 例: `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`

- GitHub Environments のシークレット（環境ごとのシークレット）
  - 本番/ステージングなど、手動承認や保護が必要な環境用。アクセスにレビュー/承認を要求できる。
  - 例: 本番用の `AWS_DEPLOY_ROLE_ARN` を `production` 環境のシークレットとして登録

- GitHub Organization secrets
  - 複数リポジトリで共有するシークレットを格納（必要な場合）

- AWS Secrets Manager / SSM (SecureString)
  - ランタイムシークレット（API キー、OAuth シークレット、JWT シークレット など）
  - Lambda から直接読み取る。CDK で Secret を作成/参照して、関数に読み取り権限を付与する。

- その他（必要に応じて）
  - Vault 等の外部シークレット管理サービス。会社ポリシーに従う。

---

## 必要なシークレット（最小セット）
以下は本プロジェクト固有に想定されるシークレットと保存場所の推奨。命名は大文字スネークケース（例: `AWS_DEPLOY_ROLE_ARN`）で統一。

1. CI / デプロイ関連（GitHub シークレット）
   - `AWS_DEPLOY_ROLE_ARN` (必須)
     - 値: arn:aws:iam::123456789012:role/GitHubActionsCDKDeployRole
     - 用途: GitHub Actions から OIDC を使って AssumeRole し、CDK デプロイ/ブートストラップを実行する
     - 保存先: リポジトリシークレット、もしくは環境ごとに `production` 等の Environment secret
   - `AWS_REGION` (必須)
     - 値例: `us-east-1`
     - 用途: CDK デプロイ時のリージョン
     - 保存先: リポジトリシークレット
   - `AWS_ACCOUNT_ID` (任意)
     - 値: `123456789012`
     - 用途: ドキュメントや一部スクリプトで利用

2. ランタイム / アプリケーション（AWS Secrets Manager 推奨）
   - `app/jwt-secret` (Secrets Manager)
     - 用途: JWT の署名鍵（Lambda が取得して認証処理に利用）
   - `thirdparty/some-service-api-key` (Secrets Manager)
     - 用途: サードパーティ API キー
   - Cognito の Client Secret（必要な場合）は Secrets Manager に保管

3. 監査 / 通知（任意）
   - `SENTRY_DSN` / `ROLLBAR_TOKEN` などは Secrets Manager（または環境シークレット）へ保存

---

## 環境ごとの管理（推奨パターン）
- GitHub Environments を使用して `dev`, `staging`, `production` を作成する。
  - 各 Environment に対して必要なシークレットを登録（例: 本番の `AWS_DEPLOY_ROLE_ARN` は production 環境シークレットに登録）
  - Environments の保護ルールで manual approval を設定すれば、本番デプロイに人の承認を必須にできる
- ワークフロー側では job に `environment: production` を指定して、その環境のシークレットを利用する

---

## ワークフローでの利用例
GitHub Actions での CDK デプロイ時の例:

```yaml
- name: Configure AWS Credentials (OIDC)
  uses: aws-actions/configure-aws-credentials@v3
  with:
    role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
    aws-region: ${{ secrets.AWS_REGION }}

- name: CDK Deploy
  run: |
    cd infra/cdk
    npx cdk deploy --all --require-approval never
```

Environment を使う場合（job level）:

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production   # production 環境に登録されたシークレットを使用
    steps: ...
```

---

## Lambda（ランタイム）でのシークレットアクセス例（CDK）
CDK で Secrets Manager のシークレットを作成し、Lambda に参照権限を付与する例:

```ts
import * as secrets from 'aws-cdk-lib/aws-secretsmanager';
const secret = new secrets.Secret(this, 'JwtSecret', { secretName: 'app/jwt-secret' });
// Lambda 関数を作成した後に
secret.grantRead(lambdaFunction);
```

Lambda ハンドラ内では SDK で Secrets Manager を呼んで値を取得する（キャッシュ推奨）。

---

## 命名規約（例）
- GitHub シークレット: `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION` など
- Environment シークレット（環境ごと同名）: `AWS_DEPLOY_ROLE_ARN`（production 環境に登録）
- AWS Secrets Manager: `/app/{env}/<purpose>` 例: `/app/prod/jwt-secret` または `app/jwt-secret`（運用規約に合わせる）

---

## ローテーション・更新ポリシー
- AWS Secrets Manager で管理しているシークレットは自動ローテーションを可能な場合は有効化（Lambda を使ったローテーションなど）
- GitHub シークレットは自動ローテーション不可（手動更新）。更新手順をドキュメント化する。
- OIDC 用の IAM ロールは短命のキーを含まないため、ロールの置き換えによってローテーションを行う（ロール ARN 自体は通常変わらない）。

---

## アクセス管理と監査
- Secrets Manager のアクセスは IAM で最小権限化。Lambda 実行ロールに `secretsmanager:GetSecretValue` のみ許可。
- GitHub Environments の `protection rules` を使い、本番デプロイにレビュー/承認を要求する。
- シークレット変更や CDK デプロイイベントは CloudTrail/CloudWatch で監査。

---

## セキュリティ運用手順（漏洩時）
1. 該当シークレットを即座にローテーションまたは無効化（Secrets Manager の場合は新しいバージョンを作成し自動ローテーションを開始）
2. GitHub シークレットの場合は更新（`gh secret set`）し、ワークフローの再実行で確認
3. 影響範囲の特定・ログ確認・必要に応じてクラウドプロバイダのアクセスキーを無効化
4. 事後レビューと再発防止（スキャン導入、Pre-commit フック、権限見直し）

---

## 実務チェックリスト（短期）
- [ ] GitHub リポジトリに `AWS_DEPLOY_ROLE_ARN` と `AWS_REGION` を登録
- [ ] (任意) Environments `production` を作成し production 用 `AWS_DEPLOY_ROLE_ARN` を登録
- [ ] AWS 上に OIDC-trusted ロールを作成して Role ARN を登録
- [ ] Secrets Manager にアプリケーション用のシークレットを作成し、CDK で参照可能にする
- [ ] CI ワークフローで OIDC ロールを使ったデプロイをテスト

---

## 参考コマンド
- GitHub にシークレットを設定（CLI）

```bash
# リポジトリシークレット
gh secret set AWS_DEPLOY_ROLE_ARN --body "arn:aws:iam::${ACCOUNT_ID}:role/GitHubActionsCDKDeployRole" --repo OWNER/REPO
gh secret set AWS_REGION --body "us-east-1" --repo OWNER/REPO

# Environment シークレット（production 環境に登録）
gh secret set AWS_DEPLOY_ROLE_ARN --env production --body "arn:aws:iam::${ACCOUNT_ID}:role/GitHubActionsCDKDeployRole" --repo OWNER/REPO
```

- Secrets Manager にシークレットを作成

```bash
aws secretsmanager create-secret --name "/app/prod/jwt-secret" --secret-string "$(generate-secret)"
```

---

## 補足
- 可能な限り OIDC を使い、長期的な AWS キーを GitHub に置かない。既に置いてある場合は速やかに廃止してロールへ切り替える。
- 会社ポリシーやセキュリティチームの要件があれば、本ドキュメントを基に最小権限ポリシーを作成します。

---

作業して欲しい場合: シークレットの登録を代行するか、登録後に自動でブートストラップ→PR マージ→デプロイを実行します。どちらを希望しますか？
