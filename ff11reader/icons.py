"""Decode the embedded 32x32 indexed bitmap to PNG, in memory only."""
import base64
import struct
import zlib


def item_icon(record):
    # Decoded item record: icon wrapper at 0x284, bitmap header after 17 bytes.
    header=0x295
    if len(record)<header+40+1024+1024:return None
    size,width,height,planes,bpp,compression=struct.unpack_from('<IiiHHI',record,header)
    if (size,width,abs(height),planes,bpp,compression)!=(40,32,32,1,8,0):return None
    palette=record[header+40:header+40+1024]
    pixels=record[header+40+1024:header+40+1024+1024]
    rows=[]
    for y in range(32):
        source_y=31-y if height>0 else y
        row=bytearray(b'\0')
        for x in range(32):
            i=pixels[source_y*32+x]*4
            b,g,r,a=palette[i:i+4]
            row.extend((r,g,b,min(a*2,255)))
        rows.append(row)
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',32,32,8,6,0,0,0))
    png+=chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b'')
    return base64.b64encode(png).decode('ascii')
