"""Pure local DAT dictionary decoding. No Lua execution or network access."""
import struct
from .codecs import text


def auto_translate(data, readings=None):
    result={}; pos=0
    while pos<len(data):
        if pos+4>len(data): raise ValueError('Truncated auto-translate header')
        marker,language,hi,lo=data[pos:pos+4]; pos+=4
        if marker!=2 or language not in (1,2,3,4): raise ValueError('Unknown auto-translate format')
        key=hi*256+lo
        if lo==0:
            if pos+72>len(data): raise ValueError('Truncated auto-translate category')
            name=data[pos+32:pos+64]; pos+=72
        else:
            if pos>=len(data): raise ValueError('Missing auto-translate length')
            length=data[pos]; pos+=1
            if length<1 or pos+length>len(data): raise ValueError('Invalid auto-translate length')
            name=data[pos:pos+length]; pos+=length
            if language==1:
                if pos>=len(data): raise ValueError('Missing Japanese reading length')
                length=data[pos]; pos+=1
                if pos+length>len(data): raise ValueError('Truncated Japanese reading')
                if readings is not None: readings[key]=text(data[pos:pos+length]).display
                pos+=length
        result[key]=text(name).display
    return result


def dmsg_names(data):
    if len(data)<64 or data[:8]!=b'd_msg\0\0\0': raise ValueError('Unknown d_msg format')
    version=struct.unpack_from('<Q',data,12)[0]
    size,header,table,entry,length,count=struct.unpack_from('<6I',data,20)
    if version!=0x300000003 or size!=len(data) or header!=64:
        raise ValueError('Unsupported d_msg header')
    if header+table+length>len(data): raise ValueError('Truncated d_msg data')
    if table and (table!=count*8 or entry): raise ValueError('Invalid d_msg table')
    if not table and length!=count*entry: raise ValueError('Invalid d_msg records')
    body=data[header+table:header+table+length]
    indexes=data[header:header+table]
    if data[10]:
        invert=bytes(255-i for i in range(256))
        body=body.translate(invert); indexes=indexes.translate(invert)
    result={}
    for i in range(count):
        off,n=struct.unpack_from('<II',indexes,i*8) if table else (i*entry,entry)
        if n<12 or off+n>len(body): raise ValueError('Invalid d_msg entry range')
        fields,relative,typ=struct.unpack_from('<III',body,off)
        if not fields or typ!=0: continue
        start=off+relative+28; end=body.find(b'\0',start,off+n)
        if start<off+12 or end<0: raise ValueError('Invalid d_msg name range')
        result[i]=text(body[start:end]).display
    return result


def resolve_token(payload, phrases, items):
    # Language byte does not change Japanese presentation. Only known token types.
    if len(payload)!=4 or payload[1] not in (1,2,3,4): return None
    key=int.from_bytes(payload[2:4],'big')
    if payload[0]==2:
        value=phrases.get(key)
        return value if value and not value.startswith('@') else None
    if payload[0] in (7,9,10):
        if payload[0]==9:
            if payload[2]!=255: return None
            key&=255
        if payload[0]==10:
            if payload[3]!=255: return None
            key&=0xFF00
        return items.get(key,{}).get('name')
    return None
