# 開発方針

この文書は開発の標準ワークフローを示します。基本の流れは以下の通りです。

> ドキュメントを修正 → 実装 → テスト → PR（レビュー・マージ）

---

## 1. 概要

- まずドキュメント（仕様・API・運用手順）を更新して合意を得る。
- その後、実装を小さな単位で行い、対応するテストを追加する。
- PR を作成し、CI 通過とレビュー承認を得てマージする。

## 2. 手順（詳細）

### 1) ドキュメントを修正／追加
- 目的: 期待動作・外部仕様を明確化して、レビューや実装ミスを減らす。
- 編集対象例: `README.md`, `docs/WEBSOCKET_API.md`, `architecture.md`, `CONTRIBUTING.md`
- ドキュメントが仕様の「契約」となるよう、具体的なメッセージフォーマットやコマンド例を入れる。

### 2) 実装
- ブランチ命名: `feature/<short-desc>`, バグ修正は `fix/<short-desc>`。
- 小さなコミットを心がけ、コミットメッセージは Conventional Commits スタイルを推奨（例: `feat: ~`、`fix: ~`、`docs: ~`）。
- コードスタイル: PEP8 準拠。自動整形ツール（black 等）を推奨。
- 開発サーバ: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

例:
```bash
git checkout -b feature/room-timeout
# 変更
git add .
git commit -m "feat: ルームタイムアウトを追加"
```

### 3) テスト
- 変更点に対するユニットテスト／統合テストを必ず追加する。
- テスト実行:
```bash
pip install -r requirements.txt
pytest -q
```
- E2E テストがある場合は `tests/e2e/` を確認して実行条件を満たす。

### 4) PR 作成
- タイトルは Conventional Commits に合わせる（例: `feat: ~`、`fix: ~`、`docs: ~`）。
- PR 本文に以下を必ず含める：概要、動機、主要変更点、動作確認手順、テスト内容。
- PR チェックリスト（最低）:
  - [ ] テストを追加/更新した
  - [ ] すべてのテストが通る
  - [ ] 必要なドキュメントを更新した
  - [ ] CI が成功している
  - [ ] レビュワーを 1 人以上アサインした
- マージポリシー: CI 合格かつレビュー承認後、`Squash and merge` を推奨。

## 3. 注意事項
- 破壊的変更（API 互換性の破壊）は事前に Issue を立て、設計合意を得ること。
- シークレットや鍵類は絶対にリポジトリに含めない（検出したら速やかに削除・回収する）。
- 大きな変更は小さな段階に分けて実装・レビューを行う。

## 4. 参考コマンド

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## CI の通過基準

CI は `.github/workflows/ci.yml` に定義されています。主な合格条件は次の通りです。

- 全ユニット／統合／E2E テストが成功すること（pytest 実行）。
- カバレッジ基準を満たすこと：行カバレッジ >= 90% かつ ブランチカバレッジ >= 80%（CI 内の coverage.xml チェックにより判定）。
- Playwright を使う E2E が含まれるため、ローカルで E2E を実行する場合は `python -m playwright install --with-deps chromium` を実行してブラウザ依存を満たすこと。
- 依存関係が正しくインストールされること（`pip install -r requirements.txt`）。

CI 実行環境について:

- GitHub Actions 上で Ubuntu 最新、Python 3.11 で動作します。可能であればローカル検証も Python 3.11 に合わせてください（少なくとも CI の実行環境と大きく乖離しないこと）。

必要に応じてこの文書をプロジェクトの慣習に合わせて更新してください。