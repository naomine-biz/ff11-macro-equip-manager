# ff11-macro-equip-manager

FF11のローカルファイルを扱うWindowsデスクトップアプリ。

## 開発資料

[要件](requirements.md)と[設計上の制約](docs/design-constraints.md)を正本とします。[参照文書一覧](docs/README.md)から検証仕様・既存実装との対応・ファイル形式を確認できます。

## 起動

Python 3.12とTkinterを使用します。リポジトリ直下で実行します。

```powershell
python reader.py
```

インストール先を指定する場合:

```powershell
python reader.py --root "C:\path\to\FINAL FANTASY XI"
```

## テスト

```powershell
python -m unittest discover -s tests -v
```

通常は合成データを使います。インストール済みFF11を読み取る統合テストは明示的な有効化が必要です。実機検証の取扱いは[SAFE-001](requirements.md#safe-001)に従います。

## データ

ゲーム資産・実マクロ・持ち物・キャラ情報・作業ファイル・バックアップはGitへ登録しません。

本プロジェクトは有志による非公式ツールです。ゲームの名称・リソースの権利は各権利者に帰属します。
