# WebSocket API（シグナリング）

このドキュメントはシグナリング用 WebSocket のメッセージ仕様を簡潔にまとめたものです。

## エンドポイント

- ws://<host>/ws/{room_code}

## 主要メッセージ

1. クライアント -> サーバ

- join
  - 目的: ルームに参加（または待機）する
  - 形式: {"type": "join", "name": "表示名"}

- offer / answer / candidate
  - 目的: SDP / ICE 情報を特定の参加者に送る
  - 形式: {"type": "offer"|"answer"|"candidate", "target": "participant_id", "data": {...}}
  - 備考: サーバは `target` に一致する参加者の websocket に `signal` メッセージを転送する

- leave
  - 目的: ルーム退出
  - 形式: {"type": "leave"}

2. サーバ -> クライアント

- joined
  - 形式: {"type": "joined", "room_code": "...", "participant_id": "...", "role": "host|participant", "name": "..."}
  - 備考: join 成功時に送られる

- waiting
  - 形式: {"type": "waiting", "room_code": "...", "message": "..."}
  - 備考: まだ他の参加者がいない場合に返される

- participants
  - 形式: {"type": "participants", "room_code": "...", "participants": [{"id": "...", "name": "...", "role": "..."}, ...]}
  - 備考: 新規参加者に既存メンバーの一覧を返す

- participant-joined
  - 形式: {"type": "participant-joined", "id": "...", "name": "...", "role": "..."}
  - 備考: 既存参加者へ新規参加者を通知する

- participant-left
  - 形式: {"type": "participant-left", "id": "...", "name": "..."}
  - 備考: 参加者退出時に残存者へ通知する

- signal
  - 形式: {"type": "signal", "signal_type": "offer|answer|candidate", "data": {...}, "from": "<sender_id>", "from_name": "<sender_name>"}
  - 備考: サーバがターゲット参加者へ転送するメッセージ

## 実装メモ

- サーバは最初の参加者を `host` として割り当てる
- 最大参加者数は `app.room_manager.MAX_PARTICIPANTS`（デフォルト 10）で制限される
- ルーム情報はプロセス内メモリで保持しているため、複数プロセス/ノードで水平スケールする場合は Redis 等で状態共有を行うこと

## 参考コード

- app/main.py: WebSocket エンドポイントの実装
- app/room_manager.py: ルーム管理ロジック（参加者登録、退出、一覧取得など）

