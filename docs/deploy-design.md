# デプロイ設計（概要）

## 目的
このリポジトリを AWS にデプロイし、データを DynamoDB に保存、API を AWS Lambda（HTTP API）で提供する。IaC は AWS CDK（TypeScript）、CI/CD は GitHub Actions（OIDC）で自動デプロイを行う。

## 前提・非機能要件
- スモール〜ミディアム規模のトラフィックを想定（初期はオンデマンド設定）
- 可用性・スケーラビリティ（Lambda + DynamoDB）、監視・アラート、最小権限のセキュリティ
- 認証は Cognito または外部 JWT を想定（実装時に決定）

## 高レベル構成
- API Gateway (REST API) ←→ Lambda (Node.js 18.x, NodejsFunction bundling)
- Lambda ←→ DynamoDB 単一テーブル設計（PK/SK）
- CloudWatch Logs / Metrics / Alarms、必要に応じて X-Ray
- CI: GitHub Actions (OIDC) → CDK deploy

## DynamoDB設計（推奨）
- テーブル名: `app-table-{env}`
- 主キー: PK (S), SK (S)
  - PK: `USER#<userId>` や `ITEM#<id>` など
  - SK: `METADATA` や `ORDER#<ts>` など
- GSI はアクセスパターンに応じて追加
- Billing: PAY_PER_REQUEST（初期）
- Point-in-time recovery: 有効
- Encryption: AWS-managed KMS
- TTL / Streams: 必要に応じて有効化

## Lambda / API設計
- Runtime: Node.js 18.x
- ハンドラ: 機能ごとに分割 or 単一エントリ（初期は単一ハンドラで簡潔に）
- メモリ / タイムアウト: 256–512MB / 10–30s（要調整）
- 環境変数: TABLE_NAME, その他設定。機密は SecretsManager または SSM を利用
- IAM: テーブルへの最小権限のみ付与
- API: REST API（現実装）、将来的に HTTP API へ移行検討
- 認証: Cognito JWT あるいは外部 JWT（要追加設計）

## CI/CD（GitHub Actions + CDK）
- ワークフロー: push→build/test→cdk synth→cdk deploy (mainへマージ後自動デプロイ)
- 認証: GitHub OIDC + IAM Role（リポジトリ secrets に Role ARN と Region を設定）
- CDK bootstrap: 環境ごとに bootstrap を実行

## ロギング・モニタリング
- CloudWatch Logs: Lambda ログ（JSON 構造推奨）
- CloudWatch Alarm: エラー率、レイテンシ、スロットル等
- Tracing: X-Ray（必要時）

## 運用
- DynamoDB: PITR を有効化
- バックアップ: 定期バックアップ・エクスポート検討
- コスト: DynamoDB の GSI と読み書きパターンを監査

## 開発・テスト
- DynamoDB Local（Docker）でのローカル開発
- Jest 等でユニットテスト、統合テスト
- CDK: `cdk synth` を CI で実行

## 実装アウトプット（予定ファイル）
- infra/cdk/
  - bin/app.ts
  - lib/dynamo-stack.ts
  - lib/api-stack.ts
  - src/handlers/api.ts
  - package.json, tsconfig.json, cdk.json
- .github/workflows/deploy-cdk.yml
- docs/deploy-design.md（このファイル）

## 次のステップ（自動実行方針）
1. この設計で問題ないか確認（必要時、追加の決定事項を提示）
2. CDK TypeScript プロジェクト骨子を作成し、Lambda ハンドラ雛形を実装
3. GitHub Actions で OIDC を使った自動デプロイを追加
4. dev 環境へデプロイして動作確認

---

（備考）この設計は最小実装を想定しています。運用要件や認証方式、ドメイン/証明書、監視の詳細などは実運用の要件に応じて追加設計します。