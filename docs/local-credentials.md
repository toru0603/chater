# ローカル認証情報の取り扱い（設計）

目的
- 公開リポジトリ環境で、認証情報を GitHub に置かずにデプロイを行うための手順と注意点をまとめる。

要点（短く）
- 推奨: OS の秘密ストアを使う（aws-vault / AWS SSO）。ファイルを使う場合はプロジェクト専用ファイルにし、厳密に .gitignore とファイル権限で保護する。
- 自動化（CI）を行う場合は、公開リポジトリでは GitHub にシークレットを置かない代替（CodeBuild/CodePipeline、または self-hosted runner + instance profile）を検討する。

1) ユースケース
- 開発者のローカルから手動で CDK デプロイを行う。\n
- （代替）自社管理のランナー（self-hosted）で同じファイルを使う場合。\n
2) 推奨パターン
- 最も安全: aws-vault / AWS SSO を使い、機密は OS キーチェーンまたは SSO のセッションで管理する。
- 最小限ファイル方式: プロジェクト内に専用ファイルを置く（例: `infra/aws-credentials`）を用い、絶対にコミットしない。\n
3) ファイル方式の手順（具体例）

(1) IAM 側の準備
- 推奨設計: 長期アクセスキーを直接使わせず、ローカルの "deploy user" に `sts:AssumeRole` のみを許可し、実際のデプロイは限定的権限の `DeployRole` を Assume して行う。
- ただし小規模で簡便にするなら deploy 用 IAM ユーザーを作り、キーを発行してローカルに保存する。運用上は代替案（AssumeRole / MFA / aws-vault）を強く推奨。

(2) プロジェクト専用認証ファイル作成

例: `infra/aws-credentials`

```
[chater-deploy]
aws_access_key_id = AKIA...YOUR_KEY...
aws_secret_access_key = yourSecretHere
# aws_session_token = ...  # 必要なら
```

操作:
```
# ファイル作成（エディタで安全に貼り付け）
chmod 600 infra/aws-credentials
# Git に絶対に含めない
echo "/infra/aws-credentials" >> .gitignore
```

(3) CDK / AWS CLI から使う

- 環境変数で明示的に指す方法:
```
export AWS_SHARED_CREDENTIALS_FILE=$(pwd)/infra/aws-credentials
export AWS_PROFILE=chater-deploy
cd infra/cdk
npx cdk deploy --profile chater-deploy --all --require-approval never
```

- または AWS_PROFILE のみ指定（デフォルトの credentials ファイルを使う場合）:
```
aws configure --profile chater-deploy
npx cdk deploy --profile chater-deploy
```

(4) 一時的な AssumeRole を使う（推奨フロー）

ローカルの弱いキーで `sts:AssumeRole` を行い、短期セッショントークンでデプロイする方法。例:
```
creds=$(aws sts assume-role --role-arn arn:aws:iam::123456789012:role/ChaterDeployRole --role-session-name chater-deploy --profile chater-deploy)
export AWS_ACCESS_KEY_ID=$(echo "$creds" | jq -r .Credentials.AccessKeyId)
export AWS_SECRET_ACCESS_KEY=$(echo "$creds" | jq -r .Credentials.SecretAccessKey)
export AWS_SESSION_TOKEN=$(echo "$creds" | jq -r .Credentials.SessionToken)
# その後 cdk deploy を実行
npx cdk deploy --all --require-approval never
```

※ `jq` が必要。簡単にするなら aws-vault を使う。

4) aws-vault 利用（推奨）

- aws-vault は OS キーチェーンでアクセスキーを安全に保持し、コマンド実行時に一時的な環境変数を注入するツール。
- 例:
```
aws-vault add chater-deploy       # 一度だけ入力
aws-vault exec chater-deploy -- npx cdk deploy --all --require-approval never
```

5) Self-hosted runner で利用する場合
- 可能なら EC2/ECS タスク の Instance Profile / Task Role を使い、認証情報ファイルを配置しない構成を推奨。
- やむを得ずファイルを置く場合は、ランナーが稼働する専用 VPC/アカウントで運用・監視を行い、ファイル権限とマシンのアクセス制御を厳格にする。

6) 権限設計（簡易サンプル）

- Local user (最小): `sts:AssumeRole` のみ許可

```json
{
  "Version":"2012-10-17",
  "Statement":[
    {"Effect":"Allow","Action":"sts:AssumeRole","Resource":"arn:aws:iam::123456789012:role/ChaterDeployRole"}
  ]
}
```

- DeployRole（CDK デプロイ用、例）:

```json
{
  "Version":"2012-10-17",
  "Statement":[
    {"Effect":"Allow","Action":["cloudformation:*","s3:*","lambda:*","apigateway:*","dynamodb:*","iam:CreateRole","iam:PassRole","iam:AttachRolePolicy","logs:*","events:*"],"Resource":"*"}
  ]
}
```

注意: CDK は CloudFormation と IAM の操作を行うため、厳密な最小権限化は難しい。まずは限定的リソースにスコープするか、運用チームでのレビューを必須にしてください。

7) セキュリティ対策
- ファイルに保存する場合は `chmod 600` を必須にする。\n- .gitignore に必ず追加し、誤ってコミットされた場合は即時にキーを無効化してローテーションする。\n- pre-commit フック（git-secrets や detect-aws-credentials）を導入してコミット前に検出する。\n- 定期的なキー回転、MFA を推奨。

8) 運用フロー（推奨）
- 開発者は aws-vault/SSO で短期トークンを取得して作業。
- 本番デプロイは承認フローを踏んだうえで、DeployRole を用いて短期トークンで実行。
- Self-hosted runner を使う場合はインスタンスプロファイル優先。

---

必要であれば、このドキュメントをベースに「デプロイ用 IAM ポリシー草案」「pre-commit 設定」「aws-vault の導入手順（OS別）」を作成します。どれを先に作りますか？
