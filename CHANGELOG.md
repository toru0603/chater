# Changelog

## Unreleased

- ドキュメント追加: WebSocket API の詳細を docs/WEBSOCKET_API.md に追加
- README.md に WebSocket API セクションを追加
- architecture.md の Signaling 節を更新（ターゲット指定のシグナリング、participant 通知の説明を追加）
- CONTRIBUTING.md / PR_GUIDE.md を追加
- .github/PULL_REQUEST_TEMPLATE.md を追加

(注) 実装上のポイント:
- WebSocket エンドポイント: /ws/{room_code}
- メッセージ仕様: join / offer/answer/candidate (target 指定) / leave
- 最大参加者数は app.room_manager.MAX_PARTICIPANTS（デフォルト 10）
