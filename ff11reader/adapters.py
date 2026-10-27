"""Read-only source adapter. All source handles are opened in rb mode."""
import hashlib
from pathlib import Path
import re
import struct
from . import codecs
from .domain import Character
from . import dictionaries


def discover():
    import winreg
    roots=[]
    for region in ('PlayOnline','PlayOnlineUS','PlayOnlineEU'):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                 rf'SOFTWARE\{region}\InstallFolder',0,
                 winreg.KEY_READ|winreg.KEY_WOW64_32KEY) as key:
                p=Path(winreg.QueryValueEx(key,'0001')[0]).resolve()
                if (p/'USER').is_dir() and p not in roots: roots.append(p)
        except OSError: pass
    return roots


class LocalReader:
    def __init__(self, root):
        self.root=Path(root).resolve(); self.sources=[]; self.diagnostics=[]

    def read(self,path):
        path=path.resolve()
        if not path.is_relative_to(self.root): raise ValueError('Source outside installation')
        before=path.stat()
        with path.open('rb') as f: data=f.read()
        after=path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise ValueError('File changed during read; retry loading')
        self.sources.append({'path':str(path),'size':len(data),
            'mtime_ns':after.st_mtime_ns,'sha256':hashlib.sha256(data).hexdigest()})
        return data

    def guarded(self,path,decode):
        try: return decode(self.read(path))
        except (OSError,ValueError,struct.error) as exc:
            self.diagnostics.append({'code':'source_unreadable','path':str(path),'message':str(exc)})
            return None

    def load_items(self, icon_ids=None):
        items={}; table=self.guarded(self.root/'FTABLE.DAT',lambda b:b)
        if table is None: return items
        for logical in codecs.DAT_IDS:
            if logical*2+2>len(table):
                self.diagnostics.append({'code':'master_table_truncated','logical_id':logical}); continue
            packed=struct.unpack_from('<H',table,logical*2)[0]
            result=self.guarded(self.root/'ROM'/str(packed>>7)/f'{packed&127}.DAT',lambda b:codecs.item_records(b,icon_ids))
            if result: items.update(result)
        return items

    def load_phrases(self):
        table=self.guarded(self.root/'FTABLE.DAT',lambda b:b)
        if table is None: return {}
        def read_dat(logical,decode):
            if logical*2+2>len(table): raise ValueError('Truncated FTABLE')
            packed=struct.unpack_from('<H',table,logical*2)[0]
            return self.guarded(self.root/'ROM'/str(packed>>7)/f'{packed&127}.DAT',decode) or {}
        phrases=read_dat(0xD8F9,dictionaries.auto_translate)
        linked={key:read_dat(logical,dictionaries.dmsg_names)
                for key,logical in {'A':0xD8EF,'C':0xD91E,'J':0xD8F0,'Y':0xD91D}.items()}
        for key,value in list(phrases.items()):
            if re.fullmatch(r'@[ACJY][0-9A-Fa-f]+',value):
                phrases[key]=linked[value[1]].get(int(value[2:],16),value)
        return phrases

    def load_characters(self, resolver=None):
        result=[]
        for folder in sorted((self.root/'USER').iterdir()):
            if not folder.is_dir() or not re.fullmatch('[0-9a-fA-F]+',folder.name): continue
            c=Character(folder.name); result.append(c)
            c.inventory_coverage={bag:'missing' for bag in codecs.BAGS.values()}
            for path in sorted(folder.iterdir()):
                if not path.is_file(): continue
                name=path.name.lower(); decoded=None
                match=re.fullmatch(r'mcr([1-9][0-9]{0,2})?\.dat',name)
                if match and int(match[1] or 0)<400:
                    page=int(match[1] or 0)
                    decoded=self.guarded(path,lambda b:codecs.macros(b,page,resolver))
                    if decoded is not None: c.macros.extend(decoded)
                elif name in ('mcr.ttl','mcr_2.ttl'):
                    decoded=self.guarded(path,lambda b:codecs.book_titles(b,name=='mcr_2.ttl'))
                    if decoded is not None: c.books.update(decoded)
                elif re.fullmatch(r'es[0-9]\.dat',name):
                    decoded=self.guarded(path,lambda b:codecs.equipsets(b,int(name[2])))
                    if decoded is not None: c.equipsets.extend(decoded)
                elif name in codecs.BAGS:
                    decoded=self.guarded(path,lambda b:codecs.inventory(b,codecs.BAGS[name]))
                    c.inventory_coverage[codecs.BAGS[name]]='loaded' if decoded is not None else 'unreadable'
                    if decoded is not None: c.inventory.extend(decoded)
            c.macros.sort(key=lambda m:(m.book,m.palette,m.bank!='ctrl',m.key))
            c.equipsets.sort(key=lambda s:s.number)
        return result

    def verify_unchanged(self):
        changed=[]
        for entry in self.sources:
            p=Path(entry['path']); stat=p.stat()
            with p.open('rb') as f: digest=hashlib.sha256(f.read()).hexdigest()
            if digest!=entry['sha256'] or stat.st_mtime_ns!=entry['mtime_ns']:
                changed.append(str(p))
        return changed
