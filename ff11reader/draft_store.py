"""Application draft persistence; all writes stay in the application work directory."""
from dataclasses import fields, is_dataclass
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from . import domain, editing

TYPES = {cls.__name__: cls for cls in (domain.Text, domain.Macro, domain.Slot, domain.Equipset, domain.ItemReference, editing.Change, editing.Edit)}


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


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if isinstance(value, dict):
        if set(value) == {'type', 'fields'}:
            return TYPES[value['type']](**{k: decode(v) for k, v in value['fields'].items()})
        if set(value) == {'tuple'}:
            return tuple(decode(v) for v in value['tuple'])
        return {k: decode(v) for k, v in value.items()}
    return value


def signature(snapshot):
    return sorted((str(s['path']), s['sha256']) for s in snapshot.sources)


class DraftStore:
    def __init__(self, path):
        self.path = Path(path)
        self.revision = self._revision()

    def _revision(self):
        return hashlib.sha256(self.path.read_bytes()).hexdigest() if self.path.exists() else None

    def load(self, snapshot):
        session = editing.EditSession(snapshot)
        if not self.path.exists():
            return session
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if data['version'] != 1 or data['installation'] != snapshot.installation_key or data['sources'] != [list(v) for v in signature(snapshot)]:
            raise ValueError('ゲームの読込元が変わっています。以前の作業ファイルを保管して、新しい編集を開始できます。')
        history = decode(data['history'])
        cursor = data['cursor']
        if not isinstance(cursor, int) or not 0 <= cursor <= len(history):
            raise ValueError('作業履歴の位置が不正です。')
        for edit in history:
            session.apply(edit)
        while session.cursor > cursor:
            session.undo()
        return session

    def save(self, session):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix('.lock')
        # Exclusive lock also prevents two app instances from overwriting a draft.
        handle = lock.open('x')
        try:
            if self._revision() != self.revision:
                raise ValueError('別の画面で作業ファイルが更新されました。アプリを開き直してください。')
            data = {'version': 1, 'installation': session.baseline.installation_key,
                    'sources': signature(session.baseline), 'history': encode(session.history), 'cursor': session.cursor}
            temp = self.path.with_name(self.path.name + '.' + uuid4().hex + '.tmp')
            try:
                with temp.open('x', encoding='utf-8') as stream:
                    json.dump(data, stream, ensure_ascii=False)
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
