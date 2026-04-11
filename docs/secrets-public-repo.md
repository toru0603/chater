# Public リポジトリ向けシークレット設計（要約）

## 前提
- リポジトリは公開 (public) であり、認証情報や長期的な鍵を GitHub に置かない制約がある。
- 目的は「CI/CD（CDK デプロイ）」「ランタイム機密（JWT・APIキー等）」を安全に扱うこと。

---

## 要件（満たすべき点）
1. GitHub 上に長期的な AWS 認証情報（アクセスキー / シークレット）は置かない。
2. デプロイ権限は最小化し、悪用されないようガードする。
3. ランタイム秘密は AWS 内の安全ストアに保管する（Secrets Manager / SSM）。
4. 自動デプロイは可能にするが、公開リポジトリに機密を置かない。

---

## 推奨アーキテクチャ（3案）

案A — AWS CodePipeline / CodeBuild を使う（推奨）
- 概要: GitHub (public) をソースに CodePipeline を構成。CodeBuild が CDK ビルド/デプロイを行う。
- 認証: CodeBuild のサービスロールにデプロイ権限を付与（IAM ロール）。GitHub 側にシークレットは不要（public repo はクローン可能）。
- 長所: デプロイ実行は完全に AWS 内で行われ、GitHub に機密を置かない。運用監査が容易。自動化に安定。
- 短所: CodePipeline のセットアップコスト、学習コスト。

案B — Self-hosted Runner（EC2/ECS/EKS）を使う
- 概要: 自社 AWS 上に GitHub Actions の self-hosted runner を立て、インスタンスプロファイル（EC2/EKSタスクロール）で AWS 権限を付与する。
- 認証: Runner 側の IAM ロールを通じてデプロイ。GitHub に秘密は不要。
- 長所: GitHub Actions の既存ワークフローを再利用可能。細かい実行環境制御が可能。
- 短所: ランナーの運用/セキュリティ（更新・スケール・隔離）負荷。

案C — GitHub OIDC を利用する（ただし「GitHubに何も置かない」要件と若干折衷）
- 概要: GitHub Actions から OIDC トークンで AWS ロールを Assume する。長期キーは不要。
- 実装の注意点: `aws-actions/configure-aws-credentials` は `role-to-assume` にロールARNを指定する必要がある（ARN自体は秘密ではないがワークフローに記載すると公開される）。
- 長所: 長期的資格情報を GitHub に置かない。標準的で容易。
- 短所: ロールARNをワークフローに置く/またはリポジトリシークレットに置く必要がある点で、完全に「GitHubに何も置かない」にはならない（ただしARNは機密でない）。

---

## ランタイムシークレットの配置（共通事項）
- JWT の署名鍵、サードパーティ API キーなどの機密は必ず AWS Secrets Manager（または SSM SecureString）に保存。
- CDK で Secret を作成・参照して Lambda に `secretsmanager:GetSecretValue` 権限のみ付与。
- Secrets Manager の自動ローテーションが可能なら有効化。

---

## 推奨（私の意見）
- Security-first: 案A（CodePipeline + CodeBuild）を推奨。パイプラインは AWS 内で完結するため公開リポジトリでも機密を一切 GitHub に置かずに自動デプロイが可能。
- CI 再利用性: 既に GitHub Actions を活用したい場合は案B（self-hosted runner）を検討。社内で runner を安全に運用できる体制があるなら有力。
- 簡便さ: 小チーム・短期なら案C を受け入れ（ARNは公開してもよいがポリシーで厳しく限定）、ただし厳密なポリシー要件がある場合は不可。

---

## 実装ステップ（案A: CodeBuild を選んだ場合の例）
1. AWS 側で CodePipeline と CodeBuild プロジェクトを作成。
2. CodeBuild のサービスロールに CloudFormation/CDK/必要なリソース権限を付与（最小権限で設計）。
3. Pipeline の Source を GitHub (public) に設定（webhook or polling）。
4. Buildspec に `npm ci && npm run build && npx cdk deploy --all --require-approval never` を記述。
5. Secrets Manager に JWT 等を保存、CDK で参照する。
6. 必要なら manual approval ステージを追加（production）。

---

## まとめ（短く）
- 公開リポジトリ条件なら「デプロイ実行を AWS 内で行う」設計（CodePipeline/CodeBuild）を第一選択とするのが最も安全。
- 代替は self-hosted runner（社内運用負荷あり）や OIDC（ARNの公開が許容される場合）。

---

次のステップ:
- 希望する案を選んでください（推奨: CodePipeline/CodeBuild）。選択を受けて実装設計（手順・IAM ポリシー草案・CDK 変更加工）を進めます。
