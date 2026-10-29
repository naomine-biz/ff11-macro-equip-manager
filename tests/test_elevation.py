"""Synthetic elevation transport: no UAC, native APIs, or installed game access."""
import encodings.cp932
from ff11reader import item_tokens, text_editing
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from ff11reader import elevation, macro_saving, equipment_saving
from tests.property_support import isolated, GameFixture
import save_helper


def helper(request,digest):
    with patch('sys.argv',['save_helper.py',str(request),digest]):return save_helper.main()


def denied_once(real):
    calls=[]
    def execute(plan,backup):
        calls.append(1)
        if len(calls)==1:raise PermissionError('synthetic access denied')
        return real(plan,backup)
    return execute


class ElevationTests(unittest.TestCase):
    def test_both_save_types_share_uac_and_checkpoint(self):
        for kind,module,function in [('macro',macro_saving,'execute_macro_save'),('equipment',equipment_saving,'execute_equipment_save')]:
            with self.subTest(kind=kind),isolated() as base:
                f=GameFixture(base,kind,1,2);f.fix();plan=f.preview()
                self.assertEqual(elevation.decode(elevation.encode(plan)),plan)
                real=getattr(module,function)
                with patch.object(module,function,side_effect=denied_once(real)),patch.object(elevation,'launch_elevated',side_effect=helper) as launch:
                    backup=f.save(plan)
                launch.assert_called_once();self.assertTrue((backup/'verified.json').exists())
                self.assertFalse(f.editor.session.dirty);f.reopen();self.assertIsNone(f.editor.blocked)
                f.editor.undo();self.assertTrue(f.editor.session.dirty)
                self.assertFalse(list((base/'backups').glob('save-request-*')))

    def test_cancel_keeps_edits_and_allows_retry(self):
        with isolated() as base:
            f=GameFixture(base,'macro',1,1);f.fix();plan=f.preview();before=f.bytes()
            with patch.object(macro_saving,'execute_macro_save',side_effect=PermissionError()),patch.object(elevation,'launch_elevated',side_effect=RuntimeError('管理者確認を取り消しました')):
                with self.assertRaisesRegex(RuntimeError,'取り消し'):f.save(plan)
            self.assertEqual(f.bytes(),before);self.assertTrue(f.editor.session.dirty)
            self.assertFalse(f.editor.store.path.with_suffix('.pending.json').exists())
            self.assertFalse(list((base/'backups').glob('save-request-*')))
            f.save(plan);self.assertFalse(f.editor.session.dirty)

    def test_hash_tamper_and_stale_plan_are_rejected(self):
        with isolated() as base:
            f=GameFixture(base,'equipment',1,1);f.fix();plan=f.preview()
            request=base/'request.json'
            raw=json.dumps({'version':1,'plan':elevation.encode(plan),'backup_root':str(base/'backup')}).encode()
            request.write_bytes(raw+b' ')
            with self.assertRaisesRegex(ValueError,'変更'):elevation.execute_request(request,hashlib.sha256(raw).hexdigest())
            request.write_bytes(raw)
            target=Path(plan.files[0].target);target.write_bytes(b'external')
            with self.assertRaises(ValueError):elevation.execute_request(request,hashlib.sha256(raw).hexdigest())
            self.assertEqual(target.read_bytes(),b'external')

    def test_no_elevation_after_write_or_nonpermission_failure(self):
        with isolated() as base:
            f=GameFixture(base,'equipment',1,1);f.fix();plan=f.preview()
            def interrupted(p,b):
                Path(p.files[0].target).write_bytes(p.files[0].replacement)
                raise PermissionError()
            with patch.object(elevation,'launch_elevated') as launch:
                with self.assertRaises(PermissionError):elevation.execute_with_permission(plan,base/'backup',interrupted)
                launch.assert_not_called()
                with self.assertRaises(ValueError):elevation.execute_with_permission(plan,base/'backup',lambda p,b:(_ for _ in ()).throw(ValueError('stale')))
                launch.assert_not_called()

    def test_missing_worker_result_keeps_recovery_record_after_write(self):
        with isolated() as base:
            f=GameFixture(base,'equipment',1,1);f.fix();plan=f.preview()
            def lost_result(request,digest):
                helper(request,digest);request.with_suffix('.result.json').unlink();return 0
            real=equipment_saving.execute_equipment_save
            with patch.object(equipment_saving,'execute_equipment_save',side_effect=denied_once(real)),patch.object(elevation,'launch_elevated',side_effect=lost_result):
                with self.assertRaises(RuntimeError):f.save(plan)
            self.assertTrue(f.editor.blocked);self.assertTrue(f.editor.store.path.with_suffix('.pending.json').exists())
            f.reopen();self.assertIsNone(f.editor.blocked);self.assertFalse(f.editor.session.dirty)

    def test_normal_save_does_not_request_elevation(self):
        with isolated() as base:
            f=GameFixture(base,'equipment',1,1);f.fix()
            with patch.object(elevation,'launch_elevated') as launch:f.save(f.preview())
            launch.assert_not_called()

    def test_windows_launcher_uses_runas_and_reports_cancellation(self):
        import ctypes
        from unittest.mock import Mock
        shell=Mock();kernel=Mock();seen=[]
        def launch(pointer):
            info=pointer._obj
            seen.append((info.lpVerb,info.lpParameters,info.nShow))
            info.hProcess=123
            return 1
        shell.ShellExecuteExW.side_effect=launch
        kernel.WaitForSingleObject.return_value=0
        def exit_code(handle,pointer):pointer._obj.value=0;return 1
        kernel.GetExitCodeProcess.side_effect=exit_code
        with patch.object(ctypes,'WinDLL',side_effect=lambda name,**kw:shell if name=='shell32' else kernel):
            self.assertEqual(elevation.launch_elevated(Path('C:/test folder/request.json'),'a'*64),0)
            self.assertEqual(seen[0][0],'runas');self.assertEqual(seen[0][2],0)
            self.assertIn('-I -B',seen[0][1]);self.assertIn('"C:',seen[0][1])
            kernel.CloseHandle.assert_called_once_with(123)
            shell.ShellExecuteExW.side_effect=None;shell.ShellExecuteExW.return_value=0
            with patch.object(ctypes,'get_last_error',return_value=1223):
                with self.assertRaisesRegex(RuntimeError,'取り消し'):elevation.launch_elevated(Path('request.json'),'a'*64)
            kernel.CloseHandle.assert_called_once_with(123)

    def test_isolated_helper_process_reports_invalid_plan(self):
        import subprocess
        import sys
        import tempfile
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'work') as folder:
            request=Path(folder)/'request.json'
            raw=json.dumps({'version':1,'plan':None,'backup_root':folder}).encode()
            request.write_bytes(raw)
            result=subprocess.run([sys.executable,'-I','-B',str(root/'save_helper.py'),str(request),hashlib.sha256(raw).hexdigest()],
                                  capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=15)
            self.assertEqual(result.returncode,1,result.stderr)
            response=json.loads(request.with_suffix('.result.json').read_text(encoding='utf-8'))
            self.assertEqual(response['status'],'failed');self.assertIn('種類',response['error'])
