"""Canonical item auto-translate identities, inverse of the local token decoder."""
def item_identity(item_id):
    if not isinstance(item_id,int) or not 0<item_id<0x7400:
        raise ValueError('アイテムIDが範囲外です。')
    hi,lo=divmod(item_id,256)
    kind=7
    if hi==0:kind,hi=9,255
    elif lo==0:kind,lo=10,255
    return bytes((kind,1,hi,lo)).hex().upper()

def is_item_identity(identity):
    if len(identity)!=4 or identity[1]!=1:return False
    kind,_,hi,lo=identity
    if kind==9 and hi==255:item_id=lo
    elif kind==10 and lo==255:item_id=hi*256
    elif kind==7:item_id=hi*256+lo
    else:return False
    try:return item_identity(item_id)==identity.hex().upper()
    except ValueError:return False
