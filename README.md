# cheter

cheter はブラウザで動作するシンプルな動画チャットアプリです。
ユーザは「待ち受け番号」でマッチングし、WebRTC を使って音声・映像をやり取りします。

## 特徴

- 待ち受け番号によるシンプルなマッチング
- WebSocket ベースのシグナリング（FastAPI）
- Jinja2 テンプレートと静的ファイルを使用

## ドキュメント

README をドキュメントの入口とし、**このリポジトリ内のドキュメントは README から辿れる状態を保つ**ことをルールとします。新しいドキュメントを追加・移動した場合は、この一覧も更新してください。

### 利用者向け

- [使い方ガイド](docs/USAGE.md)
- [WebSocket API](docs/WEBSOCKET_API.md)
- [構成図](architecture.md)
- [機能一覧](docs/FEATURES.md)

### 開発・運用

- [デプロイガイド](docs/DEPLOY.md)
- [開発方針](DEVELOPMENT.md)
- [開発ルール](docs/DEVELOPMENT_RULES.md)
- [コントリビューションガイド](CONTRIBUTING.md)
- [PR ガイドライン](PR_GUIDE.md)
- [変更履歴](CHANGELOG.md)

### GitHub 運用資料

- [Pull Request テンプレート](.github/PULL_REQUEST_TEMPLATE.md)
- [Copilot Review Policy](.github/COPILOT_REVIEW.md)

## クイックスタート（開発）

前提: Python 3.8+ がインストールされていること

1. 仮想環境を作成して有効化

   python -m venv .venv
   source .venv/bin/activate

2. 依存パッケージをインストール

   pip install -r requirements.txt

   （テストを実行する場合は pytest もインストール: pip install pytest）

3. 開発サーバを起動

   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

4. ブラウザで http://localhost:8000 を開く

前提: aws-vault + pass + GPG が設定済みであり、Docker もインストール・起動済みであること（`infra/cdk` で CDK の Lambda bundling に Docker を使用します。[デプロイガイド](docs/DEPLOY.md) 参照）

## クイックスタート（AWS デプロイ）

前提: aws-vault + pass + GPG が設定済みであること（[デプロイガイド](docs/DEPLOY.md) 参照）

```bash
# main を最新に
git checkout main && git pull origin main

# デプロイ（GPG パスフレーズの入力を求められます）
AWS_VAULT_BACKEND=pass ./scripts/deploy-cdk-with-aws-vault.sh chater-deploy
```

詳細な手順・初回セットアップ・トラブルシュートは [docs/DEPLOY.md](docs/DEPLOY.md) を参照してください。

## テスト

pytest -q

## プロジェクト構成（概要）

- app/: FastAPI アプリ本体（app.main にエントリポイント）
- docs/USAGE.md: ブラウザ版 cheter の使い方ガイド
- static/: 静的ファイル
- templates/: Jinja2 テンプレート
- architecture.md: システム構成図と説明
- tests/: テストコード

## 貢献

貢献歓迎です。開発ルールやブランチ運用については CONTRIBUTING.md を参照してください。特に、作業ブランチは必ず origin/main から作成し、PR を作る前に main を最新に保つ（rebase または merge）ことを推奨します。

このリポジトリでは、PR に対して CI が実行され、Unit テスト、E2E テスト、カバレッジがチェックされます。CI の結果サマリは PR に自動投稿され、Ruleset により全ての必須チェックが合格していないとマージできない設定になっています。CI が失敗した場合は main を先に修正してください。

## WebSocket API

### エンドポイント

- ws://<host>/ws/{room_code}  （例: ws://localhost:8000/ws/room123）

### クライアント -> サーバ（例）

- join: {"type": "join", "name": "Alice"}
- offer/answer/candidate: {"type": "offer", "target": "<participant_id>", "data": {...}}
- leave: {"type": "leave"}

### サーバ -> クライアント（主なメッセージ）

- joined: {"type": "joined", "room_code": ..., "participant_id": ..., "role": ..., "name": ..., "color": ...}
- waiting: {"type": "waiting", "room_code": ..., "message": ...}
- participants: {"type": "participants", "room_code": ..., "participants": [{"id": ..., "name": ..., "role": ..., "color": ...}, ...]}
- participant-joined: {"type": "participant-joined", "id": ..., "name": ..., "role": ..., "color": ...}
- participant-left: {"type": "participant-left", "id": ..., "name": ...}
- signal: {"type": "signal", "signal_type": "offer|answer|candidate", "data": ..., "from": "<sender_id>", "from_name": "<sender_name>"}
- 注: `color` は `joined`、`participants[*]`、`participant-joined` に含まれます。チャット関連のブロードキャストでも `color` が含まれる場合があるため、クライアント側では利用可能な追加フィールドとして扱ってください（旧サーバとの互換のため未設定の可能性は考慮してください）。

### 備考

- サーバは最初の参加者を `host` として割り当てます（以降は `participant`）。
- 最大参加者数は app.room_manager.MAX_PARTICIPANTS（デフォルト: 10）で制限されます。
- ルーム情報はプロセス内メモリで保持されます。水平スケール時は Redis 等を導入して共有する必要があります。

## ライセンス

MIT
