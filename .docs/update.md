## 更新履歴

### 2025-12-12

- **.gitignore を整備**: Python/Windows生成物と、Google OAuth関連の機密ファイル（`token.json`/`credentials.json` 等）を除外
- **.docs/ を追加**: `AGENTS.md` / `CLAUDE.md` / `copilot-instructions.md` / `update.md` を新設
- **Driveアップロード機能を追加**:
  - 入力欄へのドラッグ&ドロップでファイルをDriveへアップロード
  - アップロードURLを改行で入力欄へ追記し、従来どおりEnterでスプレッドシートに保存
  - 共有権限は変更しない（自分のみ閲覧）
  - 追加依存: `google-api-python-client`, `tkinterdnd2`


