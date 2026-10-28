# 要件と実装・検証の対応

本書は対応を探すための索引。要求は[requirements.md](../requirements.md)、内部の制約は[設計条件](design-constraints.md)を参照する。2026-10-28時点。テスト欄は存在を確認した代表テストであり、要件全体の網羅や今回の実行結果を表さない。将来要件に記載したモジュールは関連する既存基盤を示す。

合成データのテストを通常の検証に使う。`tests/test_ui.py`の実ゲーム読込を伴う検証は別扱いとし、今回実行していない。視覚品質・手動確認・未実装の不足は下表に残す。

| 要件 | 関連コード | 代表テスト | 確認範囲・不足 |
|---|---|---|---|
| SAFE-001 | [.gitignore](../.gitignore)、[file_transaction.py](../ff11reader/file_transaction.py) | [test_game_running_blocks_before_backup](../tests/test_macro_saving.py) | ゲーム終了条件を検証。Git除外と実機試験の承認は運用確認 |
| [DATA-001](../requirements.md#data-001) | [adapters.py](../ff11reader/adapters.py)、[codecs.py](../ff11reader/codecs.py)、[domain.py](../ff11reader/domain.py)、[ui.py](../ff11reader/ui.py) | [DecodingTests.test_macro_addresses_and_raw_lines](../tests/test_reader.py) | デコードの部分検証。アカウント単位の整理は未実装 |
| [DATA-002](../requirements.md#data-002) | [codecs.py](../ff11reader/codecs.py)、[dictionaries.py](../ff11reader/dictionaries.py)、[icons.py](../ff11reader/icons.py) | [DecodingTests.test_resolved_token_preserves_bytes_and_unknown_fallback](../tests/test_reader.py) | 文字解決を検証。アイコンは別の形式テストも参照 |
| [DATA-003](../requirements.md#data-003) | [codecs.py](../ff11reader/codecs.py)、[domain.py](../ff11reader/domain.py) | [DecodingTests.test_inventory_never_invents_quantity_or_augments](../tests/test_reader.py) | 未取得値を捏造しないことを検証。取得機能は未実装 |
| [DATA-004](../requirements.md#data-004) | [adapters.py](../ff11reader/adapters.py)、[references.py](../ff11reader/references.py) | [ReferenceTests.test_loaded_empty_and_missing_and_unreadable_are_distinct](../tests/test_references.py) | 参照判定を検証 |
| [EQ-001](../requirements.md#eq-001) | [references.py](../ff11reader/references.py)、[domain.py](../ff11reader/domain.py) | [SlotStateTests.test_augments_do_not_affect_reference_state](../tests/test_slot_state.py) | 一致・優先順位はSlotStateTestsにも検証あり |
| [EQ-002](../requirements.md#eq-002) | [fixes.py](../ff11reader/fixes.py)、[references.py](../ff11reader/references.py) | [FixTests.test_unique_target_in_every_storage_is_fixable](../tests/test_fixes.py) | 全収納の候補を検証 |
| [EQ-003](../requirements.md#eq-003) | [fixes.py](../ff11reader/fixes.py)、[references.py](../ff11reader/references.py) | [FixTests.test_no_candidate_and_repeated_position_are_blocked](../tests/test_fixes.py) | 不足資料・キャラ分離は関連テストでも検証 |
| [EQ-004](../requirements.md#eq-004) | [domain.py](../ff11reader/domain.py)、[references.py](../ff11reader/references.py)、[editing.py](../ff11reader/editing.py) | [FoundationTests.test_equipment_validation_and_derived_state_undo](../tests/test_edit_foundation.py) | 状態の再評価を検証 |
| [LINK-001](../requirements.md#link-001) | [macro_links.py](../ff11reader/macro_links.py) | [MacroLinksTests.test_reference_with_trailing_options](../tests/test_macro_links.py) | 空・remove・未知は同モジュールの別テストで検証 |
| [LINK-002](../requirements.md#link-002) | [macro_links.py](../ff11reader/macro_links.py)、[ui.py](../ff11reader/ui.py) | [MacroLinksTests.test_reverse_references_keep_addresses_and_lines](../tests/test_macro_links.py) | 参照位置を検証。画面上の読みやすさは手動確認 |
| [LINK-003](../requirements.md#link-003) | [macro_links.py](../ff11reader/macro_links.py) | [MacroLinksTests.test_isolation_and_no_mutation](../tests/test_macro_links.py) | キャラ分離と非変更を検証 |
| [MAC-001](../requirements.md#mac-001) | [macro_inventory.py](../ff11reader/macro_inventory.py) | [MacroInventoryTests.test_storage_mapping_and_suffix_preservation](../tests/test_editing.py) | 番号対応と後続部分を検証 |
| [MAC-002](../requirements.md#mac-002) | [macro_inventory.py](../ff11reader/macro_inventory.py)、[presentation.py](../ff11reader/presentation.py) | [MacroInventoryTests.test_state_matrix](../tests/test_editing.py) | 状態の組合せを検証 |
| [MAC-003](../requirements.md#mac-003) | [macro_inventory.py](../ff11reader/macro_inventory.py)、[editing.py](../ff11reader/editing.py) | [EditingTests.test_batch_undo_redo_branch_and_raw_preservation](../tests/test_editing.py) | 履歴と元表現を検証。番号生成はMAC-001も参照 |
| [MAC-004](../requirements.md#mac-004) | [ui.py](../ff11reader/ui.py)、[edit_application.py](../ff11reader/edit_application.py) | [EditingUITests.test_edit_preview_undo_redo_fix_and_reopen](../tests/test_editing_ui.py) | 合成GUIの操作を検証。初期フィルターの専用検証は不足 |
| [EDIT-001](../requirements.md#edit-001) | [editing.py](../ff11reader/editing.py)、[edit_application.py](../ff11reader/edit_application.py) | [EditingTests.test_fix_recomputed_and_no_game_save_dependency](../tests/test_editing.py) | 保存処理への非依存を検証 |
| [EDIT-002](../requirements.md#edit-002) | [editing.py](../ff11reader/editing.py)、[edit_values.py](../ff11reader/edit_values.py) | [FoundationTests.test_invalid_batch_is_atomic_even_through_generic_apply](../tests/test_edit_foundation.py) | 汎用変更案を含めて検証 |
| [EDIT-003](../requirements.md#edit-003) | [editing.py](../ff11reader/editing.py) | [EditingTests.test_batch_undo_redo_branch_and_raw_preservation](../tests/test_editing.py) | 共通履歴・無変更は関連テストでも検証 |
| [EDIT-004](../requirements.md#edit-004) | [draft_store.py](../ff11reader/draft_store.py)、[edit_application.py](../ff11reader/edit_application.py) | [EditingTests.test_persistence_redo_conflict_and_failed_save](../tests/test_editing.py) | 保存失敗・再開・競合を検証 |
| [EDIT-005](../requirements.md#edit-005) | [draft_store.py](../ff11reader/draft_store.py)、[edit_application.py](../ff11reader/edit_application.py) | [EditingTests.test_corrupt_draft_is_preserved](../tests/test_editing.py) | 破損保護の部分検証。外部更新から再読込する全手順の専用検証は不足 |
| [EDIT-006](../requirements.md#edit-006) | [editing.py](../ff11reader/editing.py)、[edit_application.py](../ff11reader/edit_application.py)、[ui.py](../ff11reader/ui.py) | [EditingUITests.test_edit_preview_undo_redo_fix_and_reopen](../tests/test_editing_ui.py) | マクロ編集を検証。装備セットの個別編集UIは未実装 |
| [SAVE-001](../requirements.md#save-001) | [save_plan.py](../ff11reader/save_plan.py)、[macro_saving.py](../ff11reader/macro_saving.py)、[equipment_saving.py](../ff11reader/equipment_saving.py)、[ui.py](../ff11reader/ui.py) | [MacroSavingTests.test_unrelated_manual_edits_are_retained](../tests/test_macro_saving.py) | Fix保存と保留を検証。任意編集の保存は未実装 |
| [SAVE-002](../requirements.md#save-002) | [macro_saving.py](../ff11reader/macro_saving.py)、[equipment_saving.py](../ff11reader/equipment_saving.py)、[file_transaction.py](../ff11reader/file_transaction.py) | [MacroSavingTests.test_stale_macro_inventory_and_plan_tamper_rejected](../tests/test_macro_saving.py) | マクロの競合を検証。装備保存にも同等テストあり |
| [SAVE-003](../requirements.md#save-003) | [file_transaction.py](../ff11reader/file_transaction.py) | [EquipmentSavingTests.test_candidate_changes_and_staging_failure](../tests/test_equipment_saving.py) | 装備保存の準備失敗を検証 |
| [SAVE-004](../requirements.md#save-004) | [macro_saving.py](../ff11reader/macro_saving.py)、[saving.py](../ff11reader/saving.py)、[codecs.py](../ff11reader/codecs.py) | [MacroSavingTests.test_token_zero_bytes_japanese_padding_and_length_limit](../tests/test_macro_saving.py) | 既存Fixの形式検証。新規定型文編集のエンコードは未実装 |
| [SAVE-005](../requirements.md#save-005) | [file_transaction.py](../ff11reader/file_transaction.py)、[edit_application.py](../ff11reader/edit_application.py) | [EquipmentSavingTests.test_failed_rollback_keeps_pending_and_blocks_edits](../tests/test_equipment_saving.py) | 復旧待ちを検証。外部更新は復元テストも参照 |
| [SAVE-006](../requirements.md#save-006) | [edit_application.py](../ff11reader/edit_application.py)、[draft_store.py](../ff11reader/draft_store.py) | [MacroSavingTests.test_draft_checkpoint_failure_recovers_on_restart](../tests/test_macro_saving.py) | 同期失敗を検証。保存後Undoは保存テストでも検証 |
| [VIEW-001](../requirements.md#view-001) | [ui.py](../ff11reader/ui.py) | — | 専用自動テストなし。画面で確認する |
| [VIEW-002](../requirements.md#view-002) | [ui.py](../ff11reader/ui.py)、[presentation.py](../ff11reader/presentation.py) | [PresentationTests.test_four_main_actions](../tests/test_presentation.py) | 状態表示の分類を検証。視覚品質は手動確認 |
| [VIEW-003](../requirements.md#view-003) | [ui.py](../ff11reader/ui.py) | — | 専用自動テストなし。繰返し操作と視認で確認する |
| [WARD-001](../requirements.md#ward-001) | [wardrobe_usage.py](../ff11reader/wardrobe_usage.py) | [WardrobeUsageTests.test_scope_and_both_reference_sources](../tests/test_wardrobe_usage.py) | 参照元と対象収納を検証 |
| [WARD-002](../requirements.md#ward-002) | [wardrobe_usage.py](../ff11reader/wardrobe_usage.py) | [WardrobeUsageTests.test_edit_and_undo_recompute_without_cross_character_references](../tests/test_wardrobe_usage.py) | 再計算とキャラ分離を検証 |
| [FUT-001](../requirements.md#fut-001) | [editing.py](../ff11reader/editing.py)、[save_plan.py](../ff11reader/save_plan.py) | — | 未実装。衝突・上書き・入替えの規則は着手前に確定する |
| [FUT-002](../requirements.md#fut-002) | — | — | 未実装。参照セットの同時コピーと番号衝突の扱いは未決定 |
| [FUT-003](../requirements.md#fut-003) | [macro_inventory.py](../ff11reader/macro_inventory.py) | — | /equipの参照判定は実装済み。汎用検索と誤記検出の範囲・判定規則は未決定 |

## 関連資料への索引

| 資料 | 対応する要件・制約 | 役割 |
|---|---|---|
| [ローカル形式](reference/local-formats.md) | DATA-001〜004、SAVE-004 | 形式の調査結果。バイト配置の実装根拠 |

設計条件D-01〜03は `tests/test_edit_foundation.py` の依存境界・変更案・読み取りビュー・dirty検証、D-04〜05は `tests/test_macro_saving.py` と `tests/test_equipment_saving.py` の保存・保留・復旧検証に対応する。移動の依存グループ保存、新規定型文の逆変換、操作別依存の一般化は未実装で、現在のテストを完了根拠にしない。

## 検証仕様

- [Example Test仕様](../tests/specs/example-tests.md): 84ケース。要件から導いた受入仕様。
- [Property Test仕様](../tests/specs/property-tests.md): 35項目。生成条件と不変条件。

上表の既存テストとの対応と、新しい検証仕様の実装状況は別に扱う。本整理ではテストを追加・実行していない。

## 現行実装との差分監査（2026-10-28）

対象: コミット375051eの要件・設計制約・Example Test 84ケース・Property Test 35項目と、現行コード・既存テスト102メソッド。
方法: ソースとテストの静的確認、メモリ上で構築した合成値による純粋関数の確認。テストモジュールのimport、テストスイート、GUI、インストール先の検出・読込・保存は実行していない。以下は差分記録であり、要求の追加や実装変更を行うものではない。

### A. 現在の機能で確認した差（GAP-01〜05は下記の修正結果を参照）

| ID | 根拠 | 現行の結果・確認箇所 | 必要な変更 | 追加・変更する検証 |
|---|---|---|---|---|
| GAP-01 | MAC-002、PT-09 | [macro_inventory.py](../ff11reader/macro_inventory.py)のassess_macro_inventoryは全収納のcompleteを明示収納の一致より先に確認する。`/equip body Robe 1`、B8に一個、B1未読込でincompleteとなる。合成値で確認 | 指定収納の有効な一意参照は、その収納の資料から判定する。全収納の完全性は移動先・番号追加の一意Fixで要求する | [test_editing.py](../tests/test_editing.py)のstate_matrix等へ「指定先正常・他収納欠落」「指定先重複」を追加。指定なしの場合の保留は維持 |
| GAP-02 | EQ-004、D-01/D-02、EX-E08〜10、PT-04/05 | [references.py](../ff11reader/references.py)、[fixes.py](../ff11reader/fixes.py)、[presentation.py](../ff11reader/presentation.py)で判定が分かれる。数量2の一候補はSlotがsame_type_elsewhere、Fix側はquantity_not_one。未読込収納に行が残る入力ではSlotがinsufficient_dataなのにFix側のissuesは空。合成値で確認 | ドメインで候補・Fix可否・保留理由を整合させ、Slotの評価を表示とFixで共有する。一致判定でも収納の読込状態・位置の妥当性を同じ基準で確認する | [test_slot_state.py](../tests/test_slot_state.py)、[test_fixes.py](../tests/test_fixes.py)、[test_presentation.py](../tests/test_presentation.py)へ同一入力に対する評価・理由・案の整合性を追加。未知・不完全入力を生成する |
| GAP-03 | DATA-004、WARD-001、D-01、PT-30 | [wardrobe_usage.py](../ff11reader/wardrobe_usage.py)はdirectを重複位置・読込状態の検査より優先。B8,11にRobeとOtherの2行、マクロはRobe 1で、マクロ判定はincomplete、使用状況はRobeをreferencedとする。合成値で確認 | 確定参照を出す前に対象位置の有効性を確認する。参照あり・候補・保留の判定をドメインの観測条件とそろえる | [test_wardrobe_usage.py](../tests/test_wardrobe_usage.py)へ明示参照と重複位置・無効位置・未読込の組合せを追加。確定未参照へ落とさないことも確認 |
| GAP-04 | D-02、PT-02 | [fixes.py](../ff11reader/fixes.py)のfingerprintはセット列挙順とraw_hexを含む。値を変えずセット順を反転するとapply_fixesが古い案として拒否。合成値で確認 | Fixの意味上の前提を対象キー順に正規化し、原本メタデータと分ける。保存時の原本ハッシュ照合は維持する | [test_fixes.py](../tests/test_fixes.py)へ順序置換・未編集raw差の不変性を追加。候補値変更による拒否の既存テストを維持 |
| GAP-05 | D-05、SAVE-003〜005 | GUIは[file_transaction.py](../ff11reader/file_transaction.py)のexecute_batchを使うが、[application.py](../ff11reader/application.py)のsave_game_plan→[saving.py](../ff11reader/saving.py)のexecute_saveは独自のバックアップ・置換経路を持つ。静的確認 | 旧CLIの保存も共通実行処理へ接続する。既存CLIの入出力・バックアップ互換性を確認して移行する | [test_saving.py](../tests/test_saving.py)の既存ケースを維持し、置換後の検証失敗・復旧を追加。[test_edit_foundation.py](../tests/test_edit_foundation.py)の依存境界テストをCLI経路まで拡張 |

GAP-02の未読込収納に行が残る入力は、現行デコーダーで発生した実データの報告ではない。生成仕様が許容する不完全入力に対する整合性の差として扱う。

### B. 機能拡張前に整理する設計差

| ID | 根拠 | 現行 | 必要な整理・検証 |
|---|---|---|---|
| DESIGN-01 | DATA-002、D-02/D-04、PT-07/24 | [domain.py](../ff11reader/domain.py)のTextはdisplay/raw_hex/state。[edit_values.py](../ff11reader/edit_values.py)と[editing.py](../ff11reader/editing.py)はdisplayで同一性を比較する | 任意マクロ保存前に定型文IDと表示文字の区別を値の構造へ反映する。原本メタデータ差を無視する既存テストは維持し、「同表示・異なるトークンID」「同ID・辞書表示変更」「未変更未知トークン保持」を別途検証する。現在のraw差だけの合成例はトークン衝突の実証ではない |
| DESIGN-02 | D-04、SAVE-001/004 | [macro_saving.py](../ff11reader/macro_saving.py)と[equipment_saving.py](../ff11reader/equipment_saving.py)のprepare処理に差分抽出・対応範囲判定・ファイル読込・変換がまとまっている | 任意編集の保存を増やす際に、意味上の差分・保留と形式処理の境界を明示する。新しいクラス構成を必須とはしない。持ち物を使わない名前変更にFix専用の完全性条件を広げない |
| DESIGN-03 | FUT-001、D-04、PT-32 | Change/Editによる一括適用はあるが、保存案はファイル別のFix群。参照依存グループの保存情報はない | 移動実装時にグループ全体の適用・Undo・保留・保存を表現する。現行の独立Fixの部分保存を廃止する変更は不要 |

### C. テスト仕様との不一致・前提を確定する箇所

| ID | 根拠 | 差 | 対応 |
|---|---|---|---|
| SPEC-01 | LINK-001/002、PT-08 | [macro_links.py](../ff11reader/macro_links.py)は`not is_empty`を既知の非空と同じに扱い、未知動作や16枠未満のセットも参照なし一覧へ入れる。未知一枠の合成セットで確認。既存test_remove_and_unknown_are_not_emptyは「空でない」しか検証しない | PT-08の「既知の非空だけ」を満たす空・非空・不明の区別が必要。removeは既知の非空を維持する。未知・欠落枠を含むセットの逆参照通知を要件で明記してからコードとテストをそろえる |
| SPEC-02 | EDIT-005、EX-B11、PT-18 | [edit_application.py](../ff11reader/edit_application.py)のstart_freshは現在のsavedから開始し、ファイルを再読込しない。[ui.py](../ff11reader/ui.py)のリセットも同じ。起動時に新Snapshotを渡してからリセットする経路はある | 「再起動して最新Snapshotを取得→古い作業保管→再開」と「起動中に最新を再読込」を分ける。現行リセットを押すだけで最新取得できるという期待にはしない。まず前者の受入テストを追加し、後者の必要性を要件で確定する |
| SPEC-03 | SAFE-001、PT-35 | Property仕様は全操作について保存要求前のゲーム側書込イベント0を要求する。共通条件だけでは、ゲーム側を意図的に外部更新する障害注入まで違反として数え得る | アプリ自身の書込イベントと、テスト用の外部更新・初期データ構築を区別して観測する。保存時の一時ファイルと原本置換も別イベントにする |
| SPEC-04 | DATA-001、FUT-001〜003、PT-01/32〜34 | 複数インストールを含む生成、コピー先衝突、検索範囲などに未決定事項が残る。現行の単一インストール内のキャラ分離テストだけでは全範囲を証明できない | 現行対応範囲の生成器と将来機能の生成器を分ける。未決定の期待値を現行コードから補完しない |

### D. 既存テストへ追加する検証

既存102メソッドは主に固定例によるunittest。小さな入力表・ループ検証はあるが、PT仕様の生成器、操作列モデル、失敗例の縮小・seed再現を担う共通基盤はない。35項目のPropertyがすべて未検証という意味ではなく、現在の具体例では満たす範囲が限定される。

| ID | 対象仕様 | 現状の検証 | 不足する検証 |
|---|---|---|---|
| TEST-01 | PT-01〜12、PT-30/31 | 参照・Fix・使用状況の固定例、全17収納を回すFix例、キャラ分離例 | 候補0/1/複数、読込状態、重複位置、行順の組合せ生成。評価の整合性、前方/逆参照集合の一致。GAP-01〜04の反例を固定テストにも追加 |
| TEST-02 | EX-B02/03、PT-13 | test_invalid_batch_is_atomic_even_through_generic_applyの案は同一対象を2件含み、重複拒否で先に止まる場合がある | 異なる二対象のうち一件だけを不正にするケースを追加し、不正値・古い前提・欠落対象それぞれの拒否と全体不変を独立に検証する |
| TEST-03 | PT-14〜18、PT-27 | 固定のUndo/Redo、分岐、作業保存失敗、再開、保存後Undo | 独立した値辞書と履歴カーソルの参照モデルを用意し、任意操作列で各段階を照合。無変更操作後のRedo維持、失敗したUndo/Redo、外部更新後の再開も含める |
| TEST-04 | EX-S06/07、PT-22/25/26 | 2ファイル保存、特定の置換・準備・復元失敗、作業同期失敗の具体例 | 3ファイル以上、全バックアップ・全一時ファイルの各失敗地点、各置換/検証前後、強制中断相当の再開を生成。最初の置換より前に全準備が完了したことをイベント列で検証 |
| TEST-05 | PT-23/24 | 固定オフセット41の変更と未知バイト保持、既知トークンの内部ゼロ、60バイト超過などの具体例 | 各部位・行・ページの先頭/末尾、上限直前/同値/超過、変換不能、未知トークンの組合せ。固定形式の独立オラクルを拡張し、本体エンコーダー/デコーダー同士の一致だけに依存しない |
| TEST-06 | D-01/D-05、PT-35 | test_dependency_boundariesは一部モジュールの直接importとGUI/2保存モジュールを検査 | macro_inventory、macro_links、wardrobe_usage等と旧CLI経路を対象に加える。テスト用I/Oの許可ルート・ネットワーク・レジストリ・メモリ読込の拒否を共通化 |
| TEST-07 | EX-U01〜05、PT-28/29 | 合成GUIの編集・保存例と実ゲーム依存のtest_ui | アコーディオン、空行減光、選択と詳細の対応、Fix限定一覧、ホバー/クリック反復を合成データで検証。視認性の判定基準と検証手段を定める |
| TEST-08 | SAFE-001、検証仕様の共通条件 | 合成GUIテストと実ゲームを読むtest_uiが同じFF11_RUN_INTEGRATIONフラグを使う | 合成GUIと実ゲーム統合を別の明示フラグまたは別実行対象に分ける。合成GUIの一括実行で実ゲーム読込が有効にならない構成にする |
| TEST-09 | 全Example/Property | 対応表は要件と代表テストを結ぶが、EX/PT IDごとの実装状況は未記録 | 既存テストを利用できる範囲、追加ケース、将来機能で未着手の範囲をEX/PT IDへ対応付ける。メソッド数と仕様ケース数を合否判定に使わない |

### E. 合意済みの将来機能との差

| 要件・仕様 | 現状 | 後続で必要な実装 |
|---|---|---|
| SAVE-001、EX-S15 | 現保存対象は収納番号Fix・装備位置Fix。任意編集は保留 | マクロ名・6行の形式変換と保存。DESIGN-01/02を先に扱う |
| EDIT-006、EX-B12、PT-19 | 汎用Changeで枠の値を扱えるが、個別編集・候補手動選択のUIと一般保存はない | 名前・keep/remove/equip・手動選択の編集と保存 |
| FUT-001/002、EX-F01〜04、PT-32/33 | 移動・カスケード・キャラ間コピー未実装 | 衝突規則、依存更新、一括保存、コピー先の再評価 |
| DATA-001、EX-D02 | キャラの表示名登録とフォルダ切替はあるが、アカウント別整理は未実装 | アカウント識別と整理の仕様確定・実装 |
| FUT-003、EX-F05/06、PT-34 | /equipの名前照合はある。汎用の名前/ID検索・誤記検出は未実装 | 検索対象、辞書未解決と未所持の区別、誤記候補規則 |
| EDIT-005 | 古い作業の保管・起動時再読込は可能。選択的引継ぎ未実装 | 競合時の引継ぎ規則と操作 |
| DATA-003 | オーグメント取得不可 | 保留を継続。今回の修正対象へ含めない |

### 対応順

1. GAP-01〜03の参照判定と使用状況の不整合を固定反例で検証し、ドメインへ集約する。
2. GAP-04の意味上の前提、GAP-05の共通書込み経路をそろえる。TEST-02/06/08を併せて補う。
3. TEST-01/03/04/05の生成・状態機械・障害注入を追加し、既存Fixの条件を広げず検証範囲を増やす。
4. SPEC項目を確定したうえでDESIGN項目と将来機能へ進む。

差分監査時は本対応表のみを更新した。その後のGAP-01〜05の修正結果を以下に記録する。

### GAP-01〜05の修正結果（2026-10-28）

5件の反例を先にテストへ追加し、修正前に失敗することを確認した。正本とテスト仕様の期待値は維持した。

| 差分 | 修正 | 回帰テスト |
|---|---|---|
| GAP-01 | 明示収納の一意参照をその収納の資料で判定。全収納の完全性は番号追加・変更案で要求 | [test_reference_regressions.py](../tests/test_reference_regressions.py): test_explicit_storage_match_is_local、test_unrelated_invalid_candidate_does_not_hide_explicit_match（MAC-002、PT-09） |
| GAP-02 | ItemReferenceへreason/fix_targetを追加。assess_equipmentが評価し、Fix計画と表示が利用 | 同ファイル: test_slot_and_plan_share_blocking_reason、test_slot_owns_unique_target_and_exact_match_priority（EQ-004、D-01、EX-E08〜10、PT-03〜06） |
| GAP-03 | [inventory_observation.py](../ff11reader/inventory_observation.py)で収納読込・有効位置・重複検査を共有。使用状況は不正観測を先に保留 | 同ファイル: test_usage_never_confirms_invalid_observation（WARD-001、PT-30） |
| GAP-04 | Fix指紋をキー順の意味上の値で構築し、raw_hexを除外。変更案と保留一覧の順序も固定 | 同ファイル: test_fix_preview_ignores_order_and_raw_metadata（D-02、PT-02）。候補変更時の拒否も検証 |
| GAP-05 | 旧CLIのexecute_saveもexecute_batchへ委譲。original.datと旧receipt形式を維持し、検証失敗の復元・外部更新保護を共通化 | [test_saving.py](../tests/test_saving.py): test_legacy_save_delegates_to_shared_transaction、test_post_write_decode_failure_rolls_back_legacy_save、test_legacy_rollback_preserves_external_update（D-05、SAVE-003〜005） |

旧作業ファイルのItemReferenceに新フィールドがない場合の読込・再評価はtest_old_draft_assessment_can_be_recomputedで確認。依存境界テストは新しい観測モジュール、参照クエリ群、旧CLIの共通保存呼出しまで拡張した。

検証: `FF11_RUN_INTEGRATION=0`、`python -B -m unittest discover -s tests -q`。112件中106件成功、GUI関連6件スキップ。保存・復旧は一時ディレクトリの合成ファイルのみ。ゲームデータの検出・読込・書込、実機GUI検証は行っていない。

GAP修正完了時点では、B〜Eの将来機能、仕様の明確化、Property Testの生成基盤は未着手だった。生成基盤の実装結果は次節を参照する。TEST-06の直接依存検査とCLI経路の検査は拡張済みで、全I/O隔離の共通基盤とGUIフラグ分離は引き続き未対応。

### 編集・保存のProperty Test（2026-10-28）

| 仕様 | 実装 | 検証範囲 |
|---|---|---|
| PT-13 | [test_editing_properties.py](../tests/test_editing_properties.py) | 異なる対象を含む変更案に、古い前提・欠落対象・不正構造・重複を混ぜ、順序を変えて全体拒否と作業ファイル不変を確認 |
| PT-14/15/17 | 同ファイル | 複数キャラのマクロ・装備枠編集、一括Fix、Undo/Redo、無変更、分岐、作業保存失敗、任意位置での再開。値辞書と履歴カーソルの独立モデルで各操作後を照合 |
| PT-16/20/27 | [test_saving_properties.py](../tests/test_saving_properties.py) | 一部Fix・一括Fix・名前の手編集・保存・Undo/Redo・再開・保存失敗を混在。保存可能差分と保留を分け、保存済み値・履歴・dirty・実バイトを照合 |
| PT-18 | test_editing_properties.py | 新しいSnapshotで起動して旧作業を保管する経路。起動中のファイル再読込は対象外 |
| PT-21 | test_saving_properties.py | 対象ファイル・収納・working・保存案・偽のゲーム起動状態を変更し、置換前の拒否を確認 |
| PT-22 | 同ファイル | マクロ/装備の1〜3ファイルについて、全バックアップ・一時ファイルの作成/fsync/読込検証地点へ障害注入。計72ケース。全準備が最初の置換に先行することをイベント列で確認 |
| PT-23 | 同ファイル | ページ・マクロ座標・行・装備セット内位置・部位・移動先収納をseedで変える。固定オフセットから独立に作った期待バイト、MD5、対象外バイトと照合 |
| PT-24 | 同ファイル | 現行の収納番号Fixについて、CP932の1/2バイト文字、内部ゼロを含む既知トークン、保存後59/60/61バイトを生成。任意文字入力や新規定型文保存は未実装範囲として除外 |
| PT-25 | 同ファイル | 3ファイルの各置換前後・検証地点の失敗、形式を保持した外部更新、復元失敗と操作停止を確認 |
| PT-26 | 同ファイル | 最初の書込前、各置換後、作業同期の前後、pending削除前で通常の例外復元を通らない中断を注入。全原本・全予定出力・混在を区別して再開を確認 |

生成・再現基盤は[property_support.py](../tests/property_support.py)。標準ライブラリを使用し、既定seedは0,1,7,19,42,127。編集/保存の操作列が失敗した場合は、同じ検証箇所で失敗する操作列まで削減し、seed・元の操作列・縮小列・期待値と実値を含むエラーを`work/property-tests/`へ記録する。障害地点の有限列挙はkind/count/phase/atをunittestのsubTestで報告する。

合成ルート外のファイル操作、ネットワーク、レジストリ、外部プロセス起動、ネイティブ呼出しを監査フックで拒否する。インストール検出は拒否、ゲーム起動検査・OSロック・マクロ保存時の再読込はテスト用実装へ差し替える。[test_property_support.py](../tests/test_property_support.py)で隔離と縮小処理を検証する。OSの実ロック、実プロセス強制終了・停電、GUI、実ゲームの動作確認は本検証に含めない。

#### 生成テストで発見した再開時の不一致

seed 42の保存操作列を次の5操作へ縮小した。マクロ・装備セットの両方で再現する。

`一括Fix → 保存 → Undo → 一部のFixを再適用 → 再起動`

v2作業ファイルは履歴の各対象の最初のbeforeからbaselineを復元する。保存済み操作をUndoして分岐すると、Redo破棄で履歴から消えた対象について起点の値を失い、再開時にsavedの値へ戻っていた（EDIT-003/004、D-02/03、PT-16/17）。

修正: v3作業ファイルへ編集対象のbaselineを明示保存する。再開時は対象キーと構造を検証して履歴を再生し、pending照合にもbaselineを含める。v1/v2の読込は維持し、次の作業保存でv3へ移行する。過去のv2ファイルで既に失われた起点情報の復元は対象外。

固定回帰例はtest_saved_undo_branch_reopen_regression。旧版読込、v3への保存、壊れたbaselineの拒否はtest_legacy_work_versions_and_invalid_baselineで確認する。実際のユーザー作業ファイルは操作していない。

検証結果: 既存テストを含む128件中122件成功、GUI関連6件スキップ。Property Testには複数の生成ケースと操作列を含むため、メソッド件数と生成ケース数は異なる。

残る範囲: PT-19の手動候補選択UI、任意編集の一般保存、生成範囲外の辞書変更・全文字列形式、OSレベルの障害とGUI。新しい機能や境界を追加する際に生成器を拡張する。

## 編集中の待機カーソル（2026-10-28）

EDIT-001 / D-01: `ui.py` の `run_edit` で編集・Fix・Undo/Redo・リセットと画面更新をまとめ、`waiting_cursor` で待機表示を設定・解除する。Tkの合成ウィジェットで正常終了・例外時のカーソル復元を確認済み。ゲームデータは使用していない。

## 操作時間の追跡（2026-10-28）

OBS-001 / D-08: `tracing.py` に共通の区間計測と容量制限付きログを実装。`edit_application.py`、`draft_store.py`、`ui.py` の境界で計測する。`tests/test_tracing.py` で親子ID・例外時の記録・本文非記録・ログ出力失敗時の処理継続を確認。

2キャラ計8,000マクロの合成データで編集・Undo・Redoを各1回計測したところ、画面描画を除く全体は約0.79〜0.81秒、作業保存は約0.46〜0.49秒、セッションコピーは約0.16〜0.18秒だった。実データでの時間・GUI描画時間は未計測。各親区間は子の時間を含む。ログは `work/logs/timings.jsonl`、1ファイル約2MBで過去3世代を保持する。

## 永続Mapによる編集ストアの比較試作（2026-10-28）

対象: EDIT-001〜004、D-01〜03。`experiments/persistent_edit_store.py` は本体から独立した採用判断用の試作。ドメインクラス・本体の保存形式・依存関係は変更していない。試作用依存は `experiments/requirements-undo.txt` に固定した。

入力と出力の対象オブジェクトをdeepcopyし、ストア内部の値は置換のみで更新する。内部Mapと共有値を外部へ渡さず、既存のMacro/Equipsetを使用する。永続Mapだけでは内部の可変辞書を保護できないことを負の対照で確認した。この方式はストア内部の所有権規約に依存するため、任意オブジェクトのdeepcopy代替としては扱わない。

2ライブラリ×6seed×200操作を独立した辞書モデルと照合し、編集・一括編集・Undo/Redo・分岐・保存済み範囲の更新・失敗時の状態保持を確認した。入力・取得値・保存コールバックへ渡した値の入れ子辞書への変更が内部状態へ漏れないことも確認した。保存失敗はコールバックによる模擬であり、ファイル書込み・再起動復旧は対象外。

合成8,000マクロ、編集時間は5回の中央値。全件コピー比較ストア311.521ms、immutables 0.121ms、Pyrsistent 0.138ms。400件では12.736ms、0.097ms、0.175ms。全件を外部向けに取り出すコピーは8,000件で約314〜361msと残った。10編集後のtracemalloc計測追加保持量は比較ストア159.196MiB、immutables 0.051MiB、Pyrsistent 0.046MiB。初期状態分・プロセス全体のメモリ・計測されないネイティブ割当は含まない。

比較ストアは本体Editorではなく、いずれも履歴に状態の参照を保持する。Undo/Redoの比較ストアも全件再コピーしないため、この値から本体の高速化率は算出しない。ドメイン判定、GUI、作業保存は計測対象外。導入時には全件snapshot取得と作業保存の別途改善が必要。候補としては両者とも有効で、Mapだけを必要とする現在の試作にはimmutablesが簡潔。実アプリへの採用は未決定。

再現（リポジトリ直下、Python 3.12）:

```powershell
python -m pip install --target work/undo-prototype/deps -r experiments/requirements-undo.txt
python -B experiments/persistent_edit_store.py
```

出力: `work/undo-prototype/results.json`。ゲームデータは参照しない。

## 永続Mapの組み込み（2026-10-28）

- 対応: EDIT-001〜004、SAVE-006、PERF-001、D-01〜04、EX-OWN01〜05、EX-PF01。
- `edit_state.py`: immutables 0.21で編集対象と意味上の比較値を保持。内部値は置換のみとし、入出力をコピーする。`domain.py`の型は変更していない。
- `editing.py`: forkで状態を共有し、適用時は対象だけを置換。公開したworking/baseline/saved/historyは独立した値。検証・復旧時の状態取込みはsetterで行い、重複キーは取り込み時に拒否する。
- `edit_application.py`: 作業保存成功後の確定手順を維持。`ui.py`は前回の表示用スナップショットを渡し、未変更の表示用値を再利用する。内部状態への参照は返さない。
- `draft_store.py`: v3形式、ロック、fsync、競合検出、pending復旧を維持。履歴起点のJSON文字列を読込時に準備し、同じ起点では再利用する。ゲーム保存時の原本・バックアップ形式は変更していない。
- 依存: `requirements.txt`。アプリ専用の`.venv`を使用する。

検証: 全体135件中129件成功・6件スキップ。その後追加した共有範囲検証を含め、合成GUI・保存・所有権の関連38件も成功。`test_persistent_edit_state.py`の6件は入れ子辞書・履歴・分岐の分離、作業保存失敗、表示更新、baselineキャッシュと再開を確認する。既存Property Testの期待値は維持した。旧テストの直接内部変更は、独立値を編集してsetterで取り込む形へ変更した。

`experiments/benchmark_editor.py`で実際のEditorを合成データから実行する。8,000マクロでは初回編集20.8ms、繰返し5回の中央値は編集26.1ms、Undo26.1ms、Redo25.4ms。作業保存・表示用データ更新・dirty判定を含み、GUI描画・ゲーム保存は含まない。初期化と最初の表示用データ取得には約1.07秒。以前の同規模合成計測は約0.79〜0.81秒/操作だったが、同時実行の厳密な比較ではない。実画面の約13秒に対する改善幅は再計測が必要。

未改善: 作業ファイル自体は依然全体を書き出す。初期読込・保存計画時の全体取得・保存後状態の取込みにもデータ量に応じた処理がある。将来の持ち物更新操作では装備参照の再評価範囲を追加する必要がある。

検証時の記録: 合成GUI検証に実ゲーム読込テストを誤って含め、読み取りが発生した。Fixボタンの有効性確認で停止し、ゲームへの書込みは実行していない。実ゲームUIテストを`FF11_RUN_GAME_INTEGRATION`へ分離し、以降の検証から除外した。
