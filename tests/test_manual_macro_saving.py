"""General macro editing through synthetic files and guarded save transactions."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import random
import unittest
from unittest.mock import patch
from ff11reader import codecs, application, macro_saving
from ff11reader.dictionaries import resolve_token
from ff11reader.domain import Text
from ff11reader.edit_application import Editor
from ff11reader.editing import macro_key
from ff11reader.macro_text import patch_text
from tests.property_support import GameFixture, isolated, checksum, seeds
from tests.test_saving_properties import instrument


class ManualFixture(GameFixture):
    def load(self):
        result=super().load()
        resolver=lambda token:resolve_token(token,{},result.items)
        result.characters[0].macros=[]
        for page,path in enumerate(self.original):
            result.characters[0].macros.extend(codecs.macros(path.read_bytes(),page,resolver))
        return result

    def set_line(self,payload,page=0):
        path=list(self.original)[page];raw=bytearray(path.read_bytes());offset=self.specs[page]['offset']
        raw[offset:offset+61]=payload+b'\0'+b'Q'*(60-len(payload))
        path.write_bytes(checksum(raw))
        self.editor=Editor(self.load(),self.base/'draft.json')

    def edit(self,title=None,lines=None,page=0):
        key=self.specs[page]['key'];m=next(m for m in self.editor.snapshot().characters[0].macros if macro_key(m)==key)
        self.editor.apply(self.editor.prepare_macro_edit('abc',key,m.title.display if title is None else title,
            [x.display for x in m.lines] if lines is None else lines))

    def edit_line(self,after,page=0):
        key=self.specs[page]['key'];m=next(m for m in self.editor.snapshot().characters[0].macros if macro_key(m)==key)
        lines=[x.display for x in m.lines];lines[self.specs[page]['line']-1]=after
        self.edit(lines=lines,page=page)

    def preview(self):return self.editor.prepare_macro_save('abc','all')


class MacroTextTests(unittest.TestCase):
    def field(self,payload,width=61):return payload+b'\0'+b'Z'*(width-len(payload)-1)

    def test_byte_boundaries_and_literal_roundtrip(self):
        for title,limit,width in ((True,8,10),(False,60,61)):
            original=self.field(b'old',width)
            for length in (limit-1,limit,limit+1):
                for string in ('a'*length,'あ'*(length//2)+'a'*(length%2)):
                    with self.subTest(title=title,length=length,string=string):
                        if length>limit:
                            with self.assertRaisesRegex(ValueError,str(limit)):patch_text(original,'old',string,lambda _:None,title=title)
                        else:
                            output=patch_text(original,'old',string,lambda _:None,title=title)
                            payload=string.encode('cp932');expected=bytearray(original)
                            expected[:len(payload)+1]=payload+b'\0'
                            self.assertEqual(output,bytes(expected))
            for invalid in ('🙂','x\n','x\0','x\t','〜'):
                with self.subTest(title=title,invalid=invalid),self.assertRaises(ValueError):
                    patch_text(original,'old',invalid,lambda _:None,title=title)

    def test_token_identity_unknown_ambiguity_and_malformed_input(self):
        token=bytes.fromhex('fd07010064fd');other=bytes.fromhex('fd07010065fd')
        resolver=lambda _: '装備'
        raw=self.field(b'/echo '+token)
        output=patch_text(raw,'/echo 【装備】','/say 【装備】',resolver)
        self.assertEqual(output,self.field(b'/say '+token)[:len(b'/say '+token)+1]+raw[len(b'/say '+token)+1:])
        for bad in ('/echo 【別】','/echo 【装備','/echo 装備】','/echo {AT:07010066}'):
            with self.assertRaises(ValueError):patch_text(raw,'/echo 【装備】',bad,resolver)
        ambiguous=self.field(token+other)
        with self.assertRaisesRegex(ValueError,'一意'):patch_text(ambiguous,'【装備】【装備】','x【装備】',resolver)
        self.assertEqual(patch_text(ambiguous,'【装備】【装備】','【装備】【装備】',resolver),ambiguous)
        literal=self.field('【装備】'.encode('cp932')+token)
        with self.assertRaisesRegex(ValueError,'一意'):patch_text(literal,'【装備】【装備】','x【装備】',resolver)
        unknown=self.field(b'/echo '+token)
        result=patch_text(unknown,'/echo {AT:07010064}','/say {AT:07010064}',lambda _:None)
        self.assertIn(token,result)
        broken=self.field(b'\xfdabcd')
        with self.assertRaises(ValueError):patch_text(broken,codecs.text(broken).display,'new',resolver)

    def test_token_counts_toward_byte_limit(self):
        token=bytes.fromhex('fd07010064fd');raw=self.field(token)
        for n in (53,54,55):
            after='x'*n+'【装備】'
            if n==55:
                with self.assertRaisesRegex(ValueError,'60'):patch_text(raw,'【装備】',after,lambda _:'装備')
            else:self.assertEqual(patch_text(raw,'【装備】',after,lambda _:'装備')[:n+7],b'x'*n+token+b'\0')


class ManualMacroSavingTests(unittest.TestCase):
    def test_generated_names_all_lines_backup_and_unrelated_bytes(self):
        for seed in seeds():
            with self.subTest(seed=seed),isolated() as base:
                f=ManualFixture(base,'macro',seed,2);before=f.bytes();expected=dict(before)
                for page,spec in enumerate(f.specs):
                    title='魔法'+str(page);lines=[f'/echo {seed} 行{n}' for n in range(6)]
                    f.edit(title,lines,page)
                    path=list(f.original)[page];raw=bytearray(before[path]);key=spec['key']
                    record=24+((0 if key[2]=='ctrl' else 10)+key[3]-1)*380
                    for n,value in enumerate([title]+lines):
                        offset=record+370 if n==0 else record+4+(n-1)*61
                        payload=value.encode('cp932')+b'\0';raw[offset:offset+len(payload)]=payload
                    expected[path]=checksum(raw)
                plan=f.preview();self.assertEqual(sum(len(file.changes) for file in plan.files),14)
                self.assertEqual(f.bytes(),before)
                folder=f.save(plan);self.assertEqual(f.bytes(),expected);self.assertFalse(f.editor.session.dirty)
                receipt=json.loads((folder/'receipt.json').read_text(encoding='utf-8'));self.assertEqual(receipt['kind'],'macro-edit')
                for i,file in enumerate(plan.files):self.assertEqual((folder/f'{i:03}.original.dat').read_bytes(),before[Path(file.target)])
                f.reopen();self.assertIsNone(f.editor.blocked);self.assertFalse(f.editor.session.dirty)
                f.editor.undo();self.assertTrue(f.editor.session.dirty);self.assertEqual(f.bytes(),expected)
                f.editor.redo();self.assertFalse(f.editor.session.dirty)
                self.assertEqual(len(macro_saving.restore_macro_backup(folder)),2)

    def test_token_survives_repeated_edit_restart_delete_undo_and_save(self):
        with isolated() as base:
            f=ManualFixture(base,'macro',7,1);token=bytes.fromhex('fd07010064fd');f.set_line(b'/echo '+token)
            f.edit_line('/say 【Robe0】');f.edit_line('/echo 【Robe0】 <wait 1>')
            f.reopen();self.assertIsNone(f.editor.blocked)
            plan=f.preview();self.assertIn(token,plan.files[0].changes[0].replacement);f.save(plan)
            f.edit_line('/echo removed');f.save(f.preview());f.reopen();f.editor.undo()
            restored=f.preview();self.assertIn(token,restored.files[0].changes[0].replacement)
            f.save(restored);f.reopen();self.assertFalse(f.editor.session.dirty)
            self.assertIn(token,next(iter(f.original)).read_bytes())

    def test_plain_name_and_line_do_not_depend_on_inventory_or_dictionary(self):
        with isolated() as base:
            f=ManualFixture(base,'macro',1,1);f.edit('New',['/echo custom']+['']*5)
            with patch('ff11reader.adapters.LocalReader.load_phrases',side_effect=AssertionError('unneeded dictionary')):
                plan=f.preview()
                self.assertEqual({Path(p).name for p,_ in plan.dependencies},{'mcr.dat'})
                bag=f.folder/'wr.dat';data=bytearray(bag.read_bytes());data[4]^=1;bag.write_bytes(checksum(data))
                f.save(plan)
            self.assertFalse(f.editor.session.dirty)

    def test_invalid_input_blocks_plan_and_leaves_game_files_unchanged(self):
        for title,line in [('123456789','ok'),('ok','x'*61),('ok','🙂'),('ok','【New】')]:
            with self.subTest(title=title,line=line),isolated() as base:
                f=ManualFixture(base,'macro',0,1);before=f.bytes();f.edit(title,[line]+['']*5)
                with self.assertRaises(ValueError):f.preview()
                self.assertEqual(f.bytes(),before)

    def test_clearing_macro_and_unchanged_unknown_field_preservation(self):
        with isolated() as base:
            f=ManualFixture(base,'macro',42,1)
            f.set_line(b'/echo '+bytes.fromhex('fd02010001fd'))
            raw=next(iter(f.original)).read_bytes()
            f.edit(title='New')
            plan=f.preview();self.assertEqual([x.line for x in plan.files[0].changes],[0])
            offset=f.specs[0]['offset']
            self.assertEqual(plan.files[0].replacement[offset:offset+61],raw[offset:offset+61])
            f.save(plan)
            f.edit('', ['']*6);f.save(f.preview());f.reopen()
            key=f.specs[0]['key'];m=next(m for m in f.editor.snapshot().characters[0].macros if macro_key(m)==key)
            self.assertEqual(m.title.display,'');self.assertTrue(all(x.display=='' for x in m.lines))

    def test_stale_target_tampered_plan_and_changed_buffer_are_rejected(self):
        for mode in ('target','plan','working'):
            with self.subTest(mode=mode),isolated() as base:
                f=ManualFixture(base,'macro',1,1);f.edit('New',['/echo custom']+['']*5);plan=f.preview()
                if mode=='working':f.editor.undo()
                elif mode=='plan':plan=replace(plan,files=(replace(plan.files[0],replacement=plan.files[0].original),))
                else:
                    path=Path(plan.files[0].target);raw=bytearray(path.read_bytes());raw[0]^=1;path.write_bytes(bytes(raw))
                before=f.bytes()
                with self.assertRaises(ValueError):f.save(plan)
                self.assertEqual(f.bytes(),before)

    def test_two_file_failure_rolls_back_and_checkpoint_failure_recovers(self):
        for failure in ('replace','checkpoint'):
            with self.subTest(failure=failure),isolated() as base:
                f=ManualFixture(base,'macro',19,2)
                f.edit('One',['/echo one']+['']*5,0);f.edit('Two',['/echo two']+['']*5,1)
                before=f.bytes();plan=f.preview()
                if failure=='replace':
                    with instrument(f,'replaced',1):
                        with self.assertRaises(RuntimeError):f.save(plan)
                    self.assertEqual(f.bytes(),before);self.assertTrue(f.editor.session.dirty)
                else:
                    save=f.editor.store.save;calls=0
                    def broken(session):
                        nonlocal calls
                        calls+=1
                        if calls==2:raise OSError('synthetic checkpoint failure')
                        return save(session)
                    with patch.object(f.editor.store,'save',side_effect=broken):
                        with self.assertRaises(RuntimeError):f.save(plan)
                    f.reopen();self.assertIsNone(f.editor.blocked);self.assertFalse(f.editor.session.dirty)

    @unittest.skipUnless(os.environ.get('FF11_RUN_INTEGRATION')=='1','Enable synthetic Tk checks')
    def test_main_button_opens_general_preview_and_saves_fixture(self):
        import tkinter as tk
        from tkinter import ttk
        from ff11reader.ui import ReaderWindow
        with isolated() as base:
            f=ManualFixture(base,'macro',1,1);f.edit('New',['/echo custom']+['']*5)
            app=tk.Tk();app.withdraw();errors=[];app.report_callback_exception=lambda *args:errors.append(args)
            def find(parent,label):
                for child in parent.winfo_children():
                    if isinstance(child,ttk.Button) and label in str(child.cget('text')):return child
                    result=find(child,label)
                    if result:return result
            try:
                with patch('ff11reader.ui.Editor',return_value=f.editor):view=ReaderWindow(app,f.load())
                before=f.bytes();find(app,'マクロの編集をゲームに保存').invoke();app.update()
                window=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
                detail=next(w for w in window.winfo_children() if isinstance(w,tk.Text)).get('1.0','end')
                self.assertIn('名前',detail);self.assertIn('/echo custom',detail);self.assertEqual(f.bytes(),before)
                save=f.editor.save_macros
                with patch.object(application,'load_snapshot',side_effect=lambda _:f.load()),patch.object(f.editor,'save_macros',side_effect=lambda plan,root:save(plan,base/'backups')):
                    find(window,'バックアップして').invoke();app.update()
                self.assertFalse(f.editor.session.dirty);self.assertFalse(errors,errors)
            finally:app.destroy()
