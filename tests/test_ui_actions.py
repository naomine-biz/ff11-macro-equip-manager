import os
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch
from ff11reader.ui_actions import ActionButton, state
from ff11reader import dialogs

@unittest.skipUnless(os.environ.get('FF11_RUN_INTEGRATION')=='1','Synthetic Tk checks')
class ActionTests(unittest.TestCase):
    def setUp(self):
        self.wrapper=tk.CallWrapper;self.wait=tk.Misc.wait_window
        self.app=tk.Tk();self.errors=[];self.app.report_callback_exception=lambda *args:self.errors.append(args)
        self.entry=tk.Entry(self.app,cursor='xterm');self.entry.pack();self.app.update()
    def tearDown(self):
        try:self.app.destroy()
        except tk.TclError:pass
    def test_only_declared_heavy_actions_are_busy(self):
        values=[];busy=state(self.app)
        heavy=ActionButton(self.app,busy=True,command=lambda:values.append(self.entry.cget('cursor')))
        light=ActionButton(self.app,command=lambda:values.append(self.entry.cget('cursor')))
        with patch.object(busy,'show',wraps=busy.show) as show:
            light.invoke()
            ttk.Button(self.app,command=lambda:values.append(self.entry.cget('cursor'))).invoke()
            self.entry.bind('<<Select>>',lambda e:values.append(self.entry.cget('cursor')))
            self.entry.event_generate('<<Select>>')
            self.app.after_idle(lambda:values.append(self.entry.cget('cursor')));self.app.update()
            self.assertEqual(show.call_count,0)
            heavy.invoke();self.assertEqual(show.call_count,1)
        self.assertEqual(values,['xterm']*4+['wait'])
        self.assertEqual(self.entry.cget('cursor'),'xterm')
        self.assertIs(tk.CallWrapper,self.wrapper);self.assertIs(tk.Misc.wait_window,self.wait)
    def test_nested_exception_and_changed_command(self):
        busy=state(self.app);seen=[]
        inner=ActionButton(self.app,busy=True,command=lambda:seen.append(busy.depth))
        def fail():inner.invoke();raise ValueError('test')
        outer=ActionButton(self.app,busy=True,command=fail);outer.invoke()
        self.assertEqual(seen,[2]);self.assertEqual(len(self.errors),1)
        self.assertEqual(busy.depth,0);self.assertEqual(self.entry.cget('cursor'),'xterm')
        outer.configure(command=lambda:seen.append(self.entry.cget('cursor')));outer.invoke()
        self.assertEqual(seen[-1],'wait')
        outer.configure(busy=False);outer.invoke();self.assertEqual(seen[-1],'xterm')
    def test_dialog_input_wait_is_normal_and_action_resumes(self):
        seen=[];original=dialogs.Modal
        def modal(*args,**kwargs):
            result=original(*args,**kwargs)
            def finish():
                seen.append(self.entry.cget('cursor'));result.finish(True)
            self.app.after(10,finish)
            return result
        def action():
            self.assertTrue(dialogs.askyesno('確認','本文',parent=self.app))
            seen.append(self.entry.cget('cursor'))
        with patch.object(dialogs,'Modal',side_effect=modal):ActionButton(self.app,busy=True,command=action).invoke()
        self.assertEqual(seen,['xterm','wait']);self.assertEqual(self.entry.cget('cursor'),'xterm')
        self.assertFalse(self.errors)
    def test_child_destroy_restores_and_keyboard_invokes(self):
        child=tk.Toplevel(self.app);seen=[]
        button=ActionButton(child,busy=True,command=lambda:seen.append(self.entry.cget('cursor')));button.pack()
        self.app.update();button.focus_force();button.event_generate('<KeyPress-space>');button.event_generate('<KeyRelease-space>');self.app.update()
        self.assertEqual(seen,['wait'])
        button.configure(command=child.destroy);button.invoke()
        self.assertEqual(self.entry.cget('cursor'),'xterm');self.assertFalse(self.errors)
