# cheter

cheter はブラウザで動作するシンプルな動画チャットアプリです。
ユーザは「待ち受け番号」でマッチングし、WebRTC を使って音声・映像をやり取りします。

## 特徴

- 待ち受け番号によるシンプルなマッチング
- WebSocket ベースのシグナリング（FastAPI）
- Jinja2 テンプレートと静的ファイルを使用

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

## ライセンス

MIT
