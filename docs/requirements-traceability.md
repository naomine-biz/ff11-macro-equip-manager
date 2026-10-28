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
