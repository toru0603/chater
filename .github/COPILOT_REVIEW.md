# Copilot Review Policy

このリポジトリでは、Pull Request をマージする際に以下をルールとします。

- CI（Unit Tests と E2E Tests (Playwright)）が成功していること。
- GitHub Copilot の PR レビュー提案（利用可能な場合）を考慮し、仕様に反しない限り自動で適用します。自動適用は .github/workflows/copilot-auto-apply.yml によって実行されます。
- 自動適用できなかった提案や曖昧な提案は PR にコメントで通知され、手動で対応してください。
- 必要に応じて人間のレビュワーが最終判断を行い、PR の承認・修正を行います。

このポリシーはリポジトリのルールです。自動適用ワークフローは安全策として、GitHub Actions が最後に行ったコミットを検出して無限ループを回避します。変更が自動で適用された場合は PR のコミット履歴とコメントで記録されます。
