"""Pure binary decoders. Unknown bytes retained; never encodes or writes DATs."""
import hashlib
import struct
from .domain import Text, TextToken, Macro, Slot, Equipset, InventoryRow

SLOTS = 'main sub range ammo head body hands legs feet neck waist ear1 ear2 ring1 ring2 back'.split()
BAGS = {'is.dat':0,'bs.dat':1,'cl.dat':2,'ti.dat':3,'mb.dat':4,
        'sb.dat':5,'sk.dat':6,'ca.dat':7,'wr.dat':8,'b2.dat':9,
        **{f'wr_{i}.dat':i+8 for i in range(2,9)}}
DAT_IDS = [4,5,8,7,6,9,0xD8FB,0xD8FC,0xD8FF,0xD8FD]


def text(raw, resolver=None):
    # Tokens can themselves contain zero bytes: split tokens before NUL handling.
    parts=[]; pending=bytearray(); partial=False; i=0; tokens=[]
    def flush():
        nonlocal partial
        b=bytes(pending); pending.clear()
        try: parts.append(b.decode('cp932'))
        except UnicodeDecodeError:
            parts.append(b.decode('cp932', errors='backslashreplace')); partial=True
    while i<len(raw):
        if raw[i]==0: break
        if raw[i]==0xFD and i+5<len(raw) and raw[i+5]==0xFD:
            flush(); name=resolver(raw[i+1:i+5]) if resolver else None
            label='【'+name+'】' if name else '{AT:'+raw[i+1:i+5].hex().upper()+'}'
            start=sum(map(len,parts));tokens.append(TextToken(start,start+len(label),raw[i+1:i+5].hex().upper()))
            parts.append(label)
            if not name: partial=True
            i+=6
        else: pending.append(raw[i]); i+=1
    flush()
    return Text(''.join(parts), raw.hex(), 'partial' if partial else 'cp932',tuple(tokens) or None)


def checked(data, size):
    if len(data)!=size: raise ValueError(f'Unexpected size: {len(data)} != {size}')
    if hashlib.md5(data[24:]).digest()!=data[8:24]: raise ValueError('MD5 mismatch')


def macros(data, page, resolver=None):
    checked(data,7624)
    if not 0<=page<400: raise ValueError('Invalid palette index')
    result=[]
    for n in range(20):
        b=data[24+n*380:24+(n+1)*380]
        result.append(Macro(page//10+1,page%10+1,'ctrl' if n<10 else 'alt',
                            n%10+1,text(b[370:380]),
                            tuple(text(b[4+i*61:65+i*61],resolver) for i in range(6))))
    return result


def book_titles(data, second=False):
    checked(data,344)
    return {i+1+(20 if second else 0):text(data[24+i*16:40+i*16]) for i in range(20)}


def equipsets(data, file_index):
    checked(data,1624); result=[]
    if not 0<=file_index<10: raise ValueError('Invalid equipset file index')
    for n in range(20):
        b=data[24+n*80:104+n*80]; slots=[]
        for s,name in enumerate(SLOTS):
            raw=b[16+s*4:20+s*4]; flags,index,item=struct.unpack('<BBH',raw)
            action={0:'keep',1:'equip',2:'remove',3:'unknown'}[flags&3]
            slots.append(Slot(name,action,item if action=='equip' else None,
                              flags>>2 if action=='equip' else None,
                              index if action=='equip' else None,raw.hex()))
        result.append(Equipset(file_index*20+n+1,text(b[:16]),tuple(slots)))
    return result


def inventory(data, container):
    checked(data,4240)
    if struct.unpack_from('<HH',data)!=(0x0208,4216): raise ValueError('Unknown cache header')
    result=[]
    for n in range(81):
        b=data[0xA3C+n*20:0xA3C+(n+1)*20]
        index,aux,item=struct.unpack_from('<BBH',b,16)
        if item in (0,65535): continue
        if index!=n: raise ValueError(f'Unexpected inventory index {index} at {n}')
        result.append(InventoryRow(container,index,item,raw_hex=b.hex()))
    return result


ROTATE = bytes((v>>5 | v<<3)&255 for v in range(256))


def item_records(data, icon_ids=None):
    from .icons import item_icon
    if len(data)%0x1400: raise ValueError('Unknown item master record size')
    items={}
    for start in range(0,len(data),0x1400):
        b=data[start:start+0x1400].translate(ROTATE)
        item=struct.unpack_from('<H',b)[0]
        if item in (0,65535) or item>=0x7400: continue
        pos=(0x1C if item<0x2800 else 0x30 if item<0x4000 else
             0x3C if item<0x5A00 else 0x30 if item<0x7000 else 0x54)
        count,offset,typ=struct.unpack_from('<III',b,pos)
        name=None
        if 1<=count<=16 and typ==0:
            name_start=pos+offset+0x1C
            if pos+4+count*8<=name_start<len(b):
                name=text(b[name_start:b.find(b'\0',name_start) if b'\0' in b[name_start:] else len(b)])
        items[item]={'name':name.display if name else None,
                     'name_state':name.state if name else 'unknown',
                     'type':struct.unpack_from('<H',b,10)[0],
                     'icon_png':item_icon(b) if icon_ids is not None and item in icon_ids else None}
    return items
