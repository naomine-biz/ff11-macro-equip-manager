import os
import unittest
from ff11reader.dictionaries import auto_translate
from ff11reader.phrases import PhraseCatalog

PHRASES={0x100:'ジョブアビリティ',0x101:'挑発',0x102:'かまえる',0x200:'魔法',0x201:'火門の計',0x202:'ケアル',0x203:' '}
READINGS={0x101:'チョウハツ',0x201:'カモンノケイ'}

class ReadingTests(unittest.TestCase):
    def test_decode_reading_without_changing_names(self):
        def record(key,name,reading):
            n=name.encode('cp932')+b'\0';r=reading.encode('cp932')+b'\0'
            return bytes([2,1,key>>8,key&255,len(n)])+n+bytes([len(r)])+r
        data=record(0x101,'挑発','チョウハツ')+record(0x202,'ケアル','')
        readings={};names=auto_translate(data,readings)
        self.assertEqual(names,auto_translate(data))
        self.assertEqual(readings,{0x101:'チョウハツ',0x202:''})
        with self.assertRaises(ValueError):auto_translate(data[:-1],{})

    def test_readings_categories_and_identity(self):
        catalog=PhraseCatalog(PHRASES,READINGS)
        for query in ['挑発','ちょうはつ','チョウハツ','ﾁｮｳﾊﾂ','ちょうはち']:
            self.assertEqual(catalog.search(query)[0].identity,'02010101')
        self.assertEqual(catalog.search('かもん')[0].name,'火門の計')
        self.assertEqual(catalog.search('けある')[0].name,'ケアル')
        self.assertFalse(catalog.search('ちょうはつ','魔法'))
        self.assertEqual(len(catalog.search('','魔法')),2)
        self.assertEqual(len(catalog.search('')),4)
        self.assertEqual(catalog.categories,('魔法','ジョブアビリティ'))

class CategoryTests(unittest.TestCase):
    def test_order_aliases_unknown_and_identity(self):
        source={0x100:'ジョブアビリティ２',0x101:'挑発',0x200:'ジョブアビリティ',0x201:'挑発',
                0x300:'アオマホウ',0x301:'青',0x400:'マホウ',0x401:'白',
                0x500:'ソウビブイ',0x501:'頭',0x600:'未知カテゴリ',0x601:'新規',
                0x700:'チメイ２',0x701:'地名候補',0x800:'チメイ',0x801:'地名候補'}
        catalog=PhraseCatalog(source)
        self.assertEqual(catalog.groups,('魔法','アビリティ','装備関連','その他'))
        self.assertEqual(catalog.categories_for('魔法'),('魔法','青魔法'))
        self.assertEqual(catalog.categories_for('アビリティ'),('ジョブアビリティ',))
        self.assertEqual([p.identity for p in catalog.search('',group='アビリティ')],['02010101','02010201'])
        self.assertEqual(len(catalog.search('',category='地名')),2)
        self.assertEqual(catalog.search('新規')[0].category,'未知カテゴリ')
        self.assertEqual(len(catalog.search('')),8)

@unittest.skipUnless(os.environ.get('FF11_RUN_INTEGRATION')=='1','Synthetic Tk check')
class ReadingUITests(unittest.TestCase):
    def test_tab_category_search_insert_cancel(self):
        import tkinter as tk
        from tkinter import ttk
        from ff11reader.phrase_ui import PhraseEntry
        from ff11reader.domain import Text
        app=tk.Tk();errors=[];app.report_callback_exception=lambda *args:errors.append(args)
        try:
            entry=tk.Entry(app);entry.pack()
            control=PhraseEntry(entry,Text('','','draft'),PhraseCatalog(PHRASES,READINGS))
            app.update();entry.focus_force();entry.event_generate('<Tab>');app.update()
            popup=control.popup
            search=next(w for w in popup.winfo_children() if type(w)==tk.Entry)
            groups,categories=[w for w in popup.winfo_children() if isinstance(w,ttk.Combobox)]
            listing=next(c for w in popup.winfo_children() for c in w.winfo_children() if isinstance(c,tk.Listbox))
            search.focus_force();search.event_generate('<Shift-Tab>');app.update()
            self.assertEqual(app.focus_get(),groups)
            self.assertEqual(listing.size(),4)
            groups.current(1);groups.event_generate('<<ComboboxSelected>>');app.update()
            self.assertEqual(listing.size(),2)
            groups.event_generate('<Return>');app.update();self.assertEqual(app.focus_get(),categories)
            categories.current(1);categories.event_generate('<<ComboboxSelected>>');app.update()
            self.assertEqual(listing.size(),2)
            groups.current(0);groups.event_generate('<<ComboboxSelected>>');app.update()
            self.assertEqual(listing.size(),4)
            self.assertEqual(categories.get(),'すべて')
            groups.current(1);groups.event_generate('<<ComboboxSelected>>');app.update()
            categories.event_generate('<Return>');app.update()
            search.insert(0,'かもん');app.update();self.assertEqual(listing.size(),1)
            groups.current(2);groups.event_generate('<<ComboboxSelected>>');app.update()
            self.assertEqual(search.get(),'かもん');self.assertEqual(listing.size(),0)
            groups.current(0);groups.event_generate('<<ComboboxSelected>>');app.update()
            self.assertEqual(listing.size(),1)
            search.focus_force();search.event_generate('<Return>');app.update();self.assertEqual(entry.get(),'')
            listing.focus_force();listing.event_generate('<Return>');app.update()
            self.assertEqual(control.value.tokens[0].identity,'02010201')
            before=control.value;entry.event_generate('<Tab>');app.update()
            control.popup.event_generate('<Escape>');app.update();self.assertEqual(control.value,before)
            self.assertFalse(errors,errors)
        finally:app.destroy()
