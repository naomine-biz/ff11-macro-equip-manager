"""Synthetic phrase search, semantic identity, editing, persistence and save tests."""
from dataclasses import replace
import json
import encodings.cp932
import os
from time import perf_counter
import unittest
from unittest.mock import patch
from ff11reader import codecs
from ff11reader.domain import Text, TextToken
from ff11reader.phrases import PhraseCatalog
from ff11reader.text_editing import replace_range, remap_text, validate_tokens
from ff11reader.macro_text import patch_text
from ff11reader.edit_values import text_value
from ff11reader.edit_application import Editor
from ff11reader.editing import macro_key
from tests.test_manual_macro_saving import ManualFixture
from tests.property_support import isolated, seeds

PHRASES={0x100:'挨拶',0x101:'こんにちは。',0x200:'魔法',0x201:'リジェネ',0x202:'リジェネ',0x203:'ケアル',0x204:'@CFFFF'}


class PhraseFixture(ManualFixture):
    def load(self):
        result=super().load();result.phrases=dict(PHRASES)
        resolver=lambda p:PHRASES.get(int.from_bytes(p[2:],'big')) if p[:2]==b'\x02\x01' else None
        for c in result.characters:
            c.macros=[replace(m,lines=tuple(codecs.text(bytes.fromhex(t.raw_hex),resolver) for t in m.lines)) for m in c.macros]
        return result

    def set_value(self,value):
        key=self.specs[0]['key'];m=next(m for m in self.editor.snapshot().characters[0].macros if macro_key(m)==key)
        lines=list(m.lines);lines[self.specs[0]['line']-1]=value
        self.editor.apply(self.editor.prepare_macro_edit('abc',key,m.title.display,lines))


class PhraseTests(unittest.TestCase):
    def test_search_categories_normalization_typos_and_order(self):
        catalog=PhraseCatalog(PHRASES)
        self.assertEqual(len(catalog.search('')),4)
        for query in ('リジェネ','りじぇね','ﾘｼﾞｪﾈ','リジェメ','リジネ','リジェネー'):
            self.assertEqual([p.identity for p in catalog.search(query)],['02010201','02010202'])
        self.assertEqual(catalog.search('ケア')[0].name,'ケアル')
        self.assertEqual(catalog.search('xxxxxxxx'),())
        names={0x101:'Regen',0x102:'Regeneration',0x103:'SuperRegen',0x104:'Regan'}
        self.assertEqual([p.name for p in PhraseCatalog(names).search('ＲＥＧＥＮ')],list(names.values()))

    def test_search_budget(self):
        names={key:'候補'+str(key) for key in range(1,3100) if key%256}
        catalog=PhraseCatalog(names);times=[]
        for query in ('候補123','候捕123','なし',''):
            start=perf_counter();catalog.search(query);times.append(perf_counter()-start)
        self.assertLess(max(times),.1,times)

    def test_range_edits_same_label_and_invalid_spans(self):
        first,second=PhraseCatalog(PHRASES).search('リジェネ')
        value=replace_range(Text('/ma ','','draft'),4,4,first.label,first.identity)
        value=replace_range(value,len(value.display),len(value.display),second.label,second.identity)
        self.assertEqual([t.identity for t in value.tokens],[first.identity,second.identity])
        changed=replace_range(value,4,4+len(first.label),second.label,second.identity)
        self.assertEqual(changed.display,value.display);self.assertNotEqual(text_value(changed),text_value(value))
        with self.assertRaises(ValueError):replace_range(value,5,6,'')
        with self.assertRaises(ValueError):validate_tokens(replace(value,tokens=(TextToken(4,999,first.identity),)))
        self.assertEqual(remap_text(value,'').tokens,())
        self.assertEqual([t.identity for t in remap_text(value,'x'+value.display).tokens],[first.identity,second.identity])

    def test_literal_with_same_label_does_not_become_token(self):
        phrase=PhraseCatalog(PHRASES).search('リジェネ')[0]
        raw=phrase.label.encode('cp932')+bytes.fromhex('FD'+phrase.identity+'FD')
        source=codecs.text(raw+b'\0',lambda _:phrase.name)
        with self.assertRaises(ValueError):remap_text(source,'x'+source.display)
        edited=replace_range(source,0,0,'x')
        field=raw+b'\0'*(61-len(raw))
        output=patch_text(field,source.display,edited.display,lambda _:phrase.name,tokens=edited.tokens)
        self.assertEqual(output[:len(raw)+2],b'x'+raw+b'\0')

    def test_encoding_rejects_forged_name_unknown_new_id_and_overflow(self):
        raw=b'\0'*61;resolver=lambda p:PHRASES.get(int.from_bytes(p[2:],'big'))
        for identity,label in [('02010201','【偽名】'),('0201FFFF','【不明】'),('02010200','【魔法】')]:
            with self.assertRaises(ValueError):patch_text(raw,'',label,resolver,tokens=(TextToken(0,len(label),identity),))
        phrase=PhraseCatalog(PHRASES).search('リジェネ')[0]
        for size in (54,55):
            value=replace_range(Text('x'*size,'','draft'),size,size,phrase.label,phrase.identity)
            if size==55:
                with self.assertRaises(ValueError):patch_text(raw,'',value.display,resolver,tokens=value.tokens)
            else:self.assertEqual(patch_text(raw,'',value.display,resolver,tokens=value.tokens)[54:60],bytes.fromhex('FD02010201FD'))

    def test_generated_insert_identity_only_change_undo_restart_save(self):
        for seed in seeds():
            with self.subTest(seed=seed),isolated() as base,patch('ff11reader.adapters.LocalReader.load_phrases',return_value=PHRASES):
                f=PhraseFixture(base,'macro',seed,1);before=f.bytes()
                value=Text('/ma ','','draft');phrase=PhraseCatalog(PHRASES).search('リジェネ')[seed%2]
                value=replace_range(value,4,4,phrase.label,phrase.identity)
                f.set_value(value);self.assertEqual(f.bytes(),before)
                f.editor.undo();self.assertFalse(f.editor.session.dirty)
                f.editor.redo();f.reopen();self.assertIsNone(f.editor.blocked)
                plan=f.preview();self.assertIn(bytes.fromhex('FD'+phrase.identity+'FD'),plan.files[0].changes[0].replacement)
                f.save(plan);f.reopen();self.assertIsNone(f.editor.blocked);self.assertFalse(f.editor.session.dirty)
                other=PhraseCatalog(PHRASES).search('リジェネ')[1-seed%2]
                changed=replace_range(value,4,len(value.display),other.label,other.identity)
                f.set_value(changed);self.assertTrue(f.editor.session.dirty)
                plan=f.preview();self.assertEqual(plan.files[0].changes[0].before,plan.files[0].changes[0].after)
                f.save(plan);f.reopen();self.assertFalse(f.editor.session.dirty)
                f.editor.undo();self.assertTrue(f.editor.session.dirty)
                self.assertIn(bytes.fromhex('FD'+phrase.identity+'FD'),f.preview().files[0].changes[0].replacement)
                f.save(f.preview());f.reopen();self.assertFalse(f.editor.session.dirty)

    def test_generated_range_edits_have_exact_token_bytes(self):
        import random
        resolver=lambda p:PHRASES.get(int.from_bytes(p[2:],'big'))
        choices=PhraseCatalog(PHRASES).search('リジェネ')
        for seed in seeds():
            rng=random.Random(seed);value=Text('',('00'*61),'draft');expected=[]
            for n in range(8):
                phrase=rng.choice(choices);position=rng.randrange(len(expected)+1)
                offset=position*len(phrase.label)
                value=replace_range(value,offset,offset,phrase.label,phrase.identity)
                expected.insert(position,phrase.identity)
                encoded=patch_text(b'\0'*61,'',value.display,resolver,tokens=value.tokens)
                wanted=b''.join(bytes.fromhex('FD'+identity+'FD') for identity in expected)
                self.assertEqual(encoded[:len(wanted)+1],wanted+b'\0')
                self.assertEqual(codecs.text(encoded,resolver).tokens,value.tokens)
                self.assertEqual([t.identity for t in value.tokens],expected)

    def test_old_draft_without_token_fields_reopens(self):
        with isolated() as base,patch('ff11reader.adapters.LocalReader.load_phrases',return_value=PHRASES):
            f=PhraseFixture(base,'macro',7,1);f.set_line(b'/echo '+bytes.fromhex('FD02010201FD'))
            f.edit_line('/say 【リジェネ】')
            path=f.editor.store.path;data=json.loads(path.read_text(encoding='utf-8'))
            def strip(value):
                if isinstance(value,dict):
                    if value.get('type')=='Text':
                        value['fields'].pop('tokens',None)
                        if value['fields']['state']=='draft':value['fields']['raw_hex']=''
                    for v in value.values():strip(v)
                elif isinstance(value,list):
                    for v in value:strip(v)
            strip(data);path.write_text(json.dumps(data),encoding='utf-8')
            f.reopen();self.assertIsNone(f.editor.blocked)
            self.assertIn(bytes.fromhex('FD02010201FD'),f.preview().files[0].changes[0].replacement)


@unittest.skipUnless(os.environ.get('FF11_RUN_INTEGRATION')=='1','Enable synthetic Tk checks')
class PhraseUITests(unittest.TestCase):
    def test_keyboard_search_selection_cancel_and_atomic_delete(self):
        import tkinter as tk
        from ff11reader.phrase_ui import PhraseEntry
        app=tk.Tk();errors=[];app.report_callback_exception=lambda *args:errors.append(args)
        try:
            entry=tk.Entry(app);entry.pack();entry.insert(0,'/ma ')
            controller=PhraseEntry(entry,Text('/ma ','','draft'),PhraseCatalog(PHRASES))
            app.update();entry.focus_force();entry.icursor('end');entry.event_generate('<Tab>');app.update()
            self.assertIsNotNone(controller.popup)
            popup=controller.popup
            search=next(w for w in popup.winfo_children() if type(w)==tk.Entry)
            def listbox():
                return next(c for frame in popup.winfo_children() for c in frame.winfo_children() if isinstance(c,tk.Listbox))
            search.insert(0,'りじぇめ');app.update();self.assertEqual(listbox().size(),2)
            search.event_generate('<Return>');app.update()
            self.assertEqual(entry.get(),'/ma ')  # IME/search Enter does not insert.
            listing=listbox();listing.selection_clear(0,'end');listing.selection_set(1)
            listing.focus_force();listing.event_generate('<Return>');app.update()
            self.assertEqual(controller.value.tokens[0].identity,'02010202')
            self.assertEqual(entry.get(),'/ma 【リジェネ】')
            entry.insert('end',' <me>');app.update();self.assertEqual(controller.value.display,entry.get())
            before=controller.value;entry.event_generate('<Tab>');app.update()
            controller.popup.event_generate('<Escape>');app.update();self.assertEqual(controller.value,before)
            entry.icursor(6);entry.insert(6,'x');self.assertEqual(controller.value,before)
            entry.event_generate('<BackSpace>');app.update()
            self.assertEqual(entry.get(),'/ma  <me>');self.assertEqual(controller.value.tokens,())
            self.assertFalse(errors,errors)
        finally:app.destroy()


    def test_main_editor_phrase_preview_apply_and_save(self):
        import tkinter as tk
        from tkinter import ttk
        from ff11reader.ui import ReaderWindow
        from ff11reader import application
        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)
        def button(parent,label):
            return next(w for w in descendants(parent) if isinstance(w,ttk.Button) and label in str(w.cget('text')))
        with isolated() as base,patch('ff11reader.adapters.LocalReader.load_phrases',return_value=PHRASES):
            f=PhraseFixture(base,'macro',1,1);app=tk.Tk();errors=[]
            app.report_callback_exception=lambda *args:errors.append(args)
            try:
                with patch('ff11reader.ui.Editor',return_value=f.editor):view=ReaderWindow(app,f.load())
                view.mode.set('マクロ');view.change_mode()
                macro=next(m for m in view.character.macros if macro_key(m)==f.specs[0]['key'])
                view.inspect_macro(macro);view.edit_selected_macro();app.update()
                editor=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
                fields=[w for w in descendants(editor) if isinstance(w,tk.Entry)]
                entry=fields[f.specs[0]['line']];entry.delete(0,'end');entry.insert(0,'/ma ')
                entry.focus_force();entry.event_generate('<Tab>');app.update()
                popup=next(w for w in descendants(editor) if isinstance(w,tk.Toplevel))
                search=next(w for w in descendants(popup) if type(w)==tk.Entry)
                search.insert(0,'リジェネ');app.update()
                listing=next(w for w in descendants(popup) if isinstance(w,tk.Listbox))
                listing.focus_force();listing.event_generate('<Return>');app.update()
                button(editor,'変更案を確認').invoke();app.update()
                preview=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel) and '作業データ' in w.title())
                button(preview,'作業データに適用').invoke();app.update()
                plan=f.preview();self.assertIn(bytes.fromhex('FD02010201FD'),plan.files[0].changes[0].replacement)
                before=f.bytes();button(app,'マクロの編集をゲームに保存').invoke();app.update()
                saving=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel) and 'ゲームへの保存' in w.title())
                self.assertEqual(f.bytes(),before)
                save=f.editor.save_macros
                with patch.object(application,'load_snapshot',side_effect=lambda _:f.load()),patch.object(f.editor,'save_macros',side_effect=lambda plan,root:save(plan,base/'backups')):
                    button(saving,'バックアップして').invoke();app.update()
                self.assertFalse(f.editor.session.dirty);self.assertFalse(errors,errors)
                f.reopen();self.assertIsNone(f.editor.blocked);self.assertFalse(f.editor.session.dirty)
            finally:app.destroy()
