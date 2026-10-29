"""Synthetic startup scheduling; never discovers or reads a game install."""
import os
import threading
import time
import tkinter as tk
import unittest
from ff11reader.startup import Startup


@unittest.skipUnless(os.environ.get('FF11_RUN_INTEGRATION')=='1','Enable Tk tests')
class StartupTests(unittest.TestCase):
    def setUp(self):
        self.app=tk.Tk();self.release=threading.Event();self.errors=[]
        self.app.report_callback_exception=lambda *e:self.errors.append(e)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.release.set()
        if hasattr(self,'startup') and hasattr(self.startup,'worker'):self.startup.worker.join(2)
        try:self.app.destroy()
        except tk.TclError:pass

    def until(self,predicate):
        deadline=time.monotonic()+3
        while not predicate() and time.monotonic()<deadline:
            self.app.update();time.sleep(.005)
        self.assertTrue(predicate());self.assertFalse(self.errors)

    def test_visible_responsive_then_single_main_thread_handoff(self):
        entered=threading.Event();threads=[];results=[];ticks=[]
        def prepare(report):
            threads.append(threading.get_ident());entered.set();report('履歴を復元中')
            self.release.wait(3);return 'prepared'
        def ready(value):results.append((value,threading.get_ident()))
        self.startup=Startup(self.app,prepare,ready)
        self.until(entered.is_set)
        self.assertTrue(self.app.winfo_viewable())
        self.app.after(10,lambda:ticks.append(True))
        self.until(lambda:ticks and self.startup.status['text']=='履歴を復元中')
        self.assertFalse(results);self.assertNotEqual(threads[0],threading.get_ident())
        self.release.set();self.until(lambda:bool(results))
        self.assertEqual(results,[('prepared',threading.get_ident())])
        self.assertFalse(self.startup.panel.winfo_exists())

    def test_failure_stays_visible(self):
        def prepare(report):raise ValueError('合成データの読込エラー')
        self.startup=Startup(self.app,prepare,lambda _:self.fail('unexpected ready'))
        self.until(lambda:'起動エラー' in self.app.title())
        details=[w for w in self.startup.panel.winfo_children() if isinstance(w,tk.Text)]
        self.assertIn('合成データの読込エラー',details[0].get('1.0','end'))

    def test_close_during_prepare_never_opens_main_window(self):
        entered=threading.Event();results=[]
        def prepare(report):
            entered.set();self.release.wait(3);report('done');return 1
        self.startup=Startup(self.app,prepare,results.append)
        self.until(entered.is_set);self.startup.close();self.release.set()
        self.startup.worker.join(2)
        self.assertFalse(self.startup.worker.is_alive());self.assertFalse(results)

    def test_prepared_editor_is_reused_by_main_window(self):
        from unittest.mock import patch
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from tests.test_editing import snapshot, TEMP_ROOT
        from ff11reader.edit_application import Editor
        from ff11reader.ui import ReaderWindow
        with TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            source=snapshot();editor=Editor(source,Path(tmp)/'draft.json')
            working=editor.snapshot()
            with patch('ff11reader.ui.Editor',side_effect=AssertionError('Duplicate restore')):
                view=ReaderWindow(self.app,working,editor=editor)
            self.assertIs(view.editor,editor)
            self.assertIs(view.snapshot,working)
