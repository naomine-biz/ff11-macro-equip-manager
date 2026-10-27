"""Use case orchestration. UI consumes snapshots, never DAT adapters directly."""
from datetime import datetime, timezone
from uuid import uuid4
import hashlib
from pathlib import Path
from dataclasses import replace
from . import store
from .adapters import LocalReader, discover
from .domain import Snapshot
from .dictionaries import resolve_token
from .references import assess_equipment
from .codecs import BAGS, text
from .fixes import plan_fixes, apply_fixes


def prepare_game_save(snapshot, character, number):
    from .saving import prepare_save
    return prepare_save(snapshot, character, number)


def save_game_plan(plan):
    from .saving import execute_save
    return execute_save(plan, Path(__file__).resolve().parent.parent / 'backups')


def restore_game_backup(folder):
    from .saving import restore_backup
    return restore_backup(folder)


def installations():
    return [str(p) for p in discover()]


def load_snapshot(root):
    reader=LocalReader(root)
    characters=reader.load_characters()
    icon_ids={r.item_id for c in characters for r in c.inventory}
    icon_ids.update(s.item_id for c in characters for e in c.equipsets for s in e.slots if s.item_id)
    items=reader.load_items(icon_ids); phrases=reader.load_phrases()
    resolver=lambda p:resolve_token(p,phrases,items)
    for c in characters:
        c.macros=[replace(m,lines=tuple(text(bytes.fromhex(l.raw_hex),resolver)
                     if '{AT:' in l.display else l for l in m.lines)) for m in c.macros]
    changed=reader.verify_unchanged()
    if changed: raise RuntimeError('Sources changed during snapshot; reload: '+', '.join(changed))
    for c in characters:
        sources={}
        for source in reader.sources:
            path=Path(source['path'])
            if path.parent.name==c.folder_id and path.name.lower() in BAGS:
                sources[BAGS[path.name.lower()]]=dict(source)
        c.equipsets=assess_equipment(c,sources)
    installation_key=hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()
    try:
        labels=store.read_labels().get(installation_key,{})
        for c in characters:
            if isinstance(labels.get(c.folder_id),str) and labels[c.folder_id]:
                c.display_name=labels[c.folder_id]; c.identity_status='user_mapped'
    except (OSError,ValueError) as exc:
        reader.diagnostics.append({'code':'labels_unreadable','message':str(exc)})
    return Snapshot(str(uuid4()),datetime.now(timezone.utc).isoformat(),
                    characters,items,reader.sources,reader.diagnostics,installation_key)


def set_character_label(snapshot,character,name):
    name=name.strip()
    if len(name)>40: raise ValueError('名前は40文字以内で指定してください')
    if character not in snapshot.characters: raise ValueError('Unknown character')
    store.save_label(snapshot.installation_key,character.folder_id,name)
    character.display_name=name or None
    character.identity_status='user_mapped' if name else 'unknown'


def preview_reference_fixes(snapshot, character):
    if not any(c is character for c in snapshot.characters):raise ValueError('Unknown character')
    return plan_fixes(character)


def apply_reference_fixes(snapshot, character, plan):
    index=next((i for i,c in enumerate(snapshot.characters) if c is character),None)
    if index is None:raise ValueError('Unknown character')
    sources={BAGS[Path(s['path']).name.lower()]:s for s in snapshot.sources
             if Path(s['path']).parent.name==character.folder_id and Path(s['path']).name.lower() in BAGS}
    snapshot.characters[index]=apply_fixes(character,plan,sources)
    return snapshot.characters[index]
