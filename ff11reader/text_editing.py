"""Pure text edits retaining the identity and location of auto-translate tokens."""
from dataclasses import replace
import re
from .domain import Text, TextToken


def validate_tokens(value):
    if value.tokens is None:return
    if not isinstance(value.tokens,tuple):raise ValueError('定型文の範囲が不正です。')
    end=0
    for token in value.tokens:
        if (not isinstance(token,TextToken) or type(token.start) is not int or type(token.end) is not int
            or not end<=token.start<token.end<=len(value.display)
            or not isinstance(token.identity,str) or not re.fullmatch('[0-9A-F]{8}',token.identity)):
            raise ValueError('定型文の範囲・IDが不正です。')
        label=value.display[token.start:token.end]
        if not (label.startswith('【') and label.endswith('】') or label=='{AT:'+token.identity+'}'):
            raise ValueError('定型文の表示が途中で切れています。')
        end=token.end


def replace_range(value,start,end,insert,identity=None):
    validate_tokens(value)
    if not 0<=start<=end<=len(value.display):raise ValueError('編集位置が不正です。')
    for t in value.tokens or ():
        if t.start<start<t.end or t.start<end<t.end:raise ValueError('定型文はまとまりで編集してください。')
    delta=len(insert)-(end-start)
    tokens=[]
    for t in value.tokens or ():
        if t.end<=start:tokens.append(t)
        elif t.start>=end:tokens.append(replace(t,start=t.start+delta,end=t.end+delta))
    if identity is not None:tokens.append(TextToken(start,start+len(insert),identity))
    result=Text(value.display[:start]+insert+value.display[end:],value.raw_hex,'draft',
                tuple(sorted(tokens,key=lambda t:t.start)) if value.tokens is not None or identity else None)
    validate_tokens(result)
    return result


def remap_text(value,display):
    if display==value.display:return value
    if value.tokens is None:return Text(display,value.raw_hex,'draft')
    groups={}
    for token in value.tokens:
        groups.setdefault(value.display[token.start:token.end],[]).append(token)
    tokens=[]
    pattern=re.compile(r'【[^【】]*】|\{AT:[0-9A-Fa-f]{8}\}')
    for label,original in groups.items():
        if sum(m.group()==label for m in pattern.finditer(value.display))!=len(original):
            raise ValueError('定型文と同じ表示の通常文字があります。選択範囲を指定して編集してください。')
        matches=[m for m in pattern.finditer(display) if m.group()==label]
        if len({t.identity for t in original})>1 and len(matches) not in (0,len(original)):
            raise ValueError('同名の定型文は選択範囲を指定して編集してください。')
        for index,match in enumerate(matches):
            identity=original[min(index,len(original)-1)].identity
            tokens.append(TextToken(match.start(),match.end(),identity))
    return Text(display,value.raw_hex,'draft',tuple(sorted(tokens,key=lambda t:t.start)))
