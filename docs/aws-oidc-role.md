# GitHub Actions OIDC IAM Role (for CDK deploy)

目的
- GitHub Actions の OIDC を使って安全に AWS へ CDK デプロイするための IAM ロール作成手順とサンプルポリシー。

注意
- ここでは手順の簡便さのために管理ポリシー(AdministratorAccess)を例示します。運用前に最小権限へ絞ることを強く推奨します。

1) OIDC プロバイダーの登録（必要なら）

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

2) 信頼ポリシー（trust policy）の例

ファイル: `trust-policy.json`（`{ACCOUNT_ID}` を実環境の AWS アカウントID に置換）

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::{ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:toru0603/chater:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

- 上記 `sub` 条件は main ブランチからのみアサンプトを許可します。複数ブランチや環境を許可する場合は `repo:OWNER/REPO:*` や `repo:OWNER/REPO:environment:ENV_NAME` を使用できます。

3) ロール作成例（簡易）

```bash
aws iam create-role --role-name GitHubActionsCDKDeployRole \
  --assume-role-policy-document file://trust-policy.json

# 初期は管理ポリシーを付与（簡便/運用後に見直す）
aws iam attach-role-policy --role-name GitHubActionsCDKDeployRole \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

4) ロール ARN を GitHub に登録（リポジトリシークレット）

- シークレット名: `AWS_DEPLOY_ROLE_ARN` 値: `arn:aws:iam::{ACCOUNT_ID}:role/GitHubActionsCDKDeployRole`
- シークレット名: `AWS_REGION` 値: `us-east-1`（デプロイ先リージョン）

GitHub CLI 例:

```bash
gh secret set AWS_DEPLOY_ROLE_ARN --body "arn:aws:iam::${ACCOUNT_ID}:role/GitHubActionsCDKDeployRole"
gh secret set AWS_REGION --body "us-east-1"
```

5) CDK Bootstrap 実行
- GitHub の Actions タブから `CDK Bootstrap` ワークフローを手動実行（workflow_dispatch）。
- または CLI で実行: `gh workflow run cdk-bootstrap.yml --ref main`

6) PR マージおよび自動デプロイ
- シークレット登録と bootstrap が完了したら PR #31 をマージすると `.github/workflows/deploy-cdk.yml` が自動でデプロイを実行します。

7) 最小権限化の指針
- 運用段階では AdministratorAccess を外し、下記権限を許可する最小ポリシーを検討してください（例）:
  - cloudformation:*, s3:*, iam:CreateRole, iam:PassRole, lambda:*, apigateway:*, dynamodb:*, logs:*, kms:*, ecr:*, events:*
- 可能ならアカウント内の特定リソースにスコープしてください。

---

質問があればこのファイルで指示ください。追加で最小権限ポリシーの草案も作成できます。