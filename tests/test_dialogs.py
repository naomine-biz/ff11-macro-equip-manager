"""Synthetic application-owned modal lifecycle; no game or native dialogs."""
import os
import tkinter as tk
import unittest
from unittest.mock import patch
from ff11reader import dialogs


@unittest.skipUnless(os.environ.get('FF11_RUN_INTEGRATION')=='1','Enable synthetic Tk checks')
class DialogTests(unittest.TestCase):
    def setUp(self):
        self.app=tk.Tk();self.app.geometry('800x500');self.errors=[]
        self.app.report_callback_exception=lambda *args:self.errors.append(args)
        self.behind=tk.Entry(self.app);self.behind.pack();self.app.update();self.behind.focus_force()
        self.app.after(4000,self.app.destroy)

    def tearDown(self):
        try:self.app.destroy()
        except tk.TclError:pass
        self.assertFalse(self.errors,self.errors)

    def test_overlay_cancel_focus_and_confirm(self):
        modal=dialogs.Modal(self.app,'確認','本文','confirm')
        self.app.update()
        self.assertIs(modal.layer.master,self.app)
        self.assertFalse(any(isinstance(w,tk.Toplevel) for w in self.app.winfo_children()))
        self.assertEqual(self.app.grab_current(),modal.layer)
        self.assertEqual(self.app.focus_get(),modal.cancel_button)
        self.app.after(10,lambda:modal.cancel_button.event_generate('<Escape>'))
        self.assertFalse(modal.wait());self.assertIsNone(self.app.grab_current())
        self.assertEqual(self.app.focus_get(),self.behind)
        modal=dialogs.Modal(self.app,'確認','本文','confirm')
        self.app.after(10,modal.ok_button.invoke);self.assertTrue(modal.wait())

    def test_input_empty_value_and_cancel(self):
        modal=dialogs.Modal(self.app,'入力','本文','input','元の名前')
        modal.entry.delete(0,'end')
        self.app.after(10,modal.ok_button.invoke);self.assertEqual(modal.wait(),'')
        modal=dialogs.Modal(self.app,'入力','本文','input','名前')
        self.app.after(10,modal.cancel);self.assertIsNone(modal.wait())

    def test_long_message_scroll_and_tab_containment(self):
        message='長い通知\n'*100
        modal=dialogs.Modal(self.app,'エラー',message,'error');self.app.update()
        self.assertEqual(modal.body.get('1.0','end-1c'),message)
        modal.body.yview_moveto(1);self.assertGreater(modal.body.yview()[0],0)
        for _ in range(12):
            modal.cycle(1);self.app.update()
            self.assertIn(self.app.focus_get(),modal.focusables)
        self.app.after(10,modal.ok_button.invoke);modal.wait()

    def test_nested_overlay_restores_grab(self):
        outer=dialogs.Modal(self.app,'外側','本文','confirm');self.app.update()
        inner=dialogs.Modal(self.app,'内側','本文','error');self.app.update()
        self.app.after(10,inner.cancel);inner.wait()
        self.assertTrue(outer.layer.winfo_exists());self.assertEqual(self.app.grab_current(),outer.layer)
        self.app.after(10,outer.cancel);outer.wait()

    def test_parent_close_cancels(self):
        parent=tk.Toplevel(self.app);parent.geometry('500x300');self.app.update()
        modal=dialogs.Modal(parent,'確認','本文','confirm')
        self.app.after(10,parent.destroy);self.assertFalse(modal.wait())

    def test_startup_warning_keeps_never_mapped_window_visible(self):
        # A fresh window is essential: previously mapped windows hide this deadlock.
        parent=tk.Toplevel(self.app);parent.geometry('500x300');observed=[]
        self.assertFalse(parent.winfo_ismapped())
        done=tk.BooleanVar(master=self.app,value=False)
        def startup():
            modal=dialogs.Modal(parent,'作業再開の確認','読込元が変わっています。','warning')
            def inspect():
                observed.append((parent.winfo_viewable(),parent.winfo_width(),parent.winfo_height()))
                modal.cancel()
            self.app.after(30,inspect);modal.wait();done.set(True)
        dialogs.when_visible(parent,startup)
        self.app.wait_variable(done)
        self.assertEqual(observed,[(1,500,300)])
        parent.withdraw();parent.deiconify();self.app.update()
        self.assertEqual(len(observed),1)
        parent.destroy()

    def test_short_notice_is_compact_without_scrollbar(self):
        for kind in ('notice','warning','error','confirm','input'):
            modal=dialogs.Modal(self.app,'確認','短い通知です。',kind);self.app.update()
            self.assertLess(modal.panel.winfo_height(),230)
            self.assertLess(modal.panel.winfo_width(),600)
            self.assertFalse(modal.scroll.winfo_ismapped())
            self.assertEqual(modal.body.yview(),(0.0,1.0))
            self.app.after(1,modal.cancel);modal.wait()

    def test_wrapped_long_message_is_bounded_and_resizes(self):
        modal=dialogs.Modal(self.app,'確認','日本語の折り返し表示を確認します。'*100,'warning')
        self.app.update()
        self.assertTrue(modal.scroll.winfo_ismapped())
        self.assertLessEqual(modal.panel.winfo_height(),425)
        self.assertLessEqual(modal.panel.winfo_width(),760)
        self.app.geometry('600x350');self.app.update()
        self.assertLessEqual(modal.panel.winfo_width(),560)
        self.assertLessEqual(modal.panel.winfo_height(),298)
        modal.body.yview_moveto(1);self.assertGreater(modal.body.yview()[0],0)
        self.app.after(1,modal.cancel);modal.wait()

    def test_multiline_notice_grows_only_as_needed(self):
        heights=[]
        for message in ('一行','一行\n二行\n三行\n四行'):
            modal=dialogs.Modal(self.app,'確認',message);self.app.update()
            heights.append(modal.panel.winfo_height())
            self.assertFalse(modal.scroll.winfo_ismapped())
            self.assertEqual(modal.body.yview(),(0.0,1.0))
            self.app.after(1,modal.cancel);modal.wait()
        self.assertGreater(heights[1],heights[0])

    def test_public_functions_use_shared_overlay(self):
        cls=dialogs.Modal
        def create(*args,**kwargs):
            modal=cls(*args,**kwargs);self.app.after(10,modal.cancel);return modal
        with patch.object(dialogs,'Modal',side_effect=create):
            self.assertFalse(dialogs.askyesno('確認','本文',parent=self.app))
            self.assertIsNone(dialogs.askstring('入力','本文',parent=self.app))
            dialogs.showwarning('警告','本文',parent=self.app)
            dialogs.showerror('エラー','本文',parent=self.app)
