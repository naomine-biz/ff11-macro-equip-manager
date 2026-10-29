import unittest
from dataclasses import replace
from unittest.mock import patch
from ff11reader.phrases import PhraseCatalog
from ff11reader.dictionaries import resolve_token
from ff11reader.item_tokens import item_identity, is_item_identity
from ff11reader.domain import Text
from ff11reader.text_editing import replace_range
from ff11reader.macro_text import patch_text
from ff11reader import codecs
from tests.test_phrase_editing import PhraseFixture, PHRASES
from tests.property_support import isolated

ITEMS={1:{'name':'ポーション','name_state':'cp932'},256:{'name':'同名装備'},257:{'name':'同名装備'},65535:{'name':'無効'},2:{'name':'.'},3:{'name':'破損','name_state':'partial'}}
class ItemFixture(PhraseFixture):
    def load(self):
        snapshot=super().load();snapshot.items.update(ITEMS)
        resolver=lambda p:resolve_token(p,PHRASES,snapshot.items)
        for c in snapshot.characters:
            c.macros=[replace(m,lines=tuple(codecs.text(bytes.fromhex(t.raw_hex),resolver) for t in m.lines)) for m in c.macros]
        return snapshot

class ItemTests(unittest.TestCase):
    def test_catalog_filter_order_and_names(self):
        catalog=PhraseCatalog(PHRASES,items=ITEMS)
        self.assertEqual(catalog.groups,('魔法','アイテム','その他'))
        self.assertEqual(len(catalog.search('',group='アイテム')),3)
        self.assertEqual(catalog.search('ぽーしょん')[0].identity,'0901FF01')
        self.assertEqual({p.identity for p in catalog.search('同名装備')},{'0A0101FF','07010101'})

    def test_all_supported_ids_round_trip(self):
        for item in range(1,0x7400):
            identity=item_identity(item);payload=bytes.fromhex(identity)
            self.assertTrue(is_item_identity(payload))
            self.assertEqual(resolve_token(payload,{}, {item:{'name':'装備'}}),'装備')
        for payload in ('07010001','07010100','09010001','0A010100','07017400'):
            self.assertFalse(is_item_identity(bytes.fromhex(payload)))

    def test_edit_undo_restart_and_synthetic_save(self):
        with isolated() as base,patch('ff11reader.adapters.LocalReader.load_phrases',return_value=PHRASES):
            f=ItemFixture(base,'macro',1,1)
            for item in (1,256,257):
                phrase=next(p for p in PhraseCatalog({},items=ITEMS).search('') if p.identity==item_identity(item))
                value=replace_range(Text('/item ','','draft'),6,6,phrase.label,phrase.identity)
                before=f.bytes();f.set_value(value);self.assertEqual(f.bytes(),before)
                f.editor.undo();f.editor.redo();f.reopen();self.assertIsNone(f.editor.blocked)
                plan=f.preview();expected=bytes.fromhex('FD'+phrase.identity+'FD')
                self.assertIn(expected,plan.files[0].changes[0].replacement)
                f.save(plan);f.reopen();self.assertIsNone(f.editor.blocked)
                self.assertFalse(f.editor.session.dirty)

    def test_unknown_item_rejected(self):
        value=replace_range(Text('','','draft'),0,0,'【未知】',item_identity(10))
        with self.assertRaises(ValueError):
            patch_text(b'\0'*61,'',value.display,lambda p:resolve_token(p,{},ITEMS),tokens=value.tokens)

import os
@unittest.skipUnless(os.environ.get('FF11_RUN_INTEGRATION')=='1','Synthetic Tk check')
class ItemUITests(unittest.TestCase):
    def test_tab_item_group_insert(self):
        import tkinter as tk
        from tkinter import ttk
        from ff11reader.phrase_ui import PhraseEntry
        app=tk.Tk()
        try:
            entry=tk.Entry(app);entry.pack()
            control=PhraseEntry(entry,Text('','','draft'),PhraseCatalog(PHRASES,items=ITEMS))
            app.update();entry.focus_force();entry.event_generate('<Tab>');app.update()
            popup=control.popup
            groups=next(w for w in popup.winfo_children() if isinstance(w,ttk.Combobox))
            groups.set('アイテム');groups.event_generate('<<ComboboxSelected>>');app.update()
            search=next(w for w in popup.winfo_children() if type(w)==tk.Entry)
            search.insert(0,'ぽーしょん');app.update()
            listing=next(c for w in popup.winfo_children() for c in w.winfo_children() if isinstance(c,tk.Listbox))
            self.assertEqual(listing.size(),1)
            listing.focus_force();listing.event_generate('<Return>');app.update()
            self.assertEqual(control.value.display,'【ポーション】')
            self.assertEqual(control.value.tokens[0].identity,'0901FF01')
        finally:app.destroy()
