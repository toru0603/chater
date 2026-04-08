# Changelog

## Unreleased

- CI: Unit Tests と E2E Tests (Playwright) を分割。CI で Playwright ブラウザをインストールし、失敗時に trace とスクリーンショットをアップロードするように変更
- 修正: Playwright E2E の安定化（RTCPeerConnection/getUserMedia のスタブ導入、タイムアウト延長、DOM ベースの待機へ変更）
- Infra: ブランチ保護で必須ステータスチェック（Unit Tests、E2E Tests (Playwright)、Copilot Suggestions (auto-apply)）を設定。delete_branch_on_merge と allow_auto_merge を有効化
- Copilot: Copilot の PR 提案を仕様に反しない限り自動適用するポリシーと自動適用ワークフロー／スクリプトを追加（.github/COPILOT_POLICY.md、.github/workflows/copilot-auto-apply.yml、.github/scripts/apply_copilot_suggestions.py）。自動適用できない提案は PR に通知
- ドキュメント: docs/WEBSOCKET_API.md を整備、README に color フィールドの説明を追記
- その他: .github/PULL_REQUEST_TEMPLATE.md、CONTRIBUTING.md / PR_GUIDE.md を追加

(注) 実装上のポイント:
- WebSocket エンドポイント: /ws/{room_code}
- メッセージ仕様: join / offer/answer/candidate (target 指定) / leave
- 最大参加者数は app.room_manager.MAX_PARTICIPANTS（デフォルト 10）
