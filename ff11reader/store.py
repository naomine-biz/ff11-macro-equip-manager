"""Application-owned labels only; never stores labels inside the game folder."""
import json
from pathlib import Path

LABELS = Path(__file__).resolve().parent.parent/'character-labels.json'


def read_labels():
    if not LABELS.exists(): return {}
    value=json.loads(LABELS.read_text(encoding='utf-8'))
    if not isinstance(value,dict): raise ValueError('Invalid character labels file')
    return value


def save_label(installation_key,folder,name):
    labels=read_labels(); labels.setdefault(installation_key,{})[folder]=name
    temp=LABELS.with_suffix('.tmp')
    temp.write_text(json.dumps(labels,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(LABELS)
