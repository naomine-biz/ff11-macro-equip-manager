"""Keyboard phrase picker and token-aware entry adapter."""
import tkinter as tk
from tkinter import ttk
from .text_editing import replace_range


class PhraseEntry:
    def __init__(self,entry,value,catalog):
        self.entry=entry;self.value=value;self.catalog=catalog;self.popup=None;self.updating=False
        command=entry.register(self.validate)
        entry.configure(validate='key',validatecommand=(command,'%d','%i','%S','%P'))
        entry.bind('<Tab>',self.open)
        entry.bind('<BackSpace>',lambda e:self.delete_token(True))
        entry.bind('<Delete>',lambda e:self.delete_token(False))

    def validate(self,action,index,fragment,proposed):
        if self.updating:return True
        if action not in ('0','1'):return True
        start=int(index);end=start+(len(fragment) if action=='0' else 0)
        try:updated=replace_range(self.value,start,end,fragment if action=='1' else '')
        except ValueError:self.entry.bell();return False
        if updated.display!=proposed:return False
        self.value=updated
        return True

    def selection(self):
        if self.entry.selection_present():a,b=int(self.entry.index('sel.first')),int(self.entry.index('sel.last'))
        else:a=b=int(self.entry.index('insert'))
        for token in self.value.tokens or ():
            if token.start<a<token.end:a=token.start
            if token.start<b<token.end:b=token.end
        return a,b

    def set_value(self,value,cursor):
        self.updating=True
        try:
            self.entry.delete(0,'end');self.entry.insert(0,value.display);self.value=value
            self.entry.icursor(cursor);self.entry.selection_clear()
        finally:self.updating=False

    def delete_token(self,backward):
        a,b=self.selection()
        if a!=b:
            self.set_value(replace_range(self.value,a,b,''),a);return 'break'
        pos=a-1 if backward else a
        for token in self.value.tokens or ():
            if token.start<=pos<token.end:
                self.set_value(replace_range(self.value,token.start,token.end,''),token.start);return 'break'

    def open(self,event=None):
        if self.popup and self.popup.winfo_exists():self.popup.lift();return 'break'
        start,end=self.selection()
        popup=self.popup=tk.Toplevel(self.entry,background='#080f22')
        popup.title('定型文を選択');popup.geometry('720x480');popup.transient(self.entry.winfo_toplevel())
        ttk.Label(popup,text='名前・読みで検索　／　カテゴリを選んで絞り込み',padding=10).pack(anchor='w')
        ttk.Label(popup,text='大分類',padding=(10,0)).pack(anchor='w')
        group=tk.StringVar(value='すべて')
        groups=ttk.Combobox(popup,textvariable=group,values=('すべて',)+self.catalog.groups,state='readonly')
        groups.pack(fill='x',padx=10,pady=(0,4))
        ttk.Label(popup,text='小分類',padding=(10,0)).pack(anchor='w')
        category=tk.StringVar(value='すべて')
        categories=ttk.Combobox(popup,textvariable=category,values=('すべて',),state='disabled')
        categories.pack(fill='x',padx=10,pady=(0,8))
        query=tk.StringVar()
        search=tk.Entry(popup,textvariable=query,bg='#101b38',fg='#edf1fa',insertbackground='white')
        search.pack(fill='x',padx=10)
        frame=ttk.Frame(popup);frame.pack(fill='both',expand=True,padx=10,pady=8)
        listing=tk.Listbox(frame,bg='#101b38',fg='#edf1fa',selectbackground='#354b7a',exportselection=False)
        scrollbar=ttk.Scrollbar(frame,command=listing.yview);listing.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y');listing.pack(side='left',fill='both',expand=True)
        status=ttk.Label(popup,padding=10);status.pack(anchor='w')
        ttk.Label(popup,text='大分類から選択　「すべて」でEnter: 全体検索へ　候補のEnter: 挿入　Esc: 取消',padding=10).pack(anchor='w')
        matches=[]
        def update(*_):
            matches[:]=self.catalog.search(query.get(),None if categories.current()==0 else category.get(),None if groups.current()==0 else group.get());listing.delete(0,'end')
            for phrase in matches:listing.insert('end',f'{phrase.name}  —  {phrase.category}  [{phrase.identity}]')
            if matches:listing.selection_set(0)
            status.configure(text=f'{len(matches)}件' if matches else '候補がありません。検索語を変えてください。')
        def close(*_):
            popup.destroy();self.popup=None;self.entry.focus_set();return 'break'
        def focus_list(*_):
            if matches:listing.focus_set()
            return 'break'
        def choose(*_):
            selected=listing.curselection()
            if not selected:return 'break'
            phrase=matches[selected[0]]
            self.set_value(replace_range(self.value,start,end,phrase.label,phrase.identity),start+len(phrase.label))
            return close()
        def type_query(event):
            if event.keysym=='BackSpace':
                search.focus_set();query.set(query.get()[:-1]);search.icursor('end');return 'break'
            if event.char and event.char.isprintable() and not event.state&4:
                search.focus_set();query.set(query.get()+event.char);search.icursor('end');return 'break'
        def change_group(*_):
            category.set('すべて')
            categories.configure(values=('すべて',)+self.catalog.categories_for(group.get()),state='disabled' if groups.current()==0 else 'readonly')
            update()
        query.trace_add('write',update)
        groups.bind('<<ComboboxSelected>>',change_group)
        groups.bind('<Return>',lambda e:((search if groups.current()==0 else categories).focus_set(),'break')[-1])
        categories.bind('<<ComboboxSelected>>',update)
        categories.bind('<Return>',lambda e:(search.focus_set(),'break')[-1])
        search.bind('<Shift-Tab>',lambda e:(groups.focus_set(),'break')[-1])
        search.bind('<Down>',focus_list);search.bind('<Return>',focus_list)
        listing.bind('<Return>',choose);listing.bind('<Double-Button-1>',choose);listing.bind('<KeyPress>',type_query)
        popup.bind('<Escape>',close);popup.protocol('WM_DELETE_WINDOW',close)
        update();groups.focus_set()
        return 'break'
