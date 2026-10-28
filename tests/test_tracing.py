import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from ff11reader import tracing

class TracingTests(unittest.TestCase):
    def test_parentage_error_and_privacy(self):
        Path('work/trace-tests').mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir='work/trace-tests') as directory:
            path=Path(directory)/'timings.jsonl'
            with patch.object(tracing, '_logger', None):
                tracing.configure(path)
                try:
                    with tracing.span('operation'):
                        with tracing.span('child'):
                            raise ValueError('private text')
                except ValueError: pass
                for handler in tracing._logger.handlers: handler.close()
                rows=[json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual(rows[0]['operation_id'],rows[1]['operation_id'])
                self.assertEqual(rows[0]['parent_id'],rows[1]['span_id'])
                self.assertTrue(all(row['status']=='error' and row['elapsed_ms']>=0 for row in rows))
                self.assertNotIn('private text',path.read_text())
                self.assertIsNone(tracing._current.get())

    def test_logging_failure_preserves_result_and_exception(self):
        with patch.object(tracing, '_logger') as logger:
            logger.info.side_effect=OSError('full')
            with tracing.span('success'): result=42
            self.assertEqual(result,42)
            with self.assertRaisesRegex(ValueError,'original'):
                with tracing.span('failure'): raise ValueError('original')
            self.assertIsNone(tracing._current.get())
