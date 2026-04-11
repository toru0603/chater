# 機能一覧

このドキュメントは cheter の主要な機能を一覧化したものです。

- 待ち受け番号によるマッチング
  - ユーザは任意の「待ち受け番号」を入力し、同じ番号の参加者と接続します。
- WebSocket シグナリング（/ws/{room_code})
  - サインaling メッセージ: `join`, `offer`/`answer`/`candidate`, `leave`, `chat`, `camera`, `audio` など
- WebRTC による P2P 映像・音声の送受信
- テキストチャット（弾幕表示）
- 参加者ごとの表示色割当
- ホスト/参加者ロール（最初に入室した参加者が `host`）
- 最大参加者数の制限（app.room_manager.MAX_PARTICIPANTS）
- ルーム管理（RoomManager: プロセス内メモリで保持）
- フロントエンド: Jinja2 テンプレートと static/app.js（UI: 参加/退出、カメラ/マイク、メッセージ送信など）
- テスト: ユニットテスト、E2E（Playwright）
- CI: Lint / Type check / Unit / E2E 等の必須ステータスチェック（マージ前に通すこと）
- ドキュメント: README、docs/WEBSOCKET_API.md、docs/USAGE.md、docs/DEVELOPMENT_RULES.md など

参考: 各機能の実装は app/ 以下や docs/ の該当ファイルを参照してください。
