# 要件と実装・検証の対応

2026-10-29、コミット`f7c69de`を基準に、保存時の権限要求の追加と、この会話での実機確認まで反映した索引。動作の正本は[requirements.md](../requirements.md)、内部の制約は[設計条件](design-constraints.md)。将来要件のコード欄は関連する既存基盤を示す。

実装状態・合成テスト・実機確認を分けて記載する。今回の文書整理ではテストを再実行していない。過去の監査で解消した問題は回帰テストへの対応として残し、当時の予定・途中経過は現在の残件に置き換えた。

## 要件からコード・テストへの索引

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
| [EDIT-005](../requirements.md#edit-005) | [draft_store.py](../ff11reader/draft_store.py)、[edit_application.py](../ff11reader/edit_application.py) | [EditingTests.test_corrupt_draft_is_preserved](../tests/test_editing.py) | 古い作業の保管と新Snapshotでの再開はProperty Testでも検証。起動中の再読込UIと選択的引継ぎは未実装 |
| [EDIT-006](../requirements.md#edit-006) | [editing.py](../ff11reader/editing.py)、[edit_application.py](../ff11reader/edit_application.py)、[ui.py](../ff11reader/ui.py) | [EditingUITests.test_edit_preview_undo_redo_fix_and_reopen](../tests/test_editing_ui.py) | マクロ編集と[装備セット名の編集・履歴・保存](../tests/test_equipment_names.py)を合成データで検証。[装備枠の個別編集・部位別選択・履歴・保存](../tests/test_equipment_slots.py)も合成データで検証。2026-10-29にユーザーが各枠編集の保存後、ゲーム内で認識されることを確認済み。2026-10-29にユーザーが名前編集・Undo/Redoと保存後のゲーム内反映を確認済み |
| [EDIT-007](../requirements.md#edit-007) | [phrases.py](../ff11reader/phrases.py)、[text_editing.py](../ff11reader/text_editing.py)、[phrase_ui.py](../ff11reader/phrase_ui.py)、[macro_text.py](../ff11reader/macro_text.py) | [test_phrase_editing.py](../tests/test_phrase_editing.py) | 通常定型文・アイテム名の検索、読み、カテゴリ階層、初期フォーカス、ID保持を実装。2026-10-29に実機確認まで完了。詳細は下記「定型文入力」を参照 |
| [SAVE-001](../requirements.md#save-001) | [save_plan.py](../ff11reader/save_plan.py)、[macro_saving.py](../ff11reader/macro_saving.py)、[equipment_saving.py](../ff11reader/equipment_saving.py)、[ui.py](../ff11reader/ui.py) | [MacroSavingTests.test_unrelated_manual_edits_are_retained](../tests/test_macro_saving.py) | Fix限定保存と保留に加え、[test_manual_macro_saving.py](../tests/test_manual_macro_saving.py)で名前・各行の一般保存を検証。[test_equipment_names.py](../tests/test_equipment_names.py)で装備セット名の単独保存・Fixとの混在・保留を検証 |
| [SAVE-002](../requirements.md#save-002) | [macro_saving.py](../ff11reader/macro_saving.py)、[equipment_saving.py](../ff11reader/equipment_saving.py)、[file_transaction.py](../ff11reader/file_transaction.py) | [MacroSavingTests.test_stale_macro_inventory_and_plan_tamper_rejected](../tests/test_macro_saving.py) | マクロの競合を検証。装備保存にも同等テストあり |
| [SAVE-003](../requirements.md#save-003) | [file_transaction.py](../ff11reader/file_transaction.py) | [EquipmentSavingTests.test_candidate_changes_and_staging_failure](../tests/test_equipment_saving.py) | 装備保存の準備失敗を検証 |
| [SAVE-004](../requirements.md#save-004) | [macro_saving.py](../ff11reader/macro_saving.py)、[saving.py](../ff11reader/saving.py)、[codecs.py](../ff11reader/codecs.py) | [MacroSavingTests.test_token_zero_bytes_japanese_padding_and_length_limit](../tests/test_macro_saving.py) | [macro_text.py](../ff11reader/macro_text.py)で手編集のCP932・上限・既存定型文保持も検証。通常定型文・アイテム名の新規挿入とID保持は合成保存で検証。通常定型文とアイテム名のゲーム内表示・使用はユーザー確認済み |
| [SAVE-005](../requirements.md#save-005) | [file_transaction.py](../ff11reader/file_transaction.py)、[edit_application.py](../ff11reader/edit_application.py) | [EquipmentSavingTests.test_failed_rollback_keeps_pending_and_blocks_edits](../tests/test_equipment_saving.py) | 復旧待ちを検証。外部更新は復元テストも参照 |
| [SAVE-006](../requirements.md#save-006) | [edit_application.py](../ff11reader/edit_application.py)、[draft_store.py](../ff11reader/draft_store.py) | [MacroSavingTests.test_draft_checkpoint_failure_recovers_on_restart](../tests/test_macro_saving.py) | 同期失敗を検証。保存後Undoは保存テストでも検証 |
| [VIEW-001](../requirements.md#view-001) | [ui.py](../ff11reader/ui.py) | — | 専用自動テストなし。画面で確認する |
| [VIEW-002](../requirements.md#view-002) | [ui.py](../ff11reader/ui.py)、[presentation.py](../ff11reader/presentation.py) | [PresentationTests.test_four_main_actions](../tests/test_presentation.py) | 状態表示の分類を検証。視覚品質は手動確認 |
| [VIEW-003](../requirements.md#view-003) | [ui.py](../ff11reader/ui.py)、[dialogs.py](../ff11reader/dialogs.py) | [test_dialogs.py](../tests/test_dialogs.py) | 親画面内モーダル、取消・入力、フォーカスとgrabの復帰、長文、起動時の表示を合成Tkで検証。実機で起動通知・再読込操作・本文量に応じたサイズをユーザーが確認済み |
| [WARD-001](../requirements.md#ward-001) | [wardrobe_usage.py](../ff11reader/wardrobe_usage.py) | [WardrobeUsageTests.test_scope_and_both_reference_sources](../tests/test_wardrobe_usage.py) | 参照元と対象収納を検証 |
| [WARD-002](../requirements.md#ward-002) | [wardrobe_usage.py](../ff11reader/wardrobe_usage.py) | [WardrobeUsageTests.test_edit_and_undo_recompute_without_cross_character_references](../tests/test_wardrobe_usage.py) | 再計算とキャラ分離を検証 |
| [FUT-001](../requirements.md#fut-001) | [editing.py](../ff11reader/editing.py)、[save_plan.py](../ff11reader/save_plan.py) | — | 未実装。衝突・上書き・入替えの規則は着手前に確定する |
| [FUT-002](../requirements.md#fut-002) | — | — | 未実装。参照セットの同時コピーと番号衝突の扱いは未決定 |
| [FUT-003](../requirements.md#fut-003) | [macro_inventory.py](../ff11reader/macro_inventory.py) | — | /equipの参照判定は実装済み。定型文候補の名前検索は実装済み。種類IDによる参照調査と誤記検出は未実装で、範囲・判定規則は未決定 |
| OBS-001 | [tracing.py](../ff11reader/tracing.py)、[edit_application.py](../ff11reader/edit_application.py) | [test_tracing.py](../tests/test_tracing.py) | 親子の操作ID・所要時間・失敗・個人データ非記録を検証。ゲーム保存内部の詳細区間は未実装 |
| PERF-001 | [edit_state.py](../ff11reader/edit_state.py)、[draft_store.py](../ff11reader/draft_store.py)、[ui.py](../ff11reader/ui.py) | [test_persistent_edit_state.py](../tests/test_persistent_edit_state.py)、[benchmark_editor.py](../experiments/benchmark_editor.py) | 所有権・共有・作業保存失敗を検証。実機の応答はユーザー確認済み。数値基準は未確定 |

## 現在の未完了項目

| 要件 | 現在できること | 残件 |
|---|---|---|
| DATA-001 | キャラ別の閲覧・表示名・切替 | アカウント単位の整理 |
| DATA-003 | 取得不可として扱い、参照一致条件から除外 | オーグメント取得は保留。メモリ読取の導入は別途合意 |
| EDIT-005 | 再起動時の最新読込、旧作業の保管と再開 | 起動中の再読込UI、選択的引継ぎ。リセット単独ではファイルを読み直さない |
| FUT-001 | 一括変更とUndo/Redoの基盤 | 移動、参照カスケード、依存グループ単位の保存。衝突・上書き・入替え規則の確定 |
| FUT-002 | キャラ別の参照判定 | キャラ間コピー。参照セットの同時コピーと番号衝突の扱いの確定 |
| FUT-003 | /equipの参照判定、定型文候補の名前検索 | 種類IDによる参照調査、誤記検出。辞書未解決と未所持の区別・候補規則の確定 |
| OBS-001 | 編集・作業保存・画面更新・ゲーム保存入口の区間計測 | ゲーム保存内部の詳細区間 |
| PERF-001 | 永続Mapによる編集高速化、待機カーソル。実機の応答をユーザー確認済み | 数値の合格基準。初期読込・全体取得・作業ファイル全体書出しのデータ量依存 |

## 定型文入力（EDIT-007、D-09、SAVE-004）

| 対応 | 実装 | 検証 |
|---|---|---|
| 読み・名前の全体検索 | `dictionaries.auto_translate` → `LocalReader.phrase_readings` → `Snapshot.phrase_readings` → `PhraseCatalog` | [test_phrase_readings.py](../tests/test_phrase_readings.py)。ひらがな・カタカナ・漢字、読みの保持、かな名の検索 |
| カテゴリ階層・順序・名称 | [phrase_categories.py](../ff11reader/phrase_categories.py)、[phrases.py](../ff11reader/phrases.py) | 同テスト。魔法→アビリティ→アイテム→装備関連→その他、辞書カテゴリの統合、未知カテゴリ・同名別IDの保持 |
| キーボード操作 | [phrase_ui.py](../ff11reader/phrase_ui.py)。Tab直後は大分類へフォーカス。「すべて」でEnterなら全体検索欄へ移動 | 同テストと[test_phrase_editing.py](../tests/test_phrase_editing.py)。選択・検索・挿入・取消・フォーカス遷移 |
| アイテム候補 | [item_tokens.py](../ff11reader/item_tokens.py)、`PhraseCatalog` | [test_item_phrases.py](../tests/test_item_phrases.py)。ID逆変換、同名別ID、空名除外、Tabからの挿入。読みは補完しない |
| 編集値・履歴・保存 | `TextToken`、[text_editing.py](../ff11reader/text_editing.py)、[edit_values.py](../ff11reader/edit_values.py)、[macro_text.py](../ff11reader/macro_text.py)、[draft_store.py](../ff11reader/draft_store.py) | test_phrase_editing.py、test_item_phrases.py。同表示のID変更、原子的置換・削除、Undo/Redo、旧作業互換、合成保存・再読込 |

ユーザー確認済み: カテゴリ階層での選択、アイテム名の検索・挿入、Tab直後の大分類フォーカス。2026-10-29、ユーザーがIME変換の確定ではマクロへ挿入されず、候補選択で挿入されることを確認。さらにユーザー自身が保存し、通常定型文とアイテム名の両方がゲーム内で正しく表示され使用できることを確認した。EDIT-007は実装・実機確認ともに完了。今回の完了更新ではアシスタントはゲームデータにアクセスしていない。漢字のあるアイテム名は表示名で検索し、読みデータを持つ通常定型文は読みでも検索する。

## 編集・保存の現行経路

マクロ名と6行の一般保存、およびマクロ収納番号Fix・装備位置Fixを実装。`macro_saving.py`と`equipment_saving.py`はプレビューと保存前の再検証を行い、`file_transaction.py`へバックアップ・置換・検証・復旧を委譲する。旧CLIも同じ実行処理を使用する。装備セット名・各枠の個別編集と保存も実装し、ゲーム内反映をユーザー確認済み。移動に伴う依存グループ保存は残件。

`macro_text.py`はCP932、名前8バイト・行60バイト、選択した定型文ID、元バイトを検証する。定型文を含む変更は辞書を依存資料として確認する。通常文字による名前変更へFix専用の持ち物一意性条件を要求しない。関連検証は[test_manual_macro_saving.py](../tests/test_manual_macro_saving.py)、[test_macro_saving.py](../tests/test_macro_saving.py)、[test_equipment_saving.py](../tests/test_equipment_saving.py)、定型文テスト群。

ユーザーはマクロ収納番号Fix、マクロ手編集、装備位置Fixのゲーム反映を以前に確認済み。今回追加した定型文のゲーム反映確認とは区別する。

編集ストアは`immutables.Map`を採用済み。`edit_state.py`内の所有値を置換して共有し、公開値は独立した値として渡す。`draft_store.py`はv3形式で履歴起点を保持する。保存→Undo→分岐→再開の不一致は修正済みで、`test_saved_undo_branch_reopen_regression`が回帰を検出する。v1/v2読込は維持するが、過去に失われた履歴情報の復元は対象外。

## 解消済みの参照・保存の不整合

| 差分 | 修正 | 回帰テスト |
|---|---|---|
| GAP-01 | 明示収納の一意参照をその収納の資料で判定。全収納の完全性は番号追加・変更案で要求 | [test_reference_regressions.py](../tests/test_reference_regressions.py): test_explicit_storage_match_is_local、test_unrelated_invalid_candidate_does_not_hide_explicit_match（MAC-002、PT-09） |
| GAP-02 | ItemReferenceへreason/fix_targetを追加。assess_equipmentが評価し、Fix計画と表示が利用 | 同ファイル: test_slot_and_plan_share_blocking_reason、test_slot_owns_unique_target_and_exact_match_priority（EQ-004、D-01、EX-E08〜10、PT-03〜06） |
| GAP-03 | [inventory_observation.py](../ff11reader/inventory_observation.py)で収納読込・有効位置・重複検査を共有。使用状況は不正観測を先に保留 | 同ファイル: test_usage_never_confirms_invalid_observation（WARD-001、PT-30） |
| GAP-04 | Fix指紋をキー順の意味上の値で構築し、raw_hexを除外。変更案と保留一覧の順序も固定 | 同ファイル: test_fix_preview_ignores_order_and_raw_metadata（D-02、PT-02）。候補変更時の拒否も検証 |
| GAP-05 | 旧CLIのexecute_saveもexecute_batchへ委譲。original.datと旧receipt形式を維持し、検証失敗の復元・外部更新保護を共通化 | [test_saving.py](../tests/test_saving.py): test_legacy_save_delegates_to_shared_transaction、test_post_write_decode_failure_rolls_back_legacy_save、test_legacy_rollback_preserves_external_update（D-05、SAVE-003〜005） |

## 生成テストの実装範囲

| 仕様 | 実装 | 検証範囲 |
|---|---|---|
| PT-13 | [test_editing_properties.py](../tests/test_editing_properties.py) | 異なる対象を含む変更案に、古い前提・欠落対象・不正構造・重複を混ぜ、順序を変えて全体拒否と作業ファイル不変を確認 |
| PT-14/15/17 | 同ファイル | 複数キャラのマクロ・装備枠編集、一括Fix、Undo/Redo、無変更、分岐、作業保存失敗、任意位置での再開。値辞書と履歴カーソルの独立モデルで各操作後を照合 |
| PT-16/20/27 | [test_saving_properties.py](../tests/test_saving_properties.py) | 一部Fix・一括Fix・名前の手編集・保存・Undo/Redo・再開・保存失敗を混在。保存可能差分と保留を分け、保存済み値・履歴・dirty・実バイトを照合 |
| PT-18 | test_editing_properties.py | 新しいSnapshotで起動して旧作業を保管する経路。起動中のファイル再読込は対象外 |
| PT-21 | test_saving_properties.py | 対象ファイル・収納・working・保存案・偽のゲーム起動状態を変更し、置換前の拒否を確認 |
| PT-22 | 同ファイル | マクロ/装備の1〜3ファイルについて、全バックアップ・一時ファイルの作成/fsync/読込検証地点へ障害注入。計72ケース。全準備が最初の置換に先行することをイベント列で確認 |
| PT-23 | 同ファイル | ページ・マクロ座標・行・装備セット内位置・部位・移動先収納をseedで変える。固定オフセットから独立に作った期待バイト、MD5、対象外バイトと照合 |
| PT-24 | 同ファイル | 現行の収納番号Fixについて、CP932の1/2バイト文字、内部ゼロを含む既知トークン、保存後59/60/61バイトを生成。この生成器は収納番号Fixが対象。手編集と新規定型文はtest_manual_macro_saving.py、test_phrase_editing.py、test_item_phrases.pyで別途検証 |
| PT-25 | 同ファイル | 3ファイルの各置換前後・検証地点の失敗、形式を保持した外部更新、復元失敗と操作停止を確認 |
| PT-26 | 同ファイル | 最初の書込前、各置換後、作業同期の前後、pending削除前で通常の例外復元を通らない中断を注入。全原本・全予定出力・混在を区別して再開を確認 |

[property_support.py](../tests/property_support.py)に固定seed、独立モデルとの照合、失敗操作列の縮小・再現記録、合成ルート外I/Oの拒否を実装済み。[test_property_support.py](../tests/test_property_support.py)で隔離と縮小を検証する。仕様の全項目を網羅したという意味ではなく、上表は各生成器が扱う範囲を示す。

## 追加検証・仕様確認が残る箇所

| 対象 | 現状と残件 |
|---|---|
| LINK-001/002、PT-08（旧SPEC-01） | `macro_links.py`の逆参照一覧は`not is_empty`を使うため、未知動作・欠落枠のあるセットも含む。PT-08の「既知の非空」との関係を要件で確定し、コードとテストをそろえる。今回の整理で解消済みにはしない |
| PT-01〜12、PT-30/31 | 参照・Fix・使用状況の固定例と前節の回帰はある。読込状態・重複位置・候補数・順序を組み合わせる広い生成検証が残る |
| PT-19、PT-32〜34 | 装備手動選択・移動・コピー・参照検索の機能実装に合わせて生成器を追加する |
| PT-24、PT-AT | 手編集・定型文の境界と固定seed生成は実装済み。辞書更新・全文字列形式の網羅や、OSの実ロック・停電などは検証範囲外 |
| VIEW-001〜003、MAC-004 | 合成GUIとユーザーによる実機確認はある。アコーディオン・空行減光・Fix初期フィルター・ホバー反復などの専用自動検証は部分的 |
| EX/PT全体 | 代表テストと主要生成器の対応を本書に記載。すべてのEX/PTを個別に網羅した対応付けは残る。ケース数とテストメソッド数を同一視しない |

合成GUIは`FF11_RUN_INTEGRATION`、実ゲームを読む`test_ui.py`は`FF11_RUN_GAME_INTEGRATION`へ分離済み。共通I/O隔離はProperty Test用基盤に実装している。全テストへの隔離適用まで完了したとは扱わない。

## アプリ内通知・応答・計測

- `dialogs.py`に通知・確認・入力を集約。初回Map後に通知することで起動時の未表示を解消。短文は本文量に合わせ、長文は上限でスクロールする。[test_dialogs.py](../tests/test_dialogs.py)で初回表示・取消・入れ子・サイズ・フォーカス復帰を検証。実機の通知とサイズはユーザー確認済み。
- `ui_actions.ActionButton(busy=True)`で保存・保存プレビュー・編集適用などに待機表示を明示指定。通常のUIイベントへのフックは撤去。`tests/test_ui_actions.py`で軽い操作に待機処理が入らないこと、キー実行、入れ子・例外・子ウィンドウ破棄・ダイアログ入力待ちを検証。
- `tracing.py`は操作ID・親子区間・所要時間・成否を記録。ログは`work/logs/timings.jsonl`、約2MBで過去3世代を保持。ゲーム保存内部の詳細区間は残件。
- 永続Map導入後の記録済み合成計測は8,000マクロで編集26.1ms、Undo26.1ms、Redo25.4ms（繰返し5回の中央値）。作業保存・表示用データ更新・dirty判定を含み、GUI描画・ゲーム保存を含まない。再現用は[benchmark_editor.py](../experiments/benchmark_editor.py)。実機の応答はユーザーが十分と確認済み。数値の合格基準は未確定。

## 直近の検証記録

- `ffe9e8d`のコミット前: `FF11_RUN_INTEGRATION=1`で全体176件中175件成功・実ゲーム用1件スキップ。保存先は合成データ。
- 初期フォーカス変更（`f7c69de`）: 定型文・読み・アイテムの関連19件成功。その後、ユーザーがTabから大分類を選ぶ操作を確認。
- この文書整理では、上記の結果と現行ソースを照合した。コード・テスト・ゲームデータは変更せず、新しい実行結果は追加していない。

[Example Test仕様](../tests/specs/example-tests.md)・[Property Test仕様](../tests/specs/property-tests.md)は要件から導いた検証仕様。[ローカル形式](reference/local-formats.md)・[調査根拠](reference/sources.json)はバイナリ処理の根拠として参照する。

## 保存時の権限要求（SAVE-003/005/006）

`edit_application._save_checkpoint` → `elevation.execute_with_permission` → `save_helper.py`。マクロ・装備セットの画面保存で共通使用する。権限不足かつ全原本未変更の場合にUACを要求し、補助プロセスで既存保存関数を再実行する。要求はハッシュ照合付きJSON。親側は完了記録・バックアップ・保存後バイトを検証する。`tests/test_elevation.py`で両保存形式、取消・再試行、要求改変、競合、結果欠落からの復旧、Windows起動APIへの引数を合成データとモックで検証。実際のUAC表示・承認後のゲーム保存は未確認。

権限要求の検証結果: 全体回帰183件は既存の権限エラー期待1件がUAC取消応答で失敗、実ゲーム用1件スキップ。他181件は成功。該当テストを取消の模擬へ修正し、補助プロセスの単体起動も追加した後、権限要求・装備保存・マクロ保存・編集GUI・定型文・アイテムの関連48件が成功。実ゲームへの書込みは実施していない。


待機表示の適用範囲を見直した後、共通アクション・ダイアログ・編集GUI・定型文・読み・アイテムの関連34件が成功。全イベントの待機処理は撤去済み。ゲームデータは使用していない。

起動表示（VIEW-003、D-10）: [startup.py](../ff11reader/startup.py)で初回表示後に読込・履歴復元を開始。[test_startup.py](../tests/test_startup.py)で表示中の応答、完了引渡し、起動エラー、途中終了を合成データで検証。

装備枠編集（EDIT-006、SAVE-001〜006）: [equipment_editing.py](../ff11reader/equipment_editing.py)が候補と選択検証、[equipment_ui.py](../ff11reader/equipment_ui.py)が入力、[equipment_saving.py](../ff11reader/equipment_saving.py)が形式変換と依存資料の検証を担当する。[test_equipment_slots.py](../tests/test_equipment_slots.py)で複数候補の手動選択、keep/remove、再開と保存、辞書・収納の競合、ロールバック、合成GUI、PT-EQSの240ケースを検証。
