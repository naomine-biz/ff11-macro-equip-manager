import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from ff11reader import saving
from ff11reader.codecs import BAGS, equipsets
from ff11reader.domain import Character, Snapshot


def checksum(raw):
    raw[8:24]=hashlib.md5(raw[24:]).digest()
    return bytes(raw)


class SaveTests(unittest.TestCase):
    def setUp(self):
        work=Path(__file__).resolve().parents[1]/'work'/'save-tests'
        work.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=work);self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.folder=self.base/'game'/'USER'/'abc'
        self.folder.mkdir(parents=True)
        raw=bytearray(1624);raw[:8]=b'HEADER!!'
        raw[24:28]=b'Test'
        struct.pack_into('<BBH',raw,40,8*4+1,2,100)
        self.original=checksum(raw);self.target=self.folder/'es0.dat';self.target.write_bytes(self.original)
        for name,bag in BAGS.items():
            raw=bytearray(4240);struct.pack_into('<HH',raw,0,0x208,4216)
            if bag==8:struct.pack_into('<BBH',raw,0xA3C+5*20+16,5,0,100)
            (self.folder/name).write_bytes(checksum(raw))
        self.c=Character('abc');self.c.equipsets=equipsets(self.original,0)
        sources=[{'path':str(p.resolve()),'sha256':saving.digest(p.read_bytes())} for p in self.folder.iterdir()]
        self.snapshot=Snapshot('test','now',[self.c],{},sources,[])
        self.backups=self.base/'backups'
        self.plan=saving.prepare_save(self.snapshot,self.c,1,'main')

    def test_save_restore_only_reference_and_checksum_change(self):
        before={p:p.read_bytes() for p in self.folder.iterdir()}
        with patch.object(saving,'require_game_closed'):
            folder=saving.execute_save(self.plan,self.backups)
            actual=self.target.read_bytes()
            self.assertEqual(actual,self.plan.replacement)
            self.assertEqual(equipsets(actual,0)[0].slots[0].index,5)
            self.assertEqual({i for i,(a,b) in enumerate(zip(self.original,actual)) if a!=b}-{*range(8,24)},{41})
            self.assertEqual((folder/'original.dat').read_bytes(),self.original)
            for p,raw in before.items():
                if p!=self.target:self.assertEqual(p.read_bytes(),raw)
            saving.restore_backup(folder)
            self.assertEqual(self.target.read_bytes(),self.original)

    def test_changed_inventory_rejects_before_backup(self):
        (self.folder/'is.dat').write_bytes(b'changed')
        with patch.object(saving,'require_game_closed'),self.assertRaises(ValueError):
            saving.execute_save(self.plan,self.backups)
        self.assertEqual(self.target.read_bytes(),self.original)
        self.assertFalse(self.backups.exists())

    def test_running_game_blocks_save(self):
        with patch.object(saving,'require_game_closed',side_effect=RuntimeError('running')),self.assertRaises(RuntimeError):
            saving.execute_save(self.plan,self.backups)
        self.assertEqual(self.target.read_bytes(),self.original)

    def test_replace_failure_preserves_original_and_backup(self):
        with patch.object(saving,'require_game_closed'),patch.object(saving.os,'replace',side_effect=OSError('failure')),self.assertRaises(OSError):
            saving.execute_save(self.plan,self.backups)
        self.assertEqual(self.target.read_bytes(),self.original)
        self.assertEqual(next(self.backups.glob('*/original.dat')).read_bytes(),self.original)
        self.assertFalse(list(self.folder.glob('*.tmp')))

    def test_restore_does_not_overwrite_later_changes(self):
        with patch.object(saving,'require_game_closed'):
            folder=saving.execute_save(self.plan,self.backups)
            self.target.write_bytes(b'new game data')
            with self.assertRaises(ValueError):saving.restore_backup(folder)
        self.assertEqual(self.target.read_bytes(),b'new game data')

    def test_tampered_candidate_or_missing_dependency_rejected(self):
        change=replace(self.plan.changes[0],after=(8,6))
        altered=replace(self.plan,changes=(change,),replacement=saving.patch_equipment(self.original,0,(change,)))
        with patch.object(saving,'require_game_closed'):
            with self.assertRaises(ValueError):saving.execute_save(altered,self.backups)
            with self.assertRaises(ValueError):saving.execute_save(replace(self.plan,dependencies=()),self.backups)
        self.assertEqual(self.target.read_bytes(),self.original)

    def test_preview_stale_source_rejected(self):
        self.target.write_bytes(b'changed')
        with self.assertRaises(ValueError):saving.prepare_save(self.snapshot,self.c,1,'main')

    def test_legacy_save_delegates_to_shared_transaction(self):
        # D-05 / GAP-05: the CLI uses the same execution/rollback path as GUI.
        from ff11reader import file_transaction
        with patch.object(saving,'require_game_closed'), patch.object(file_transaction,'execute_batch',wraps=file_transaction.execute_batch) as execute:
            folder=saving.execute_save(self.plan,self.backups)
        self.assertEqual(execute.call_count,1)
        receipt=json.loads((folder/'receipt.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['target'],str(self.target))
        self.assertEqual((folder/'original.dat').read_bytes(),self.original)

    def test_post_write_decode_failure_rolls_back_legacy_save(self):
        decode=saving.equipsets
        def fail_after_write(raw,page):
            if self.target.read_bytes()==self.plan.replacement:
                raise ValueError('post-write decode failure')
            return decode(raw,page)
        with patch.object(saving,'require_game_closed'), patch.object(saving,'equipsets',side_effect=fail_after_write):
            with self.assertRaises(Exception):saving.execute_save(self.plan,self.backups)
        self.assertEqual(self.target.read_bytes(),self.original)
        folder=next(self.backups.iterdir())
        failure=json.loads((folder/'failure.json').read_text(encoding='utf-8'))
        self.assertEqual(failure['rollback_errors'],[])

    def test_legacy_rollback_preserves_external_update(self):
        decode=saving.equipsets
        external=b'external update'
        def fail_after_write(raw,page):
            if self.target.read_bytes()==self.plan.replacement:
                self.target.write_bytes(external)
                raise ValueError('external update during validation')
            return decode(raw,page)
        with patch.object(saving,'require_game_closed'), patch.object(saving,'equipsets',side_effect=fail_after_write):
            with self.assertRaises(RuntimeError):saving.execute_save(self.plan,self.backups)
        self.assertEqual(self.target.read_bytes(),external)
        folder=next(self.backups.iterdir())
        failure=json.loads((folder/'failure.json').read_text(encoding='utf-8'))
        self.assertTrue(failure['rollback_errors'])
        self.assertEqual((folder/'original.dat').read_bytes(),self.original)
