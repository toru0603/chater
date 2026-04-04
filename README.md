# cheter

cheter はブラウザで動作するシンプルな動画チャットアプリです。
ユーザは「待ち受け番号」でマッチングし、WebRTC を使って音声・映像をやり取りします。

## 特徴

- 待ち受け番号によるシンプルなマッチング
- WebSocket ベースのシグナリング（FastAPI）
- Jinja2 テンプレートと静的ファイルを使用

## クイックスタート（開発）

前提: Python 3.10+ がインストールされていること

1. 仮想環境を作成して有効化

   python -m venv .venv
   source .venv/bin/activate

2. 依存パッケージをインストール

   pip install -r requirements.txt

   （テストを実行する場合は pytest もインストール: pip install pytest）

3. 開発サーバを起動

   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

4. ブラウザで http://localhost:8000 を開く

## テスト

pytest -q

## プロジェクト構成（概要）

- app/: FastAPI アプリ本体（app.main にエントリポイント）
- static/: 静的ファイル
- templates/: Jinja2 テンプレート
- architecture.md: システム構成図と説明
- tests/: テストコード

## 貢献

小さな改善やバグ修正の PR を歓迎します。ドキュメントやテストがあるとマージが早くなります。

## WebSocket API

### エンドポイント

- ws://<host>/ws/{room_code}  （例: ws://localhost:8000/ws/room123）

### クライアント -> サーバ（例）

- join: {"type": "join", "name": "Alice"}
- offer/answer/candidate: {"type": "offer", "target": "<participant_id>", "data": {...}}
- leave: {"type": "leave"}
- chat: {"type": "chat", "text": "..."}

### サーバ -> クライアント（主なメッセージ）

- joined: {"type": "joined", "room_code": ..., "participant_id": ..., "role": ..., "name": ..., "color": "..."}
- waiting: {"type": "waiting", "room_code": ..., "message": ...}
- participants: {"type": "participants", "room_code": ..., "participants": [{"id": ..., "name": ..., "role": ..., "color": "..."}, ...]}
- participant-joined: {"type": "participant-joined", "id": ..., "name": ..., "role": ..., "color": "..."}
- participant-left: {"type": "participant-left", "id": ..., "name": ...}
- signal: {"type": "signal", "signal_type": "offer|answer|candidate", "data": ..., "from": "<sender_id>", "from_name": "<sender_name>"}
- chat: {"type": "chat", "from": "<sender_id>", "from_name": "<sender_name>", "text": "...", "color": "..."}

### 備考

- サーバは最初の参加者を `host` として割り当てます（以降は `participant`）。
- 最大参加者数は app.room_manager.MAX_PARTICIPANTS（デフォルト: 10）で制限されます。
- ルーム情報はプロセス内メモリで保持されます。水平スケール時は Redis 等を導入して共有する必要があります。

## ライセンス

MIT

ci: confirm CI runs on PR
