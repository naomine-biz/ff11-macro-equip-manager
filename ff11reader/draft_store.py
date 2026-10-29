"""Application draft persistence; all writes stay in the application work directory."""
from dataclasses import fields, is_dataclass, replace
import hashlib
from .tracing import span
import json
import os
from pathlib import Path
from uuid import uuid4
from . import domain, editing

TYPES = {cls.__name__: cls for cls in (domain.TextToken, domain.Text, domain.Macro, domain.Slot, domain.Equipset, domain.ItemReference, editing.Change, editing.Edit)}


def encode(value):
    if is_dataclass(value):
        return {'type': type(value).__name__, 'fields': {f.name: encode(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, tuple):
        return {'tuple': [encode(v) for v in value]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    return value


def decode(value, resolver=None):
    if isinstance(value, list):
        return [decode(v,resolver) for v in value]
    if isinstance(value, dict):
        if set(value) == {'type', 'fields'}:
            result=TYPES[value['type']](**{k: decode(v,resolver) for k, v in value['fields'].items()})
            if isinstance(result,domain.Text) and resolver is not None:
                from .macro_text import hydrate_text
                result=hydrate_text(result,resolver)
            if isinstance(result,editing.Change) and isinstance(result.before,domain.Macro) and isinstance(result.after,domain.Macro):
                from .text_editing import remap_text
                lines=[]
                for before,after in zip(result.before.lines,result.after.lines):
                    if after.tokens is None and not after.raw_hex and before.tokens:
                        after=remap_text(before,after.display)
                    lines.append(after)
                result=replace(result,after=replace(result.after,lines=tuple(lines)))
            return result
        if set(value) == {'tuple'}:
            return tuple(decode(v,resolver) for v in value['tuple'])
        return {k: decode(v,resolver) for k, v in value.items()}
    return value


def signature(snapshot):
    return sorted((str(s['path']), s['sha256']) for s in snapshot.sources)


class DraftStore:
    def __init__(self, path):
        self.path = Path(path)
        self.revision = self._revision()
        self._baseline_token = None
        self._baseline_json = None

    def _revision(self):
        return hashlib.sha256(self.path.read_bytes()).hexdigest() if self.path.exists() else None

    def load(self, snapshot):
        session = editing.EditSession(snapshot)
        if not self.path.exists():
            self.prepare_baseline(session)
            return session
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if data['version'] not in (1,2,3) or data['installation'] != snapshot.installation_key or data['sources'] != [list(v) for v in signature(snapshot)]:
            raise ValueError('ゲームの読込元が変わっています。以前の作業ファイルを保管して、新しい編集を開始できます。')
        from .dictionaries import resolve_token
        resolver=lambda p:resolve_token(p,snapshot.phrases,snapshot.items)
        history = decode(data['history'],resolver)
        initial = session.baseline
        if data['version'] == 3:
            # History may lose a saved operation after Undo followed by branching.
            # Keep its original values even for targets absent from the new history.
            from .edit_values import character_value, validate_structure
            baseline = decode(data['baseline'],resolver)
            if set(baseline) != {c.folder_id for c in initial.characters}:
                raise ValueError('作業履歴の起点とキャラクターが一致しません。')
            for character in initial.characters:
                record = baseline[character.folder_id]
                if set(record) != {'macros', 'equipsets'}:
                    raise ValueError('作業履歴の起点の形式が不正です。')
                before = character_value(character)
                character.macros = record['macros']
                character.equipsets = record['equipsets']
                after = character_value(character)
                if any(a.keys() != b.keys() for a, b in zip(before, after)):
                    raise ValueError('作業履歴の起点と編集対象が一致しません。')
                for kind in ('macros', 'equipsets'):
                    for item in getattr(character, kind):
                        validate_structure(item, kind)
            session.baseline = initial
            session.working = initial
        elif data['version'] == 2:
            seen = set()
            for edit in history:
                for change in edit.changes:
                    identity=(change.character,change.kind,change.key)
                    if identity in seen:continue
                    seen.add(identity)
                    if change.kind not in ('macros','equipsets'):raise ValueError('Invalid draft target')
                    character=next(c for c in initial.characters if c.folder_id==change.character)
                    values=getattr(character,change.kind)
                    key=editing.macro_key if change.kind=='macros' else lambda e:(e.number,)
                    index=next(i for i,v in enumerate(values) if key(v)==change.key)
                    values[index]=change.before
            session.baseline = initial
            session.working = initial
        cursor = data['cursor']
        if not isinstance(cursor, int) or not 0 <= cursor <= len(history):
            raise ValueError('作業履歴の位置が不正です。')
        for edit in history:
            session.apply(edit)
        while session.cursor > cursor:
            session.undo()
        self.prepare_baseline(session)
        return session

    def prepare_baseline(self, session):
        if self._baseline_token is not session.baseline_token():
            encoded = json.dumps(encode(session.baseline_records()), ensure_ascii=False)
            self._baseline_json = encoded
            self._baseline_token = session.baseline_token()

    def save(self, session):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix('.lock')
        # Exclusive lock also prevents two app instances from overwriting a draft.
        handle = lock.open('x')
        try:
            if self._revision() != self.revision:
                raise ValueError('別の画面で作業ファイルが更新されました。アプリを開き直してください。')
            with span('draft.encode'):
                self.prepare_baseline(session)
                installation, sources = session.saved_header()
                data = {'version': 3, 'installation': installation,
                        'sources': sorted((str(s['path']),s['sha256']) for s in sources),
                        'history': encode(session.history), 'cursor': session.cursor}
                header = json.dumps(data, ensure_ascii=False)
            temp = self.path.with_name(self.path.name + '.' + uuid4().hex + '.tmp')
            try:
                with span('draft.write_sync'):
                    with temp.open('x', encoding='utf-8') as stream:
                        stream.write(header[:-1])
                        stream.write(', "baseline": ')
                        stream.write(self._baseline_json)
                        stream.write('}')
                        stream.flush(); os.fsync(stream.fileno())
                temp.replace(self.path)
            finally:
                temp.unlink(missing_ok=True)
            self.revision = self._revision()
        finally:
            handle.close()
            lock.unlink()

    def archive(self):
        if self.path.exists():
            self.path.rename(self.path.with_name(self.path.stem + '.archived-' + uuid4().hex + '.json'))
        self.revision = None
