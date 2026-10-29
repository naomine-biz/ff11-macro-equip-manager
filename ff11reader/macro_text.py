"""Strict macro-field encoding with original auto-translate token identities."""
import re
from .codecs import text

TOKEN_DISPLAY = re.compile(r'【[^【】]*】|\{AT:[0-9A-Fa-f]{8}\}',re.IGNORECASE)


def segments(raw, resolver):
    parts=[];plain=bytearray();i=0
    def flush():
        if plain:
            parts.append((bytes(plain).decode('cp932',errors='strict'),bytes(plain),False))
            plain.clear()
    while i<len(raw) and raw[i]:
        if raw[i]==0xFD:
            if i+5>=len(raw) or raw[i+5]!=0xFD:raise ValueError('定型文トークンが壊れています。')
            flush();token=raw[i:i+6];name=resolver(token[1:5])
            parts.append(('【'+name+'】' if name else '{AT:'+token[1:5].hex().upper()+'}',token,True));i+=6
        else:
            size=2 if 0x81<=raw[i]<=0x9f or 0xe0<=raw[i]<=0xfc else 1
            part=raw[i:i+size]
            if len(part)!=size or 0 in part:raise ValueError('元の文字列が途中で切れています。')
            plain.extend(part);i+=size
    flush()
    return parts


def patch_text(raw, before, after, resolver, *, title=False, provenance=b''):
    width,limit=(10,8) if title else (61,60)
    if len(raw)!=width:raise ValueError('マクロ文字列の保存領域が不正です。')
    if any(c in after for c in ('\r','\n','\0')):raise ValueError('改行・NULを保存できません。')
    if text(raw,None if title else resolver).display!=before:raise ValueError('元の文字列と表示が一致しません。')
    if before==after:return raw
    try:
        if title:
            if TOKEN_DISPLAY.search(after):raise ValueError('マクロ名への定型文入力は未対応です。')
            payload=after.encode('cp932',errors='strict')
        else:
            source=provenance or raw
            if len(source)!=width:raise ValueError('編集元の文字列の保存領域が不正です。')
            parts=segments(source,resolver)
            tokens={};literal=set()
            for display,encoded,is_token in parts:
                if is_token:tokens.setdefault(display,set()).add(encoded)
                else:literal.update(m.group() for m in TOKEN_DISPLAY.finditer(display))
            pieces=[];last=0
            for match in TOKEN_DISPLAY.finditer(after):
                pieces.append(after[last:match.start()].encode('cp932',errors='strict'))
                display=match.group();choices=tokens.get(display,set())
                if choices:
                    if len(choices)!=1 or display in literal:raise ValueError('同じ表示の定型文を一意に決められません。')
                    pieces.append(next(iter(choices)))
                elif display in literal:
                    pieces.append(display.encode('cp932',errors='strict'))
                else:raise ValueError('編集元にない定型文表記です。定型文の追加・置換は未対応です。')
                last=match.end()
            pieces.append(after[last:].encode('cp932',errors='strict'))
            payload=b''.join(pieces)
            # Partial edits of a token's brackets must not silently turn it into ordinary text.
            plain=''.join(p[0] for p in parts if not p[2])
            unmatched=TOKEN_DISPLAY.sub('',after)
            for marker in ('【','】','{at:'):
                if unmatched.lower().count(marker)>TOKEN_DISPLAY.sub('',plain).lower().count(marker):
                    raise ValueError('定型文表記が途中で切れています。定型文はまとまりで編集してください。')
    except UnicodeError as exc:
        raise ValueError('CP932で保存できない文字、または解釈できない元バイトがあります。') from exc
    if len(payload)>limit:raise ValueError(f'{"名前" if title else "行"}の上限{limit}バイトを超えています（{len(payload)}バイト）。')
    # New literal reserved/control bytes must not become hidden game control sequences.
    if title and any(b<32 or b==0x7f or b==0xfd for b in payload):raise ValueError('制御文字は保存できません。')
    if not title:
        for display,encoded,is_token in segments(payload+b'\0',resolver):
            if not is_token and any(b<32 or b==0x7f for b in encoded):raise ValueError('制御文字は保存できません。')
    output=bytearray(raw);output[:len(payload)+1]=payload+b'\0'
    if text(bytes(output),None if title else resolver).display!=after:raise ValueError('保存後に文字が変わるため、この文字列を保存できません。')
    return bytes(output)
