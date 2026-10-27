import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from ff11reader import codecs
from ff11reader.adapters import LocalReader
from ff11reader.dictionaries import auto_translate, dmsg_names, resolve_token


def dat(size):
    return bytearray(size)


def seal(b):
    b[8:24]=hashlib.md5(b[24:]).digest(); return bytes(b)


class DecodingTests(unittest.TestCase):
    def test_native_phrase_table_and_truncated_input(self):
        raw='初めまして。'.encode('cp932')+b'\0'
        record=b'\x02\x01\x01\x01'+bytes([len(raw)])+raw+b'\0'
        self.assertEqual(auto_translate(record)[257],'初めまして。')
        with self.assertRaises(ValueError): auto_translate(record[:-1])

    def test_native_dmsg_fixed_and_encrypted(self):
        name='プロテス'.encode('cp932')+b'\0'; body=bytearray(64)
        struct.pack_into('<III',body,0,1,12,0);body[40:40+len(name)]=name
        head=bytearray(64);head[:8]=b'd_msg\0\0\0'
        struct.pack_into('<Q',head,12,0x300000003)
        struct.pack_into('<6I',head,20,128,64,0,64,64,1)
        self.assertEqual(dmsg_names(bytes(head+body))[0],'プロテス')
        head[10]=1
        self.assertEqual(dmsg_names(bytes(head)+bytes(255-v for v in body))[0],'プロテス')

    def test_resolved_token_preserves_bytes_and_unknown_fallback(self):
        b=bytes.fromhex('fd02010101fd00')
        value=codecs.text(b,lambda p:resolve_token(p,{257:'初めまして。'},{}))
        self.assertEqual(value.display,'【初めまして。】')
        self.assertEqual(value.raw_hex,b.hex())
        self.assertEqual(codecs.text(b,lambda p:None).display,'{AT:02010101}')
        self.assertEqual(resolve_token(bytes.fromhex('0a015cff'),{}, {0x5c00:{'name':'装備'}}),'装備')
        self.assertIsNone(resolve_token(bytes.fromhex('0a015c01'),{}, {0x5c00:{'name':'装備'}}))

    def test_macro_addresses_and_raw_lines(self):
        b=dat(7624); b[28:33]=b'/echo'
        result=codecs.macros(seal(b),399)
        self.assertEqual((result[0].book,result[0].palette),(40,10))
        self.assertEqual((result[-1].bank,result[-1].key),('alt',10))
        self.assertEqual(result[0].lines[0].display,'/echo')
        self.assertEqual(len(result[0].lines[0].raw_hex),122)

    def test_corruption_rejected(self):
        b=bytearray(seal(dat(7624))); b[-1]=1
        with self.assertRaisesRegex(ValueError,'MD5'): codecs.macros(b,0)
        with self.assertRaises(ValueError): codecs.inventory(b'',0)

    def test_token_with_embedded_zero_and_japanese(self):
        raw='装備'.encode('cp932')+bytes.fromhex('fd02000201fd')+b'\0extra'
        value=codecs.text(raw)
        self.assertEqual(value.display,'装備{AT:02000201}')
        self.assertEqual(value.raw_hex,raw.hex())
        self.assertEqual(value.state,'partial')

    def test_equipment_flags_and_zero_container(self):
        b=dat(1624)
        struct.pack_into('<BBH',b,40,1,5,123)
        b[44]=2; b[48]=3
        slots=codecs.equipsets(seal(b),9)[0].slots
        self.assertEqual((slots[0].container,slots[0].index,slots[0].item_id),(0,5,123))
        self.assertEqual([s.action for s in slots[:4]],['equip','remove','unknown','keep'])

    def test_inventory_never_invents_quantity_or_augments(self):
        b=dat(4240); struct.pack_into('<HH',b,0,0x0208,4216)
        struct.pack_into('<BBH',b,0xA3C+20+16,1,0,123)
        struct.pack_into('<BBH',b,0xA3C+40+16,2,0,65535)
        rows=codecs.inventory(seal(b),8)
        self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0].quantity)
        self.assertEqual(rows[0].augment_state,'unknown')
        b[0xA3C+20+16]=2
        with self.assertRaises(ValueError): codecs.inventory(seal(b),8)

    def test_source_mutation_detected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            p=Path(tmp)/'source'; p.write_bytes(b'a')
            reader=LocalReader(tmp); reader.read(p)
            p.write_bytes(b'b')
            self.assertEqual(reader.verify_unchanged(),[str(p.resolve())])


if __name__=='__main__': unittest.main()
