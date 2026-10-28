"""The property harness rejects non-fixture access and minimizes failures."""
import ctypes
import json
from pathlib import Path
import socket
import unittest
from tests.property_support import isolated, check_sequence, ROOT


class PropertySupportTests(unittest.TestCase):
    def test_access_guard_blocks_external_files_network_and_native_calls(self):
        with isolated() as base:
            with self.assertRaisesRegex(AssertionError,'outside synthetic root'):
                (base.parent/'must-not-open.dat').read_bytes()
            with self.assertRaisesRegex(AssertionError,'Forbidden external access'):
                socket.socket()
            with self.assertRaisesRegex(AssertionError,'Forbidden external access'):
                ctypes.CDLL('kernel32')
            p=base/'allowed.dat';p.write_bytes(b'synthetic');self.assertEqual(p.read_bytes(),b'synthetic')

    def test_shrinker_retains_a_reproducible_failure(self):
        def replay(ops):
            if 'trigger' in ops:raise AssertionError('expected=0 actual=1')
        with self.assertRaisesRegex(AssertionError,'minimized counterexample'):
            check_sequence('harness-selftest',0,['irrelevant','trigger','more'],replay)
        report=ROOT/'harness-selftest-0.json'
        try:
            data=json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(data['minimal_operations'],['trigger'])
            self.assertIn('expected=0 actual=1',data['failure'])
        finally:report.unlink()
