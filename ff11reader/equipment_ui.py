"""Equipment slot input; selection rules live in the domain."""
import tkinter as tk
from tkinter import ttk
from . import dialogs
from .ui_actions import ActionButton


class SlotEditor:
    def __init__(self,parent,title,slot,rows,items,bags,on_preview):
        self.window=tk.Toplevel(parent,background='#080f22');self.window.title(title);self.window.geometry('820x560')
        self.rows=rows;self.visible=[];self.items=items;self.bags=bags;self.on_preview=on_preview
        ttk.Label(self.window,text=title,padding=12).pack(anchor='w')
        actions=ttk.Frame(self.window);actions.pack(fill='x',padx=12)
        self.action=tk.StringVar(value=slot.action if slot.action in ('keep','remove','equip') else 'keep')
        for value,label in [('keep','変更しない'),('remove','外す'),('equip','装備する')]:
            ttk.Radiobutton(actions,text=label,variable=self.action,value=value,command=self.toggle).pack(side='left',padx=10)
        ttk.Label(self.window,text='「変更しない」は、セット実行時の装備を維持します。',padding=12).pack(anchor='w')
        search=ttk.Frame(self.window);search.pack(fill='x',padx=12)
        ttk.Label(search,text='名前・種類ID').pack(side='left')
        self.query=tk.StringVar();entry=ttk.Entry(search,textvariable=self.query);entry.pack(side='left',fill='x',expand=True,padx=8)
        ttk.Button(search,text='検索',command=self.filter).pack(side='left');entry.bind('<Return>',lambda e:self.filter())
        frame=ttk.Frame(self.window);frame.pack(fill='both',expand=True,padx=12,pady=8)
        self.listing=ttk.Treeview(frame,columns=('name','id','bag','index'),show='headings',selectmode='browse',style='Macro.Treeview')
        for key,label,width in [('name','アイテム名',290),('id','種類ID',80),('bag','収納',150),('index','内部位置',80)]:
            self.listing.heading(key,text=label);self.listing.column(key,width=width,anchor='w')
        bar=ttk.Scrollbar(frame,command=self.listing.yview);self.listing.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');self.listing.pack(fill='both',expand=True)
        ttk.Label(self.window,text='全収納の持ち物から、この部位に対応する装備を表示しています。オーグメントは取得できません。',padding=12,wraplength=760).pack(anchor='w')
        self.count=ttk.Label(self.window);self.count.pack(anchor='w',padx=12)
        controls=ttk.Frame(self.window);controls.pack(fill='x',padx=12,pady=12)
        ttk.Button(controls,text='キャンセル',command=self.window.destroy).pack(side='right')
        self.preview_button=ActionButton(controls,busy=True,text='変更案を確認',command=self.preview);self.preview_button.pack(side='right',padx=8)
        self.filter()
        for i,row in enumerate(self.visible):
            if (row.item_id,row.container,row.index)==(slot.item_id,slot.container,slot.index):self.listing.selection_set(str(i));self.listing.see(str(i));break
        self.toggle();self.window.bind('<Escape>',lambda e:self.window.destroy())

    def filter(self):
        from .equipment_editing import search_rows
        self.visible=list(search_rows(self.rows,self.items,self.query.get()))
        self.listing.delete(*self.listing.get_children())
        for i,row in enumerate(self.visible):self.listing.insert('','end',iid=str(i),values=(self.items.get(row.item_id,{}).get('name') or f'ID {row.item_id}',row.item_id,self.bags[row.container],row.index))
        self.count.configure(text=f'候補 {len(self.visible)}件')

    def toggle(self):
        self.listing.state(['!disabled'] if self.action.get()=='equip' else ['disabled'])

    def preview(self):
        selection=None
        if self.action.get()=='equip':
            selected=self.listing.selection()
            if not selected:
                dialogs.showwarning('アイテムを選択','装備するアイテムの行を選んでください。',parent=self.window);return
            row=self.visible[int(selected[0])];selection=(row.item_id,row.container,row.index)
        self.on_preview(self.action.get(),selection,self.window)
