# aws-vault 設定・運用ガイド

目的
- ローカルの安全な AWS 認証情報管理と、CDK を使った安全な手動デプロイ運用を実現する。

概要
- aws-vault はローカルで AWS の長期的なアクセスキーを OS のキーチェーン（macOS Keychain, Windows Credential Manager, Linux libsecret/pass）に安全に格納し、実行時に短期セッショントークンを発行してコマンドを実行するツールです。
- これにより長期キーをファイルや環境変数に常時保存するリスクを避けられます。

推奨ワークフロー（ローカル手動デプロイ）
1. aws-vault をインストールする（下記参照）
2. ローカルに「デプロイ用の IAM ユーザー」または `assume-role` 用の最小権限ユーザーのキーを登録する
   - 推奨: long-lived key を直接使わず、`assume-role` 方式を採用（ローカルで AssumeRole して短期トークンでデプロイ）
3. aws-vault に資格情報を追加
   - `aws-vault add chater-deploy` を実行し、アクセスキー/シークレットを入力
4. デプロイ実行
   - `aws-vault exec chater-deploy -- npx cdk deploy --all --profile chater-deploy --require-approval never`
   - または、明示的に profile を使う場合: `AWS_PROFILE=chater-deploy aws-vault exec chater-deploy -- npx cdk deploy ...`

インストール方法（OS 別）
- macOS (Homebrew 推奨):
  - `brew install --cask aws-vault` または `brew install aws-vault`（環境に依存）
- Linux (推奨: 公式リリースをダウンロード):
  - 付属スクリプト `scripts/install-aws-vault.sh` を使う: `bash scripts/install-aws-vault.sh`
  - あるいは手動で: `curl -L -o ~/bin/aws-vault https://github.com/99designs/aws-vault/releases/latest/download/aws-vault-linux-amd64 && chmod +x ~/bin/aws-vault`
- Windows (Chocolatey):
  - `choco install aws-vault`

aws-vault の基本コマンド
- `aws-vault add <profile>`: 新しい credential を追加（キーを対話的に入力）
- `aws-vault list`: 登録済み credential の一覧
- `aws-vault exec <profile> -- <cmd>`: 指定 profile の短期的セッションでコマンドを実行
- `aws-vault remove <profile>`: 削除

MFA / AssumeRole の例
- MFA を有効にしたい場合、aws-vault は対話的に MFA トークンを要求できます。
- AssumeRole を使う場合の例（ローカルキーで DeployRole を Assume）:
  ```bash
  creds=$(aws-vault exec chater-deploy -- aws sts assume-role --role-arn arn:aws:iam::123456789012:role/ChaterDeployRole --role-session-name chater)
  # env の注入は aws-vault exec の中で直接行う方が安全
  aws-vault exec chater-deploy -- npx cdk deploy --all --require-approval never
  ```

安全上の注意
- 絶対にアクセスキーをリポジトリにコミットしない。`.gitignore` に追加しても、誤コミットが発生した場合は即時キーの無効化とローテーションが必要。
- aws-vault は OS のシークレットストアに依存する。チームの OS ポリシーに合わせて選択する。

CDK との統合（例）
- 例: `aws-vault exec chater-deploy -- npx cdk deploy --all --require-approval never`
- 推奨: 事前に `cdk bootstrap` を実行して、環境を整えておく。

トラブルシューティング
- Linux で `libsecret` バックエンドが必要な場合がある（`apt install libsecret-1-dev` など）。
- `aws-vault --version` で確認。`aws-vault exec` 実行後に `env | grep AWS` で短期トークンが注入されることを確認。

参考
- https://github.com/99designs/aws-vault

---

このファイルを基に、インストール手順（OS別詳細）、IAM ポリシー草案、MFA 運用手順を追加できます。