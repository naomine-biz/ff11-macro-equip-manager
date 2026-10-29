"""Edit use cases: coordinate pure transactions and application-owned storage."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from .editing import EditSession, plan_macro_fixes, plan_equipment_edit, edit_macro, macro_key
from .draft_store import DraftStore
from .tracing import span, traced


class Editor:
    def __init__(self, snapshot, path=None):
        self.store = DraftStore(path or Path(__file__).resolve().parent.parent / 'work' / 'drafts' / (snapshot.installation_key + '.json'))
        self.blocked = None
        try:
            self._recover_save(snapshot)
            self._session = self.store.load(snapshot)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration) as exc:
            self.blocked = str(exc)
            self._session = EditSession(snapshot)

    @property
    def session(self):
        """Detached inspection copy; mutations never publish into the editor."""
        return deepcopy(self._session)

    @traced('editor.snapshot')
    def snapshot(self, previous=None):
        return self._session.view(previous)

    @traced('editor.edit_status')
    def edit_status(self):
        return self._session.cursor,self._session.history_length(),self._session.dirty

    def prepare_macro_edit(self,character,address,title,lines):
        if self.blocked:raise ValueError(self.blocked)
        from .domain import Character
        current=Character(character)
        macro=self._session.read(character,'macros',address)
        return deepcopy(edit_macro(current,macro,title,lines))

    def _recover_save(self,snapshot):
        pending=self.store.path.with_suffix('.pending.json')
        if not pending.exists():return
        data=json.loads(pending.read_text(encoding='utf-8'))
        if data.get('draft_revision')!=self.store.revision:
            current=json.loads(self.store.path.read_text(encoding='utf-8')) if self.store.path.exists() else {}
            if all(current.get(k)==data.get(k) for k in ('version','installation','sources','baseline','history','cursor')):
                pending.unlink();return
            raise ValueError('保存途中の記録と現在の作業ファイルが一致しません。作業ファイルと復旧用のpending記録を保管して確認してください。')
        from .draft_store import signature
        if data['sources']==[list(v) for v in signature(snapshot)]:
            session=DraftStore(pending).load(snapshot)
            self.store.save(session);pending.unlink()
        else:
            self.store.load(snapshot)  # Only discard if every game source is still original.
            pending.unlink()

    def _execute(self, operation):
        if self.blocked:
            raise ValueError(self.blocked)
        if self.store.path.with_suffix('.pending.json').exists():raise ValueError('ゲームへの保存または復旧が終わるまで、編集を再開できません。')
        with span('editor.fork_session'):
            next_session = self._session.fork()
        with span('editor.apply_operation'):
            operation(next_session)
        with span('draft.save'):
            self.store.save(next_session)
        self._session = next_session

    @traced('editor.apply')
    def apply(self, edit):
        self._execute(lambda s: s.apply(edit))

    @traced('editor.undo')
    def undo(self):
        self._execute(lambda s: s.undo())

    @traced('editor.redo')
    def redo(self):
        self._execute(lambda s: s.redo())

    def macro_fixes(self, character, preview, address=None):
        current = self._session.character(character)
        if preview != plan_macro_fixes(current, self._session.item_catalog(), address):
            raise ValueError('Fix案が変わりました。プレビューを開き直してください。')
        self.apply(preview)

    def equipment_fixes(self, character, plan):
        current = self._session.character(character)
        self.apply(plan_equipment_edit(current,plan))

    @traced('editor.start_fresh')
    def start_fresh(self):
        if self.store.path.with_suffix('.pending.json').exists():
            raise ValueError('ゲーム保存の復旧記録があります。バックアップと作業ファイルを確認してください。')
        next_session = EditSession(self._session.saved)
        self.store.prepare_baseline(next_session)
        self.store.archive()
        self._session = next_session
        self.blocked = None

    @traced('editor.prepare_macro_save')
    def prepare_macro_save(self,folder,scope='storage-fix'):
        if self.blocked:raise ValueError(self.blocked)
        from .macro_saving import prepare_macro_save
        return prepare_macro_save(self._session.saved,self._session.working,folder,scope)

    @traced('editor.save_macros')
    def save_macros(self,preview,backup_root):
        from .macro_saving import execute_macro_save
        from .saving import require_game_closed
        if preview!=self.prepare_macro_save(preview.character,preview.scope):raise ValueError('編集内容が変わりました。保存プレビューを開き直してください。')
        require_game_closed()
        self.store.save(self._session)  # Verify draft ownership and writable storage first.
        next_session=self._session.fork()
        saved=next_session.saved
        character=next(c for c in saved.characters if c.folder_id==preview.character)
        changes={(change.address,change.line):change for f in preview.files for change in f.changes}
        from .editing import macro_key
        from .domain import Text
        def changed(m,n,old):
            change=changes.get((macro_key(m),n))
            return Text(change.after,change.replacement.hex(),'cp932',change.tokens) if change else old
        character.macros=[replace(m,title=changed(m,0,m.title),lines=tuple(changed(m,n,line) for n,line in enumerate(m.lines,1))) for m in character.macros]
        next_session.saved=saved
        return self._save_checkpoint(preview,backup_root,next_session,execute_macro_save)

    @traced('editor.prepare_equipment_save')
    def prepare_equipment_save(self,folder):
        if self.blocked:raise ValueError(self.blocked)
        from .equipment_saving import prepare_equipment_save
        return prepare_equipment_save(self._session.saved,self._session.working,folder)

    @traced('editor.save_equipment')
    def save_equipment(self,preview,backup_root):
        from .equipment_saving import execute_equipment_save
        from .saving import require_game_closed
        from .codecs import equipsets, BAGS
        from .references import assess_equipment
        if preview!=self.prepare_equipment_save(preview.character):raise ValueError('編集内容が変わりました。保存プレビューを開き直してください。')
        require_game_closed()
        self.store.save(self._session)
        next_session=self._session.fork()
        saved=next_session.saved
        character=next(c for c in saved.characters if c.folder_id==preview.character)
        decoded={e.number:e for f in preview.files for e in equipsets(f.replacement,f.page)}
        character.equipsets=[decoded.get(e.number,e) for e in character.equipsets]
        sources={BAGS[Path(s['path']).name]:s for s in saved.sources if Path(s['path']).parent.name==preview.character and Path(s['path']).name in BAGS}
        character.equipsets=assess_equipment(character,sources)
        next_session.saved=saved
        return self._save_checkpoint(preview,backup_root,next_session,execute_equipment_save)

    def _save_checkpoint(self,preview,backup_root,next_session,execute_save):
        from .saving import digest
        saved=next_session.saved
        for source in saved.sources:
            file=next((f for f in preview.files if Path(f.target).resolve()==Path(source['path']).resolve()),None)
            if file:source['sha256']=digest(file.replacement)
        next_session.saved=saved
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
                self.blocked='ゲームへの保存が途中で止まっています。バックアップと復旧用のpending記録を残しています。復旧確認が必要です。'
                raise RuntimeError(self.blocked+' '+str(exc)) from exc
            raise
        try:
            self.store.save(next_session)
            self._session=next_session
            pending.unlink()
        except Exception as exc:
            self.blocked=f'ゲームへの保存は完了しましたが、作業ファイルの同期に失敗しました。アプリを再起動して復旧を確認してください。バックアップ: {backup}'
            raise RuntimeError(self.blocked) from exc
        return backup
