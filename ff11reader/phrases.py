"""Local phrase catalog and deterministic search, independent of widgets and I/O."""
from dataclasses import dataclass
import unicodedata
from .phrase_categories import GROUPS, category_info, category_order


def normalize(value):
    value=unicodedata.normalize('NFKC',value).casefold().strip()
    return ''.join(chr(ord(c)-0x60) if 'ァ'<=c<='ヶ' else c for c in value)


def near(a,b):
    """Levenshtein distance at most one, bounded linear work."""
    if abs(len(a)-len(b))>1:return False
    if len(a)>len(b):a,b=b,a
    i=j=errors=0
    while i<len(a) and j<len(b):
        if a[i]==b[j]:i+=1;j+=1;continue
        errors+=1
        if errors>1:return False
        if len(a)==len(b):i+=1
        j+=1
    return errors+(len(a)-i)+(len(b)-j)<=1


@dataclass(frozen=True)
class Phrase:
    identity: str
    name: str
    category: str
    group: str = 'その他'

    @property
    def label(self):return '【'+self.name+'】'


class PhraseCatalog:
    def __init__(self,phrases,readings=None,items=None):
        readings=readings or {}
        self.entries=tuple((Phrase(f'0201{key:04X}',name,category_info(phrases.get(key&0xff00,'その他'))[1],category_info(phrases.get(key&0xff00,'その他'))[0]),
                            tuple(dict.fromkeys(normalize(v) for v in (name,readings.get(key,'')) if v.strip())))
            for key,name in sorted(phrases.items()) if isinstance(key,int) and 0<key<65536 and key%256
            and isinstance(name,str) and name.strip() and not name.startswith('@'))
        from .item_tokens import item_identity
        self.entries+=tuple((Phrase(item_identity(key),item['name'],'アイテム名','アイテム'),(normalize(item['name']),))
            for key,item in sorted((items or {}).items()) if isinstance(key,int) and 0<key<0x7400
            and isinstance(item.get('name'),str) and item['name'].strip() not in ('','.')
            and item.get('name_state','cp932')=='cp932')
        self.categories=category_order({phrase.category for phrase,_ in self.entries})
        self.groups=tuple(group for group,_ in GROUPS if any(p.group==group for p,_ in self.entries))

    def categories_for(self,group):
        return tuple(c for c in self.categories if any(p.category==c and p.group==group for p,_ in self.entries))

    def search(self,query,category=None,group=None):
        query=normalize(query);found=[]
        for phrase,names in self.entries:
            if group is not None and phrase.group!=group:continue
            if category is not None and phrase.category!=category:continue
            ranks=[0 if query==name else 1 if name.startswith(query) else 2 if query in name
                   else 3 if len(query)>=2 and near(query,name) else 4 for name in names]
            rank=min(ranks)
            if rank<4:found.append((rank,names[0],phrase.identity,phrase))
        return tuple(row[-1] for row in sorted(found))
