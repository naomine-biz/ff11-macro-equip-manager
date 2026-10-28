# 開発時の参照順

1. 正本は `requirements.md` と `docs/design-constraints.md`。対象の要件ID・設計条件IDを確認してから実装する。
2. 文書の役割と更新手順は [docs/README.md](docs/README.md) に従う。
3. `tests/specs/` は正本から導いた検証仕様、`docs/requirements-traceability.md` は既存コード・テストへの索引として使う。
4. バイナリ処理は `docs/reference/local-formats.md` と `docs/reference/sources.json` を確認する。
5. 実データと合成テストの取扱いは SAFE-001 に従う。

日本語は対象と処理を具体的に書く。不要な否定文や仮説による注意を付け足さない。
