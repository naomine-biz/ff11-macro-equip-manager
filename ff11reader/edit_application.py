"""Edit use cases: coordinate pure transactions and application-owned storage."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from .editing import EditSession, Edit, Change, plan_macro_fixes
from .draft_store import DraftStore
from .fixes import apply_fixes


class Editor:
    def __init__(self, snapshot, path=None):
        self.store = DraftStore(path or Path(__file__).resolve().parent.parent / 'work' / 'drafts' / (snapshot.installation_key + '.json'))
        self.blocked = None
        try:
            self._recover_save(snapshot)
            self.session = self.store.load(snapshot)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration) as exc:
            self.blocked = str(exc)
            self.session = EditSession(snapshot)

    def _recover_save(self,snapshot):
        pending=self.store.path.with_suffix('.pending.json')
        if not pending.exists():return
        data=json.loads(pending.read_text(encoding='utf-8'))
        if data.get('draft_revision')!=self.store.revision:
            current=json.loads(self.store.path.read_text(encoding='utf-8')) if self.store.path.exists() else {}
            if all(current.get(k)==data.get(k) for k in ('version','installation','sources','history','cursor')):
                pending.unlink();return
            raise ValueError('保存途中の記録と作業ファイルの更新が競合しています。作業ファイルとpending記録を保管して確認してください。')
        from .draft_store import signature
        if data['sources']==[list(v) for v in signature(snapshot)]:
            session=DraftStore(pending).load(snapshot)
            self.store.save(session);pending.unlink()
        else:
            self.store.load(snapshot)  # Only discard if every game source is still original.
            pending.unlink()

    def execute(self, operation):
        if self.blocked:
            raise ValueError(self.blocked)
        if self.store.path.with_suffix('.pending.json').exists():raise ValueError('ゲーム保存の処理・復旧確認中です。')
        next_session = deepcopy(self.session)
        operation(next_session)
        self.store.save(next_session)
        self.session = next_session

    def apply(self, edit):
        self.execute(lambda s: s.apply(edit))

    def undo(self):
        self.execute(lambda s: s.undo())

    def redo(self):
        self.execute(lambda s: s.redo())

    def macro_fixes(self, character, preview, address=None):
        current = next(c for c in self.session.working.characters if c.folder_id == character)
        if preview != plan_macro_fixes(current, self.session.working.items, address):
            raise ValueError('Fix案が変わりました。プレビューを開き直してください。')
        self.apply(preview)

    def equipment_fixes(self, character, plan):
        current = next(c for c in self.session.working.characters if c.folder_id == character)
        sources = {s.container: s.item_reference.inventory_source for e in current.equipsets for s in e.slots if s.container is not None}
        updated = apply_fixes(current, plan, sources)
        changes = tuple(Change(character, 'equipsets', (a.number,), a, b) for a, b in zip(current.equipsets, updated.equipsets) if a != b)
        self.apply(Edit('装備セットの参照Fix', changes))

    def start_fresh(self):
        if self.store.path.with_suffix('.pending.json').exists():
            raise ValueError('ゲーム保存の復旧記録があります。バックアップと作業ファイルを確認してください。')
        self.store.archive()
        self.session = EditSession(self.session.saved)
        self.blocked = None

    def prepare_macro_save(self,folder):
        if self.blocked:raise ValueError(self.blocked)
        from .macro_saving import prepare_macro_save
        return prepare_macro_save(self.session.saved,self.session.working,folder)

    def save_macros(self,preview,backup_root):
        from .macro_saving import execute_macro_save
        from .saving import require_game_closed
        if preview!=self.prepare_macro_save(preview.character):raise ValueError('編集内容が変わりました。保存プレビューを開き直してください。')
        require_game_closed()
        self.store.save(self.session)  # Verify draft ownership and writable storage first.
        next_session=deepcopy(self.session)
        saved=next_session.saved
        character=next(c for c in saved.characters if c.folder_id==preview.character)
        changes={(change.address,change.line):change for f in preview.files for change in f.changes}
        from .editing import macro_key
        from .domain import Text
        character.macros=[replace(m,lines=tuple(Text(changes[(macro_key(m),n)].after,changes[(macro_key(m),n)].replacement.hex(),'cp932') if (macro_key(m),n) in changes else line for n,line in enumerate(m.lines,1))) for m in character.macros]
        return self._save_checkpoint(preview,backup_root,next_session,execute_macro_save)

    def prepare_equipment_save(self,folder):
        if self.blocked:raise ValueError(self.blocked)
        from .equipment_saving import prepare_equipment_save
        return prepare_equipment_save(self.session.saved,self.session.working,folder)

    def save_equipment(self,preview,backup_root):
        from .equipment_saving import execute_equipment_save
        from .saving import require_game_closed
        from .codecs import equipsets, BAGS
        from .references import assess_equipment
        if preview!=self.prepare_equipment_save(preview.character):raise ValueError('編集内容が変わりました。保存プレビューを開き直してください。')
        require_game_closed()
        self.store.save(self.session)
        next_session=deepcopy(self.session)
        character=next(c for c in next_session.saved.characters if c.folder_id==preview.character)
        decoded={e.number:e for f in preview.files for e in equipsets(f.replacement,f.page)}
        character.equipsets=[decoded.get(e.number,e) for e in character.equipsets]
        sources={BAGS[Path(s['path']).name]:s for s in next_session.saved.sources if Path(s['path']).parent.name==preview.character and Path(s['path']).name in BAGS}
        character.equipsets=assess_equipment(character,sources)
        return self._save_checkpoint(preview,backup_root,next_session,execute_equipment_save)

    def _save_checkpoint(self,preview,backup_root,next_session,execute_save):
        from .saving import digest
        saved=next_session.saved
        for source in saved.sources:
            file=next((f for f in preview.files if Path(f.target).resolve()==Path(source['path']).resolve()),None)
            if file:source['sha256']=digest(file.replacement)
        pending=self.store.path.with_suffix('.pending.json')
        if pending.exists():raise ValueError('前回のゲーム保存の復旧確認が必要です。')
        DraftStore(pending).save(next_session)
        data=json.loads(pending.read_text(encoding='utf-8'));data['draft_revision']=self.store.revision
        from .saving import atomic_replace
        atomic_replace(pending,json.dumps(data,ensure_ascii=False).encode('utf-8'))
        try:
            backup=execute_save(preview,backup_root)
        except Exception as exc:
            try:unchanged=all(Path(f.target).read_bytes()==f.original for f in preview.files)
            except OSError:unchanged=False
            if unchanged:pending.unlink()
            else:
                self.blocked='ゲーム保存の復旧確認が必要です。バックアップとpending記録を保持しています。'
                raise RuntimeError(self.blocked+' '+str(exc)) from exc
            raise
        try:
            self.store.save(next_session)
            self.session=next_session
            pending.unlink()
        except Exception as exc:
            self.blocked=f'ゲームへの保存は完了しました。作業状態の再開確認が必要です。バックアップ: {backup}'
            raise RuntimeError(self.blocked) from exc
        return backup
