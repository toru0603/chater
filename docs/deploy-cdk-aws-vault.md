# CDKデプロイ手順 — aws-vault (passバックエンド, WSL向け)

概要

このドキュメントは、WSL上でaws-vaultのpass+GPGバックエンドを使い、ローカルから安全にCDK（infra/cdk）をブートストラップおよびデプロイする手順をまとめたものです。実行前に必ず内容を確認してください。

前提

- WSL (Ubuntu 等) 環境
- Node.js (推奨: 18.x または 20.x) と npm
- git, npx が利用可能
- AWSアカウントと、長期アクセスキー（またはroleの利用元となる資格情報）
- このリポジトリの main ブランチが最新であること

重要: 認証情報はリポジトリに含めないでください。aws-vault(pass)はローカルの暗号化ストアに保存します。

1. WSL に必要なツールを入れる

推奨: 付属スクリプトを実行します（sudo が必要）

  bash scripts/install-pass-gpg.sh

このスクリプトは gnupg2, pass, pinentry-curses をインストールし、gpg-agent の pinentry 設定を行います。

2. GPG鍵の用意

既に GPG 秘密鍵があれば次へ。無ければ生成します:

  gpg --full-generate-key

対話で RSA, 4096, 有効期限（任意）、パスフレーズを設定してください。

実行時に pinentry を正しく動かすため、ターミナルで以下を設定しておくと安全です:

  export GPG_TTY=$(tty)

3. pass の初期化

下記スクリプトで初期化します。実行後、利用する GPG キーID（または指紋）を入力してください:

  ./scripts/setup-aws-vault-pass.sh

手動でも可能:

  pass init <GPG_KEY_ID>

4. aws-vault に AWS 資格情報を登録

バックエンドを pass にして aws-vault に追加します:

  export AWS_VAULT_BACKEND=pass
  ./scripts/aws-vault.sh add chater-deploy

プロンプトで Access Key ID と Secret Access Key を入力します。

(役割を跨ぐ設定にする場合は ~/.aws/config に role_arn と source_profile を設定し、source_profile を aws-vault に登録してください。)

5. 動作確認

登録後、以下で動作確認:

  export AWS_VAULT_BACKEND=pass
  ./scripts/aws-vault.sh exec chater-deploy -- aws sts get-caller-identity --output text

期待値: AWS アカウントID が返る。

6. CDK のブートストラップとデプロイ

デプロイスクリプトを使います。デフォルトプロファイル名は `chater-deploy` です。

  export AWS_VAULT_BACKEND=pass
  export AWS_REGION=ap-northeast-1   # 必要に応じて変更
  ./scripts/deploy-cdk-with-aws-vault.sh chater-deploy

スクリプトの処理:
- infra/cdk で npm ci（依存解決）
- aws sts get-caller-identity で資格情報検証
- cdk bootstrap aws://<ACCOUNT>/<REGION>
- cdk deploy --all

ログを保存するには:

  ./scripts/deploy-cdk-with-aws-vault.sh chater-deploy 2>&1 | tee deploy.log

7. トラブルシュート（よくある問題）

- aws-vault: "Specified keyring backend not available"
  -> `export AWS_VAULT_BACKEND=pass` を指定しているか確認。

- GPG / pinentry が動かない / パスフレーズが入力できない
  -> `export GPG_TTY=$(tty)` を実行してから操作。pinentry-curses をインストール済みか確認。

- pass init エラー
  -> 正しい GPG 鍵IDを指定しているか。`gpg --list-secret-keys --keyid-format LONG` で確認。

- aws sts get-caller-identity が失敗する（認証エラー）
  -> `./scripts/aws-vault.sh add` で登録したプロファイル名と AWS_VAULT_BACKEND が一致しているか、またはキーが有効か確認。

- cdk bootstrap / deploy 中の AccessDenied
  -> 使用している IAM ユーザー/ロールに十分な権限がない可能性。開発段階では一時的に AdministratorAccess を付与して動作確認すると手早い（本番では最小権限にすること）。

8. 必要な IAM 権限（概観）

CDK ブートストラップとデプロイには以下クラスの権限が必要です（詳細は CDK ドキュメント参照）:
- cloudformation: Create/Update/Delete/DescribeStacks 等
- s3: CreateBucket, PutObject, GetObject, DeleteObject
- iam: CreateRole, PassRole, AttachRolePolicy, CreatePolicy
- sts: GetCallerIdentity, AssumeRole
- lambda: CreateFunction, UpdateFunction
- ecr: CreateRepository, PutImage（もしコンテナ資産がある場合）

迅速な検証のためは AdministratorAccess を使って構築→後で権限を絞る運用が一般的です。

9. クリーンアップ

デプロイしたスタックを削除するには:

  export AWS_VAULT_BACKEND=pass
  ./scripts/aws-vault.sh exec chater-deploy -- npx cdk destroy --all

CDK のブートストラップで作成された S3 バケットやロールは手動で削除が必要な場合があります（空にしてから削除）。

10. セキュリティ注意

- 長期アクセスキーを公開リポジトリに置かないこと。
- pass（GPG）による保護はローカルのみ。GPG 秘密鍵のバックアップとパスフレーズ管理は厳重に。
- CI でのデプロイを検討する場合、公開リポジトリでは GitHub OIDC か AWS 側のCodePipeline を検討（本リポジトリ用のドキュメントあり: docs/aws-oidc-role.md）。

参考

- docs/DEPLOY.md（デプロイ手順のメインガイド）
- docs/aws-vault-pass-wsl.md
- scripts/install-pass-gpg.sh
- scripts/setup-aws-vault-pass.sh
- scripts/deploy-cdk-with-aws-vault.sh
- infra/cdk/

