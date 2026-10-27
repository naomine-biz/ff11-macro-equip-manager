from dataclasses import asdict
import base64
import struct
import unittest
import zlib
from ff11reader.domain import ItemReferenceState as State, InventoryRow
from ff11reader.references import assess_equipment
from ff11reader.icons import item_icon
from test_references import character, slot


class SlotStateTests(unittest.TestCase):
    def resolved(self,rows=(),coverage=None,slots=None):
        if coverage is None:coverage={i:'loaded' for i in range(17)}
        c=character(slots or [slot()],rows,coverage)
        before=asdict(c)
        result=assess_equipment(c)
        self.assertEqual(asdict(c),before)  # pure evaluation; no input mutation
        c.equipsets=result
        return c,result[0].slots[0].item_reference

    def test_saved_location_and_type_match(self):
        c,r=self.resolved([InventoryRow(8,1,100)])
        self.assertEqual(r.state,State.MATCH)
        self.assertEqual(r.observation,'cache_match')
        self.assertEqual(c.equipment_references[0].piece,c.equipsets[0].slots[0])
        self.assertNotIn('equipment_references',asdict(c))
        self.assertEqual(asdict(c)['equipsets'][0]['slots'][0]['item_reference']['state'],State.MATCH)

    def test_exact_match_takes_priority_over_other_same_type_candidates(self):
        _,r=self.resolved([InventoryRow(8,1,100),InventoryRow(8,2,100)])
        self.assertEqual(r.state,State.MATCH)

    def test_candidate_in_safe_and_no_candidate(self):
        _,r=self.resolved([InventoryRow(5,1,100)])
        self.assertEqual(r.state,State.SAME_TYPE_ELSEWHERE)
        _,r=self.resolved();self.assertEqual(r.state,State.NOT_OBSERVED)
        self.assertEqual(r.certainty,'cache_observation_only')

    def test_other_bags_missing_do_not_prevent_exact_match(self):
        _,r=self.resolved(coverage={8:'loaded'});self.assertEqual(r.state,State.INSUFFICIENT_DATA)
        _,r=self.resolved([InventoryRow(8,1,100)],coverage={8:'loaded'})
        self.assertEqual(r.state,State.MATCH)

    def test_candidates_elsewhere_are_not_exact_matches(self):
        _,r=self.resolved([InventoryRow(8,2,100)])
        self.assertEqual(r.state,State.SAME_TYPE_ELSEWHERE)
        _,r=self.resolved([InventoryRow(8,2,100),InventoryRow(8,3,100)])
        self.assertEqual(r.state,State.MULTIPLE_CANDIDATES)

    def test_augments_do_not_affect_reference_state(self):
        for augment in ['unknown','decoded','known_none','partial']:
            _,r=self.resolved([InventoryRow(8,1,100,augment_state=augment)])
            self.assertEqual(r.state,State.MATCH)

    def test_no_item_and_unknown_action(self):
        for action in ['keep','remove']:
            _,r=self.resolved(slots=[slot(action=action)])
            self.assertEqual(r.state,State.NOT_APPLICABLE)
        _,r=self.resolved(slots=[slot(action='unknown')]);self.assertEqual(r.state,State.INSUFFICIENT_DATA)

    def test_assessment_retains_original_bytes_and_reference(self):
        c,r=self.resolved([InventoryRow(8,5,100)])
        piece=c.equipsets[0].slots[0]
        self.assertEqual((piece.item_id,piece.container,piece.index,piece.raw_hex),(100,8,1,''))
        self.assertEqual(r.candidates,((8,5),))


class IconTests(unittest.TestCase):
    def test_bitmap_validation_and_top_down_png(self):
        data=bytearray(0x1400);header=0x295
        struct.pack_into('<IiiHHI',data,header,40,32,32,1,8,0)
        data[header+40:header+44]=bytes([0,0,255,128])
        png=base64.b64decode(item_icon(data));self.assertEqual(png[:8],b'\x89PNG\r\n\x1a\n')
        pos=8;payload=b''
        while pos<len(png):
            size=struct.unpack_from('>I',png,pos)[0]
            if png[pos+4:pos+8]==b'IDAT':payload+=png[pos+8:pos+8+size]
            pos+=12+size
        self.assertEqual(zlib.decompress(payload)[:5],b'\0\xff\0\0\xff')
        self.assertIsNone(item_icon(b''))
        data[header]=0;self.assertIsNone(item_icon(data))


if __name__=='__main__':unittest.main()
