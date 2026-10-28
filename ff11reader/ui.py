"""Graphical workspace with explicit, guarded equipment reference saving."""
from collections import Counter
from datetime import datetime
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from .application import set_character_label, preview_reference_fixes
from .presentation import present_slot
from .macro_links import is_empty
from .edit_application import Editor
from .editing import plan_macro_fixes, macro_key
from .macro_inventory import assess_macro_inventory, LABELS as MACRO_ITEM_LABELS
from .application import inspect_macro_set_links, inspect_wardrobe_usage
from pathlib import Path


ACTION_STYLE = {
 'match': ('一致', '#101e36', '#89dda3'),
 'fixable': ('Fix可能', '#101e36', '#87bfff'),
 'multiple': ('候補が複数', '#101e36', '#f3ce77'),
 'missing': ('候補なし', '#101e36', '#ef9994'),
 'needs_review': ('要確認', '#101e36', '#c6a5ee'),
 'not_applicable': ('', '#0d172c', '#7e8ca9'),
}
OBSERVATIONS = {'cache_match':'登録した位置と種類IDが持ち物データと一致',
 'cache_item_mismatch':'登録した位置にあるアイテムの種類IDが異なる',
 'cache_position_empty':'登録した位置にアイテムが見つからない',
 'cache_unavailable':'対象の収納データを読み取れていない',
 'invalid_reference':'保存された参照値が想定範囲外',
 'unknown_action':'装備枠の動作を判別できない',
 'ambiguous_position':'同じ収納・位置のデータが重複', 'unassessed':'未評価', 'not_applicable':'対象外'}
BAGS={0:'マイバッグ',1:'モグ金庫',2:'収納家具',3:'一時アイテム',4:'ロッカー',5:'サッチェル',6:'サック',7:'ケース',8:'ワードローブ1',9:'モグ金庫2',**{i+8:f'ワードローブ{i}' for i in range(2,9)}}
SLOTS={'main':'メイン','sub':'サブ','range':'遠隔','ammo':'矢弾','head':'頭','neck':'首','ear1':'左耳','ear2':'右耳','body':'胴','hands':'両手','ring1':'左指','ring2':'右指','back':'背','waist':'腰','legs':'両脚','feet':'両足'}
GRID='main sub range ammo head neck ear1 ear2 body hands ring1 ring2 back waist legs feet'.split()


class ReaderWindow:
 def __init__(self, app, snapshot):
  self.app=app;self.snapshot=snapshot;self.photos={};self.card_widgets={};self.navigation=[];self.selected=None
  self.editor=Editor(snapshot);self.snapshot=self.editor.snapshot();self.active_macro=None
  app.title('FF11 ワークスペース 0.9');app.geometry('1440x900');app.minsize(1120,720);app.configure(bg='#080f22')
  style=ttk.Style(app);style.theme_use('clam')
  app.option_add('*Font',('MS Gothic',10));app.option_add('*TCombobox*Listbox.background','#111f40');app.option_add('*TCombobox*Listbox.foreground','#f4f5f8');app.option_add('*TCombobox*Listbox.selectBackground','#354b7a')
  style.configure('.',background='#080f22',foreground='#edf1fa',font=('MS Gothic',10))
  style.configure('TFrame',background='#080f22');style.configure('TLabel',background='#080f22',foreground='#edf1fa')
  style.configure('Game.TFrame',background='#101b38',relief='ridge',borderwidth=2)
  style.configure('TButton',background='#182b53',foreground='#f3f5ff',bordercolor='#8491b2',lightcolor='#9aa7c4',darkcolor='#354267',padding=(10,5))
  style.map('TButton',background=[('active','#2b416e')])
  style.configure('Game.TRadiobutton',background='#142345',foreground='#e9edf8',padding=(12,7),indicatorrelief='flat')
  style.map('Game.TRadiobutton',background=[('selected','#354b7a'),('active','#23385f')],foreground=[('selected','#fff3c4')])
  style.configure('TCombobox',fieldbackground='#111f40',background='#263b65',foreground='#f4f5f8',arrowcolor='#dce5ff',bordercolor='#8491b2')
  style.map('TCombobox',fieldbackground=[('readonly','#111f40')],foreground=[('readonly','#f4f5f8')],selectbackground=[('readonly','#111f40')],selectforeground=[('readonly','#f4f5f8')])
  style.configure('Vertical.TScrollbar',background='#263958',troughcolor='#0b1429',arrowcolor='#bac6e2')
  style.configure('TPanedwindow',background='#080f22')
  style.configure('Macro.Treeview',background='#101b38',fieldbackground='#101b38',foreground='#edf1fa',rowheight=26,font=('MS Gothic',11),borderwidth=0)
  style.configure('Macro.Treeview.Heading',background='#182b53',foreground='#edf1fa')
  style.map('Macro.Treeview.Heading',background=[('active','#263b65')],foreground=[('active','#ffffff')])
  style.map('Macro.Treeview',background=[('selected','#354b7a')],foreground=[('selected','#fff3c4')])
  style.configure('TNotebook',background='#080f22',bordercolor='#8491b2')
  style.configure('TNotebook.Tab',background='#182b53',foreground='#edf1fa',padding=(14,8),lightcolor='#8491b2',darkcolor='#354267')
  style.map('TNotebook.Tab',padding=[('selected',(14,8)),('!selected',(14,8))],background=[('selected','#354b7a'),('active','#263b65'),('!selected','#182b53')],foreground=[('selected','#fff3c4'),('active','#ffffff'),('!selected','#edf1fa')])
  header=ttk.Frame(app,padding=(18,14));header.pack(fill='x')
  ttk.Label(header,text='FINAL FANTASY XI   /   マクロ・装備',font=('MS Gothic',17,'bold')).pack(side='left')
  ttk.Label(header,text='編集バッファ · 作業ファイルへ自動保存').pack(side='right')
  toolbar=ttk.Frame(app,padding=(18,0,18,12));toolbar.pack(fill='x')
  ttk.Label(toolbar,text='キャラクター').pack(side='left',padx=(0,8))
  self.character_choice=ttk.Combobox(toolbar,state='readonly',width=35,values=self.character_labels());self.character_choice.pack(side='left')
  self.character_choice.bind('<<ComboboxSelected>>',self.change_character)
  ttk.Button(toolbar,text='表示名を登録',command=self.rename).pack(side='left',padx=8)
  self.mode=tk.StringVar(value='装備セット')
  for mode in ['マクロ','装備セット','インベントリ']:
   ttk.Radiobutton(toolbar,text=mode,value=mode,variable=self.mode,command=self.change_mode,style='Game.TRadiobutton').pack(side='left',padx=10)
  body=ttk.Panedwindow(app,orient='horizontal');body.pack(fill='both',expand=True,padx=18,pady=(0,8))
  left=ttk.Frame(body,padding=8,style='Game.TFrame');center=ttk.Frame(body,padding=8,style='Game.TFrame');right=ttk.Frame(body,padding=12,style='Game.TFrame')
  body.add(left,weight=0);body.add(center,weight=1);body.add(right,weight=0)
  left.configure(width=230);right.configure(width=370)
  self.nav_title=ttk.Label(left,text='',font=('MS Gothic',12,'bold'));self.nav_title.pack(anchor='w',pady=(0,8))
  self.nav=tk.Listbox(left,width=27,activestyle='none',exportselection=False,borderwidth=0,font=('MS Gothic',11),bg='#101b38',fg='#edf1fa',highlightthickness=0,selectbackground='#354b7a',selectforeground='#fff3c4')
  nav_scroll=ttk.Scrollbar(left,command=self.nav.yview);self.nav.configure(yscrollcommand=nav_scroll.set)
  nav_scroll.pack(side='right',fill='y');self.nav.pack(fill='both',expand=True);self.nav.bind('<<ListboxSelect>>',self.select_navigation)
  self.nav_scroll=nav_scroll
  self.macro_tree=ttk.Treeview(left,show='tree',selectmode='browse',style='Macro.Treeview')
  self.macro_tree.column('#0',width=230,minwidth=160,stretch=True)
  self.macro_tree.tag_configure('empty',foreground='#7e8ca9')
  self.macro_tree.configure(yscrollcommand=nav_scroll.set)
  self.macro_tree.bind('<<TreeviewSelect>>',self.select_macro_palette)
  self.macro_tree.bind('<<TreeviewOpen>>',self.open_macro_book)
  self.heading=ttk.Label(center,text='',font=('MS Gothic',16,'bold'));self.heading.pack(anchor='w')
  self.subtitle=ttk.Label(center,text='');self.subtitle.pack(anchor='w',pady=(4,10))
  self.canvas=tk.Canvas(center,bg='#080f22',highlightthickness=0,width=650)
  scroll=ttk.Scrollbar(center,command=self.canvas.yview);self.canvas.configure(yscrollcommand=scroll.set)
  scroll.pack(side='right',fill='y');self.canvas.pack(fill='both',expand=True)
  self.cards=tk.Frame(self.canvas,bg='#080f22');self.canvas_window=self.canvas.create_window(0,0,window=self.cards,anchor='nw')
  self.cards.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
  self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.canvas_window,width=e.width))
  self.canvas.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-int(e.delta/120),'units'))
  ttk.Button(right,text='マクロと装備セットの参照確認',command=self.show_macro_links).pack(fill='x',pady=(0,6))
  ttk.Button(right,text='装備セットの参照位置を補正',command=self.preview_fixes).pack(fill='x',pady=(0,6))
  ttk.Button(right,text='マクロの収納番号を確認・補正',command=self.show_macro_inventory).pack(fill='x',pady=(0,6))
  ttk.Button(right,text='ワードローブの未参照アイテム',command=self.show_unused_wardrobe).pack(fill='x',pady=(0,6))
  self.edit_button=ttk.Button(right,text='選択マクロを編集',command=self.edit_selected_macro,state='disabled');self.edit_button.pack(fill='x',pady=(0,6))
  history=ttk.Frame(right);history.pack(fill='x',pady=(0,6))
  self.undo_button=ttk.Button(history,text='Undo',command=self.undo_fix);self.undo_button.pack(side='left',expand=True,fill='x')
  self.redo_button=ttk.Button(history,text='Redo',command=self.redo_edit);self.redo_button.pack(side='left',expand=True,fill='x')
  self.draft_label=ttk.Label(right,text='');self.draft_label.pack(fill='x')
  ttk.Button(right,text='装備セットの補正をゲームに保存…',command=self.preview_equipment_save).pack(fill='x',pady=(0,6))
  ttk.Button(right,text='マクロの収納番号をゲームに保存…',command=self.preview_game_save).pack(fill='x',pady=(0,6))
  ttk.Button(right,text='作業ファイルを保管して編集をリセット',command=self.reset_edits).pack(fill='x',pady=(0,6))
  ttk.Label(right,text='Item / Help',font=('MS Gothic',14,'bold')).pack(anchor='w',pady=(0,12))
  self.detail=tk.Text(right,width=38,wrap='word',font=('MS Gothic',10),bg='#101b38',fg='#edf1fa',insertbackground='white',selectbackground='#354b7a',relief='sunken',borderwidth=1,padx=12,pady=12,state='disabled')
  self.detail.pack(fill='both',expand=True)
  self.detail.tag_configure('title',font=('MS Gothic',13,'bold'),foreground='#fff1c0')
  self.evidence=None
  self.details_button=ttk.Button(right,text='判定の詳細',command=self.show_evidence,state='disabled');self.details_button.pack(fill='x',pady=(8,0))
  self.actions=ttk.Frame(right);self.actions.pack(fill='x',pady=8)
  self.candidate_menu=tk.Menu(app,tearoff=False,bg='#101b38',fg='#edf1fa')
  self.candidate_button=ttk.Menubutton(self.actions,text='候補を見る',menu=self.candidate_menu,state='disabled')
  self.candidate_button.pack(fill='x')
  legend=ttk.Frame(app,padding=(18,4,18,10));legend.pack(fill='x')
  for status in ['match','fixable','multiple','missing']:
   label,bg,fg=ACTION_STYLE[status];tk.Label(legend,text='● '+label,fg=fg,bg='#080f22',font=('MS Gothic',10)).pack(side='left',padx=(0,22))
  self.footer=ttk.Label(app,text='装備枠をクリックすると、必要な操作を確認できます。',padding=(18,0,18,8));self.footer.pack(fill='x')
  if snapshot.characters:
   self.character_choice.current(next((i for i,c in enumerate(snapshot.characters) if c.equipment_references),0));self.change_character()
  else:self.show_detail('キャラクターなし','読み取れたキャラクターフォルダはありません。')
  self.update_edit_status()
  if self.editor.blocked:self.app.after_idle(lambda:messagebox.showwarning('作業再開の確認',self.editor.blocked,parent=self.app))

 @property
 def character(self):
  i=self.character_choice.current();return self.snapshot.characters[i] if i>=0 else None

 def character_labels(self):return [(c.display_name or '名前未確認')+f' [{c.folder_id}]' for c in self.snapshot.characters]
 def equipset_label(self,number,character=None):
  c=character or self.character
  equipset=next((e for e in c.equipsets if e.number==number),None) if c else None
  title=equipset.title.display if equipset else ''
  return f'{number:03}  {title or "（名称なし）"}'
 def item_name(self,item):return self.snapshot.items.get(item,{}).get('name') or (f'ID {item}' if item is not None else '—')
 def icon(self,item):
  if item not in self.photos:
   raw=self.snapshot.items.get(item,{}).get('icon_png')
   try:self.photos[item]=tk.PhotoImage(master=self.app,data=raw).zoom(2,2) if raw else None
   except tk.TclError:self.photos[item]=None
  return self.photos[item]
 def rename(self):
  if not self.character:return
  name=simpledialog.askstring('表示名を登録','アプリ専用の表示名（空欄で解除）',initialvalue=self.character.display_name or '',parent=self.app)
  if name is None:return
  try:set_character_label(self.snapshot,self.character,name)
  except (ValueError,OSError) as e:messagebox.showerror('保存できません',str(e));return
  i=self.character_choice.current();self.character_choice.configure(values=self.character_labels());self.character_choice.current(i)
 def preview_fixes(self):
  c=self.character
  if not c:return
  plan=preview_reference_fixes(self.snapshot,c)
  window=tk.Toplevel(self.app,background='#080f22');window.title('装備セットの参照位置を補正 / プレビュー');window.geometry('950x650')
  ttk.Label(window,text=f'{c.folder_id}  ·  更新案 {len(plan.changes)}枠  ·  保留 {len(plan.issues)}枠',padding=12).pack(anchor='w')
  ttk.Label(window,text='変更前後を確認して、アプリ内の作業データに適用してください。',padding=8).pack(anchor='w')
  text=tk.Text(window,wrap='word',bg='#101b38',fg='#edf1fa',font=('MS Gothic',11),padx=12,pady=12)
  text.pack(fill='both',expand=True,padx=12)
  for x in plan.changes:
   text.insert('end',f'{self.equipset_label(x.equipset,c)} / {SLOTS[x.slot]}  {self.item_name(x.item_id)} (ID {x.item_id})\n  {BAGS.get(x.before[0],x.before[0])} / {x.before[1]} → {BAGS[x.after[0]]} / {x.after[1]}\n\n')
  reasons={'invalid_reference':'参照値不正','incomplete_inventory':'取得不足','not_observed':'候補なし','multiple_candidates':'同IDが複数','ambiguous_target':'候補位置が不正・重複','quantity_not_one':'数量が1ではない'}
  if plan.issues:
   text.insert('end','保留\n')
   for x in plan.issues:text.insert('end',f'{self.equipset_label(x.equipset,c)} / {SLOTS[x.slot]}: {reasons[x.reason]}\n')
  if not plan.changes:text.insert('end','適用できるFix案はありません。')
  text.configure(state='disabled')
  def apply():
   try:self.editor.equipment_fixes(c.folder_id,plan)
   except (ValueError,OSError) as e:messagebox.showerror('適用できません',str(e),parent=window);return
   window.destroy();self.refresh_edits()
   self.footer.configure(text=f'アプリ内の作業データに {len(plan.changes)}枠のFixを適用しました。')
  ttk.Button(window,text='この案をアプリ内に適用（ゲームへの保存なし）',command=apply,state='normal' if plan.changes else 'disabled').pack(side='right',padx=12,pady=12)
  ttk.Button(window,text='閉じる',command=window.destroy).pack(side='right',pady=12)
 def update_edit_status(self):
  cursor,history_length,dirty=self.editor.edit_status()
  self.undo_button.configure(state='normal' if cursor and not self.editor.blocked else 'disabled')
  self.redo_button.configure(state='normal' if cursor<history_length and not self.editor.blocked else 'disabled')
  self.draft_label.configure(text='作業再開の確認が必要' if self.editor.blocked else f'編集中 {cursor}操作 · '+('変更あり' if dirty else '保存済み状態'))
 def refresh_edits(self):
  selected=self.selected;address=self.active_macro
  self.snapshot=self.editor.snapshot()
  self.change_mode()
  if self.mode.get()=='マクロ' and address:
   item=f'palette-{address[0]}-{address[1]}'
   self.macro_tree.selection_set(item);self.macro_tree.see(item);self.select_macro_palette()
   macro=next(m for m in self.character.macros if macro_key(m)==address);self.inspect_macro(macro)
  elif self.mode.get()=='装備セット' and selected:
   index=next((i for i,e in enumerate(self.navigation) if e.number==selected.number),0)
   self.nav.selection_clear(0,'end');self.nav.selection_set(index);self.nav.see(index);self.select_navigation()
  self.update_edit_status()
 def undo_fix(self):
  try:self.editor.undo()
  except (OSError,ValueError) as e:messagebox.showerror('Undo',str(e),parent=self.app);return
  self.refresh_edits()
 def redo_edit(self):
  try:self.editor.redo()
  except (OSError,ValueError) as e:messagebox.showerror('Redo',str(e),parent=self.app);return
  self.refresh_edits()
 def reset_edits(self):
  if not messagebox.askyesno('編集をリセット','現在の作業ファイルを保管し、読込時の状態から編集を開始しますか？',parent=self.app):return
  try:self.editor.start_fresh()
  except (OSError,ValueError) as e:messagebox.showerror('リセット',str(e),parent=self.app);return
  self.refresh_edits()
 def preview_game_save(self):
  if not self.character:return
  try:plan=self.editor.prepare_macro_save(self.character.folder_id)
  except (OSError,ValueError,RuntimeError) as e:messagebox.showerror('保存プレビュー',str(e),parent=self.app);return
  window=tk.Toplevel(self.app,background='#080f22');window.title('マクロ収納番号Fix / ゲームへの保存');window.geometry('980x680')
  count=sum(len(f.changes) for f in plan.files)
  ttk.Label(window,text=f'{self.character.display_name or self.character.folder_id} · {count}行 / {len(plan.files)}ファイル · 保留 {plan.deferred}件（詳細は下記）',padding=10).pack(anchor='w')
  ttk.Label(window,text='FF11とPlayOnlineを終了してから保存してください。対象ファイルをすべてバックアップして保存します。保存完了まではゲームを起動しないでください。',padding=10).pack(anchor='w')
  text=tk.Text(window,bg='#101b38',fg='#edf1fa',wrap='word',padx=12,pady=12)
  bar=ttk.Scrollbar(window,command=text.yview);text.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');text.pack(fill='both',expand=True)
  for file in plan.files:
   text.insert('end',file.target+'\n')
   for change in file.changes:
    b,p,bank,key=change.address
    text.insert('end',f'ブック {b:02} / パレット {p} / {bank.upper()} {key if key<10 else 0} / {change.line}行目\n  前: {change.before}\n  後: {change.after}\n\n')
  if plan.deferred_changes:
   text.insert('end','作業データに残す変更\n')
   for change in plan.deferred_changes:text.insert('end',f'{change.target}: {change.reason}\n')
  text.configure(state='disabled')
  def save():
   button.configure(state='disabled');window.update_idletasks()
   try:backup=self.editor.save_macros(plan,Path(__file__).resolve().parent.parent/'backups'/'macros')
   except (OSError,ValueError,RuntimeError) as e:
    self.update_edit_status();messagebox.showerror('ゲームへの保存',str(e),parent=window);button.configure(state='normal');return
   window.destroy();self.refresh_edits();self.footer.configure(text=f'{count}行を保存・検証しました。バックアップ: {backup}')
  button=ttk.Button(window,text=f'バックアップして{count}行をゲームに保存',command=save);button.pack(pady=12)
 def preview_equipment_save(self):
  if not self.character:return
  try:plan=self.editor.prepare_equipment_save(self.character.folder_id)
  except (OSError,ValueError,RuntimeError) as e:messagebox.showerror('保存プレビュー',str(e),parent=self.app);return
  window=tk.Toplevel(self.app,background='#080f22');window.title('装備セットの補正 / ゲームへの保存');window.geometry('980x680')
  count=sum(len(f.changes) for f in plan.files)
  ttk.Label(window,text=f'{self.character.display_name or self.character.folder_id} · {count}枠 / {len(plan.files)}ファイル · 保留 {plan.deferred}件（詳細は下記）',padding=10).pack(anchor='w')
  ttk.Label(window,text='FF11とPlayOnlineを終了してから保存してください。対象ファイルをすべてバックアップして保存します。保存完了まではゲームを起動しないでください。',padding=10).pack(anchor='w')
  text=tk.Text(window,bg='#101b38',fg='#edf1fa',wrap='word',padx=12,pady=12)
  bar=ttk.Scrollbar(window,command=text.yview);text.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');text.pack(fill='both',expand=True)
  for file in plan.files:
   text.insert('end',file.target+'\n')
   for change in file.changes:
    text.insert('end',f'{self.equipset_label(change.equipset,self.character)} / {SLOTS[change.slot]} / {self.item_name(change.item_id)} (ID {change.item_id})\n  前: {BAGS.get(change.before[0],change.before[0])} / 位置 {change.before[1]}\n  後: {BAGS[change.after[0]]} / 位置 {change.after[1]}\n\n')
  if plan.deferred_changes:
   text.insert('end','作業データに残す変更\n')
   for change in plan.deferred_changes:text.insert('end',f'{change.target}: {change.reason}\n')
  text.configure(state='disabled')
  def save():
   button.configure(state='disabled');window.update_idletasks()
   try:backup=self.editor.save_equipment(plan,Path(__file__).resolve().parent.parent/'backups'/'equipment')
   except (OSError,ValueError,RuntimeError) as e:
    self.update_edit_status();messagebox.showerror('ゲームへの保存',str(e),parent=window);button.configure(state='normal');return
   window.destroy();self.refresh_edits();self.footer.configure(text=f'{count}枠を保存・検証しました。バックアップ: {backup}')
  button=ttk.Button(window,text=f'バックアップして{count}枠をゲームに保存',command=save);button.pack(pady=12)
 def change_character(self,event=None):self.change_mode()
 def change_mode(self):
  if not self.character:return
  self.active_macro=None;self.edit_button.configure(state='disabled')
  self.nav.delete(0,'end');c=self.character;mode=self.mode.get();self.navigation=[]
  self.macro_tree.delete(*self.macro_tree.get_children())
  self.macro_tree.pack_forget();self.nav.pack_forget()
  active=self.macro_tree if mode=='マクロ' else self.nav
  active.pack(fill='both',expand=True);self.nav_scroll.configure(command=active.yview)
  self.fix_plan=preview_reference_fixes(self.snapshot,c)
  self.macro_links=inspect_macro_set_links(self.snapshot,c)
  self.macro_item_refs=assess_macro_inventory(c,self.snapshot.items)
  if mode=='装備セット':
   self.nav_title.configure(text='装備セット')
   self.navigation=c.equipsets
   for e in self.navigation:
    self.nav.insert('end',self.equipset_label(e.number)+('  [マクロ参照なし]' if e.number in self.macro_links.unreferenced else ''))
    if is_empty(e):self.nav.itemconfigure(self.nav.size()-1,foreground='#7e8ca9',selectforeground='#a6aec0')
  elif mode=='マクロ':
   self.nav_title.configure(text='ブック / パレット')
   self.navigation=sorted({(m.book,m.palette) for m in c.macros})
   for book in sorted({b for b,_ in self.navigation}):
    title=c.books.get(book)
    self.macro_tree.insert('','end',iid=f'book-{book}',text=f'{book:02}  '+((title.display.strip() if title else '') or '（名前なし）'),open=False)
   for book,palette in self.navigation:
    macros=[m for m in c.macros if (m.book,m.palette)==(book,palette)]
    empty=all(not m.title.display.strip() and all(not line.display.strip() for line in m.lines) for m in macros)
    self.macro_tree.insert(f'book-{book}','end',iid=f'palette-{book}-{palette}',text=f'パレット {palette}',tags=('empty',) if empty else ())
   for book in self.macro_tree.get_children():
    if all('empty' in self.macro_tree.item(palette,'tags') for palette in self.macro_tree.get_children(book)):
     self.macro_tree.item(book,tags=('empty',))
  else:
   self.nav_title.configure(text='収納')
   self.navigation=list(BAGS)
   counts=Counter(r.container for r in c.inventory)
   for bag in self.navigation:self.nav.insert('end',f'{BAGS[bag]}  ·  {counts[bag]}')
  if self.navigation:
   if mode=='マクロ':
    book,palette=self.navigation[0];self.macro_tree.selection_set(f'palette-{book}-{palette}');self.select_macro_palette()
   else:self.nav.selection_set(0);self.select_navigation()
  else:
   self.clear_cards();self.heading.configure(text=mode);self.subtitle.configure(text='読み取れたデータがありません。');self.show_detail('データなし','インベントリ保存情報や設定ファイルが未取得の場合もあります。')
 def clear_cards(self):
  for w in self.cards.winfo_children():w.destroy()
  self.card_widgets={};self.active_card=None
  for column in range(10):self.cards.columnconfigure(column,weight=0,minsize=0)
  self.canvas.yview_moveto(0)
 def expand_macro_book(self,item):
  book=self.macro_tree.parent(item) or item
  for sibling in self.macro_tree.get_children():
   self.macro_tree.item(sibling,open=sibling==book)
 def open_macro_book(self,event=None):
  item=self.macro_tree.focus()
  if item:self.expand_macro_book(item)
 def select_macro_palette(self,event=None):
  if self.mode.get()!='マクロ':return
  selection=self.macro_tree.selection()
  if not selection:return
  self.expand_macro_book(selection[0])
  parts=selection[0].split('-')
  if parts[0]=='book':
   self.active_macro=None;self.edit_button.configure(state='disabled')
   self.clear_cards();self.selected=None
   self.heading.configure(text=self.macro_tree.item(selection[0],'text'))
   self.subtitle.configure(text='パレットを選択してください。')
   self.show_detail('ブック','左のツリーからパレットを選択してください。');return
  value=(int(parts[1]),int(parts[2]))
  if event is not None and self.selected==value:return
  self.clear_cards();self.selected=value;self.render_macros(value)
 def select_navigation(self,event=None):
  selection=self.nav.curselection()
  if not selection:return
  value=self.navigation[selection[0]];self.clear_cards();self.selected=value
  mode=self.mode.get()
  if mode=='装備セット':self.render_equipment(value)
  elif mode=='マクロ':self.render_macros(value)
  else:self.render_inventory(value)
 def show_evidence(self):
  if not self.evidence:return
  title,body=self.evidence
  window=tk.Toplevel(self.app,background='#080f22');window.title('詳細 / '+title);window.geometry('780x650')
  text=tk.Text(window,wrap='word',bg='#101b38',fg='#edf1fa',font=('MS Gothic',11),padx=14,pady=14)
  bar=ttk.Scrollbar(window,command=text.yview);text.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');text.pack(fill='both',expand=True)
  text.insert('end',body);text.configure(state='disabled')
 def show_detail(self,title,text,actions=(),evidence=None):
  self.evidence=(title,evidence) if evidence else None
  self.details_button.configure(state='normal' if evidence else 'disabled')
  self.detail.configure(state='normal');self.detail.delete('1.0','end');self.detail.insert('end',title+'\n\n','title');self.detail.insert('end',text);self.detail.configure(state='disabled')
  self.candidate_menu.delete(0,'end')
  for label,command in actions:self.candidate_menu.add_command(label=label,command=command)
  self.candidate_button.configure(state='normal' if actions else 'disabled',text=f'候補の場所を見る ({len(actions)})' if actions else '候補の場所を見る')
 def card(self,index,title,caption,command,item=None,state=None,badge=None,compact=False):
  label,bg,fg=ACTION_STYLE[state] if state is not None else ('','#101e36','#8295b8')
  height=88 if compact else 148
  frame=tk.Canvas(self.cards,bg=bg,highlightbackground=fg,highlightthickness=1,borderwidth=0,width=48 if compact else 142,height=height)
  frame.normal_border=fg
  columns=10 if compact else 4
  row=index//10*2+1 if compact else index//4
  frame.grid(row=row,column=index%columns,padx=2 if compact else 5,pady=5,sticky='nsew')
  self.cards.columnconfigure(index%columns,weight=1)
  border=frame.create_rectangle(2,2,140,height-3,outline='#52617e')
  title_id=frame.create_text(70,14,text=title,fill=fg,font=('MS Gothic',10,'bold'))
  photo=self.icon(item) if item is not None else None
  image_id=None
  if not compact:
   image_id=frame.create_image(70,57,image=photo) if photo else frame.create_text(70,57,text='—',fill=fg,font=('MS Gothic',16))
  caption_id=frame.create_text(70,47 if compact else 112,text=caption,fill='#edf1fa',width=128,font=('MS Gothic',9))
  badge_id=frame.create_text(70,133,text=badge or label,fill=fg,width=128,font=('MS Gothic',8)) if (badge or label) and not compact else None
  def resize(event):
   width=event.width
   frame.coords(border,2,2,width-3,height-3)
   for node,y in [(title_id,14),(image_id,57),(caption_id,47 if compact else 112),(badge_id,133)]:
    if node is not None:frame.coords(node,width/2,y)
   frame.itemconfigure(caption_id,width=max(20,width-12))
   if badge_id is not None:frame.itemconfigure(badge_id,width=max(20,width-12))
  frame.bind('<Configure>',resize)
  frame.bind('<Button-1>',lambda e:self.activate_card(frame,command))
  frame.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-int(e.delta/120),'units'))
  return frame
 def activate_card(self,frame,command):
  previous=getattr(self,'active_card',None)
  if previous is not None and previous.winfo_exists():previous.configure(highlightbackground=previous.normal_border,highlightthickness=1)
  self.active_card=frame;frame.configure(highlightbackground='#fff1bc',highlightthickness=1);command()
 def render_equipment(self,equipset):
  self.heading.configure(text=self.equipset_label(equipset.number))
  refs=self.macro_links.for_set(equipset.number)
  summary=f'マクロ参照: {len(refs)}行' if refs else 'マクロ参照なし'
  self.subtitle.configure(text='空の装備セット' if is_empty(equipset) else summary+' · 参照一覧は右の「マクロと装備セットの参照確認」から')
  slots={s.name:s for s in equipset.slots}
  for i,key in enumerate(GRID):
   s=slots[key];caption=self.item_name(s.item_id) if s.action=='equip' else {'keep':'変更しない','remove':'装備を外す'}.get(s.action,'未知の動作')
   self.card_widgets[key]=self.card(i,SLOTS[key],caption,lambda slot=s:self.inspect_slot(slot),s.item_id if s.action=='equip' else None,present_slot(s,equipset.number,self.fix_plan).status)
  counts=Counter(ACTION_STYLE[present_slot(s,equipset.number,self.fix_plan).status][0] for s in equipset.slots if s.action=='equip')
  body='\n'.join(f'{k}: {v}枠' for k,v in counts.items())
  if not is_empty(equipset):
   body+='\n\n参照元マクロ\n'
   if refs:
    body+='\n\n'.join(f'ブック {r.book:02} / パレット {r.palette:02}\n{r.bank.upper()} {r.key if r.key<10 else 0} · {r.macro_title or "（空欄）"}\n{r.line}行目: /{r.command} {r.number:03}' for r in refs)
   else:body+='マクロ参照なし'
  body+='\n\nFix可能な枠は、上のボタンから変更案を確認できます。'
  self.show_detail('装備セット '+self.equipset_label(equipset.number),body)
 def inspect_slot(self,slot):
  a=slot.item_reference;view=present_slot(slot,self.selected.number,self.fix_plan)
  label=ACTION_STYLE[view.status][0]
  text=f'{label}\n{view.instruction}\n\n'
  if slot.action in ('keep','remove'):text+='動作: '+('変更しない' if slot.action=='keep' else '装備を外す')
  else:
   text+=f'登録アイテム\n{self.item_name(slot.item_id)}\n種類ID: {slot.item_id}\n収納: {BAGS.get(slot.container,slot.container)}\n内部スロット: {slot.index}\n\n持ち物データとの照合結果\n{OBSERVATIONS.get(a.observation,a.observation)}\n'
   for item in a.observed_item_ids:text+=f'指定位置のインベントリ保存情報: {item} {self.item_name(item)}\n'
   text+='\n同じ種類IDの候補\n'+('\n'.join(f'{BAGS.get(b,b)} / 内部スロット {i}' for b,i in a.candidates) or '持ち物データに候補なし')
   text+='\n\n照合対象: ローカルに保存されたインベントリ情報'
  if a.inventory_source:
   source=a.inventory_source;stamp=datetime.fromtimestamp(source['mtime_ns']/1e9).astimezone().isoformat()
   text+=f'\n\nインベントリファイル更新日時\n{stamp}\n\n取得元\n{source["path"]}\n\nSHA-256\n{source["sha256"]}'
  actions=[(f'{BAGS.get(b,b)} / {i} の候補を見る',lambda bag=b,index=i:self.open_inventory(bag,index)) for b,i in a.candidates]
  title=self.equipset_label(self.selected.number)+'\n'+SLOTS.get(slot.name,slot.name)+' / '+self.item_name(slot.item_id)
  primary=f'{label}\n\n{view.instruction}'
  if view.change:
   x=view.change
   primary+=f'\n\n変更前\n{BAGS.get(x.before[0],x.before[0])} / {x.before[1]}\n\n変更案\n{BAGS[x.after[0]]} / {x.after[1]}'
  elif slot.action=='equip':
   primary+=f'\n\n登録先\n{BAGS.get(slot.container,slot.container)} / {slot.index}'
  if view.status in ('multiple','needs_review') and a.candidates:
   primary+='\n\n候補\n'+'\n'.join(f'{BAGS.get(b,b)} / {i}' for b,i in a.candidates)
  text+='\n\n補足\n照合条件: 収納・内部位置・種類ID。候補は読み取れたインベントリから検索します。保存情報の更新タイミングは調査中です。'
  self.show_detail(title,primary,actions[:8] if view.status in ('multiple','needs_review','fixable') else (),evidence=text)
 def render_macros(self,address):
  self.active_macro=None;self.edit_button.configure(state='disabled')
  book,palette=address;self.heading.configure(text=f'ブック {book} / パレット {palette}');self.subtitle.configure(text='マクロをクリックすると全6行を表示します。')
  macros=[m for m in self.character.macros if (m.book,m.palette)==address]
  for row,title in [(0,'Ctrl'),(2,'Alt')]:
   tk.Label(self.cards,text=title,fg='#dce5ff',bg='#080f22',font=('MS Gothic',11,'bold'),anchor='w').grid(row=row,column=0,columnspan=10,sticky='ew',padx=4,pady=(12,2))
  for i,m in enumerate(macros):
   key=f'{m.key if m.key<10 else 0}'
   empty=any(r.target_state=='empty' for r in self.macro_links.for_macro(m))
   self.card(i,key,('⚠ 空セット参照\n' if empty else '')+(m.title.display or '（空欄）'),lambda macro=m:self.inspect_macro(macro),state='missing' if empty else None,badge=f'{sum(bool(l.display) for l in m.lines)} / 6 行',compact=True)
  self.show_detail('マクロパレット',f'ブック {book} / パレット {palette}\n\nマクロをクリックしてタイトルと各行を確認してください。')
 def inspect_macro(self,macro):
  self.active_macro=macro_key(macro);self.edit_button.configure(state='disabled' if self.editor.blocked else 'normal')
  refs=self.macro_links.for_macro(macro)
  warning='\n'.join(f'⚠ {r.line}行目: {self.equipset_label(r.number)} は空です' for r in refs if r.target_state=='empty')
  body='\n\n'.join(f'{i+1}  {line.display or "（空欄）"}' for i,line in enumerate(macro.lines))
  if refs:body+='\n\n参照先\n'+'\n'.join(f'{r.line}行目 → {self.equipset_label(r.number)}'+('（未取得）' if r.target_state=='unavailable' else '') for r in refs)
  inventory=[r for r in self.macro_item_refs if r.address==macro_key(macro)]
  if inventory:body+='\n\nアイテム参照\n'+'\n'.join(f'{r.line}行目: {MACRO_ITEM_LABELS[r.state]}' for r in inventory)
  self.show_detail(macro.title.display or '（空欄マクロ）',(warning+'\n\n' if warning else '')+body)
 def edit_selected_macro(self):
  if not self.active_macro:return
  c=self.character;macro=next(m for m in c.macros if macro_key(m)==self.active_macro)
  window=tk.Toplevel(self.app,background='#080f22');window.title('マクロを編集');window.geometry('800x400')
  ttk.Label(window,text=f'ブック {macro.book:02} / パレット {macro.palette} / {macro.bank.upper()} {macro.key if macro.key<10 else 0}',padding=10).pack(anchor='w')
  entries=[]
  for label,value in [('名前',macro.title.display)]+[(f'{i}行目',line.display) for i,line in enumerate(macro.lines,1)]:
   row=ttk.Frame(window);row.pack(fill='x',padx=12,pady=4)
   ttk.Label(row,text=label,width=8).pack(side='left')
   entry=tk.Entry(row,bg='#101b38',fg='#edf1fa',insertbackground='white');entry.insert(0,value);entry.pack(side='left',fill='x',expand=True);entries.append(entry)
  def preview():
   try:edit=self.editor.prepare_macro_edit(c.folder_id,macro_key(macro),entries[0].get(),[e.get() for e in entries[1:]])
   except ValueError as e:messagebox.showerror('入力内容',str(e),parent=window);return
   self.preview_edit(edit,lambda:self.editor.apply(edit),window)
  ttk.Button(window,text='変更案を確認',command=preview).pack(pady=12)
 def preview_edit(self,edit,apply,parent=None):
  window=tk.Toplevel(self.app,background='#080f22');window.title(edit.label+' / 作業データ');window.geometry('900x600')
  text=tk.Text(window,bg='#101b38',fg='#edf1fa',wrap='word',padx=12,pady=12)
  scrollbar=ttk.Scrollbar(window,command=text.yview);text.configure(yscrollcommand=scrollbar.set)
  scrollbar.pack(side='right',fill='y');text.pack(fill='both',expand=True)
  count=0
  for change in edit.changes:
   if change.before==change.after:continue
   count+=1;b,p,bank,key=change.key
   text.insert('end',f'ブック {b:02} / パレット {p} / {bank.upper()} {key if key<10 else 0}  {change.before.title.display}\n')
   if change.before.title!=change.after.title:text.insert('end',f'名前: {change.before.title.display} → {change.after.title.display}\n')
   for n,(before,after) in enumerate(zip(change.before.lines,change.after.lines),1):
    if before!=after:text.insert('end',f'{n}行目\n  前: {before.display}\n  後: {after.display}\n')
   text.insert('end','\n')
  if not count:text.insert('end','変更対象なし')
  text.configure(state='disabled')
  def commit():
   try:apply()
   except (ValueError,OSError) as e:messagebox.showerror('作業保存',str(e),parent=window);return
   window.destroy()
   if parent and parent.winfo_exists():parent.destroy()
   self.refresh_edits()
  ttk.Button(window,text=f'{count}マクロの変更を作業データに適用',command=commit,state='normal' if count and not self.editor.blocked else 'disabled').pack(pady=12)
 def show_macro_inventory(self):
  c=self.character
  if not c:return
  all_refs=assess_macro_inventory(c,self.snapshot.items)
  refs=[]
  window=tk.Toplevel(self.app,background='#080f22');window.title('マクロの収納番号を確認・補正');window.geometry('1050x700')
  ttk.Label(window,text='選択中のキャラクターの /equip を照合 · Fixは収納番号を追加・変更',padding=10).pack(anchor='w')
  filter_choice=ttk.Combobox(window,state='readonly',values=('Fix可能のみ','すべての参照'),width=24)
  filter_choice.current(0);filter_choice.pack(anchor='w',padx=10,pady=(0,8))
  listing=tk.Listbox(window,bg='#101b38',fg='#edf1fa',selectbackground='#354b7a',height=14,exportselection=False)
  scrollbar=ttk.Scrollbar(window,command=listing.yview);listing.configure(yscrollcommand=scrollbar.set)
  scrollbar.pack(side='right',fill='y');listing.pack(fill='both',expand=True,padx=10)
  detail=tk.Text(window,height=9,bg='#101b38',fg='#edf1fa',wrap='word',padx=10,pady=10);detail.pack(fill='x',padx=10,pady=8)
  def select(event=None):
   if not listing.curselection():return
   r=refs[listing.curselection()[0]]
   selected_fix.configure(state='normal' if any(x.address==r.address and x.replacement is not None for x in all_refs) else 'disabled')
   detail.configure(state='normal');detail.delete('1.0','end')
   detail.insert('end',r.text+'\n'+MACRO_ITEM_LABELS[r.state]+'\n')
   for bag,index,item in r.candidates:detail.insert('end',f'{BAGS[bag]} / 内部位置 {index} / {self.item_name(item)}\n')
   if r.state=='same_storage_multiple':detail.insert('end','使い分けるには収納を分けてください。\n')
   if r.replacement:detail.insert('end','Fix案: '+r.replacement)
   detail.configure(state='disabled')
  listing.bind('<<ListboxSelect>>',select)
  def preview(selected=False):
   address=refs[listing.curselection()[0]].address if selected and listing.curselection() else None
   if selected and address is None:return
   edit=plan_macro_fixes(c,self.snapshot.items,address)
   self.preview_edit(edit,lambda:self.editor.macro_fixes(c.folder_id,edit,address),window)
  buttons=ttk.Frame(window);buttons.pack(fill='x',padx=10,pady=10)
  selected_fix=ttk.Button(buttons,text='選択マクロのFix案',command=lambda:preview(True),state='disabled');selected_fix.pack(side='left')
  ttk.Button(buttons,text='このキャラのFix案をまとめて確認',command=preview,state='normal' if any(r.replacement is not None for r in all_refs) else 'disabled').pack(side='left',padx=10)
  def open_macro():
   if not listing.curselection():return
   address=refs[listing.curselection()[0]].address
   self.mode.set('マクロ');self.change_mode();item=f'palette-{address[0]}-{address[1]}'
   self.macro_tree.selection_set(item);self.macro_tree.see(item);self.select_macro_palette()
   self.inspect_macro(next(m for m in self.character.macros if macro_key(m)==address));window.destroy()
  ttk.Button(buttons,text='マクロを開く',command=open_macro).pack(side='left')
  def populate(event=None):
   nonlocal refs
   refs=[r for r in all_refs if filter_choice.current()==1 or r.replacement is not None]
   listing.delete(0,'end');selected_fix.configure(state='disabled')
   detail.configure(state='normal');detail.delete('1.0','end')
   if not refs:detail.insert('end','Fix可能な参照はありません。' if filter_choice.current()==0 else '参照はありません。')
   detail.configure(state='disabled')
   for r in refs:
    b,p,bank,key=r.address
    listing.insert('end',f'{b:02}-{p:02} {bank.upper()} {key if key<10 else 0} / {r.line}行目  [{MACRO_ITEM_LABELS[r.state]}]  {r.text}')
   if refs:listing.selection_set(0);select()
  filter_choice.bind('<<ComboboxSelected>>',populate)
  populate()
 def macro_reference_label(self,ref):
  return f'{ref.book:02}-{ref.palette:02} {ref.bank.upper()} {ref.key if ref.key<10 else 0} / {ref.macro_title or "（空欄）"} / {ref.line}行目'
 def show_macro_links(self):
  c=self.character
  if not c:return
  report=inspect_macro_set_links(self.snapshot,c)
  window=tk.Toplevel(self.app,background='#080f22');window.title('マクロと装備セットの参照確認');window.geometry('950x620')
  ttk.Label(window,text='読み取ったマクロの /equipset・/lockstyleset を、同じキャラの装備セットと照合します。',padding=10).pack(anchor='w')
  ttk.Label(window,text='一覧で選択して「開く」を押すと、対象へ移動します。',padding=10).pack(anchor='w')
  notebook=ttk.Notebook(window);notebook.pack(fill='both',expand=True,padx=10,pady=10)
  sets={e.number:e for e in c.equipsets}
  entries=[('空セットへの参照',[(self.macro_reference_label(r)+' → '+self.equipset_label(r.number,c),r) for r in report.empty_references]),
           ('マクロ参照なし',[(self.equipset_label(n,c),n) for n in report.unreferenced])]
  for title,rows in entries:
   frame=ttk.Frame(notebook);notebook.add(frame,text=f'{title} ({len(rows)})')
   listing=tk.Listbox(frame,bg='#101b38',fg='#edf1fa',selectbackground='#354b7a',exportselection=False)
   bar=ttk.Scrollbar(frame,command=listing.yview);listing.configure(yscrollcommand=bar.set)
   bar.pack(side='right',fill='y');listing.pack(fill='both',expand=True)
   for label,_ in rows:listing.insert('end',label)
   if not rows:listing.insert('end','該当なし')
   def open_selected(items=rows,box=listing):
    selected=box.curselection()
    if not selected or not items:return
    value=items[selected[0]][1]
    self.character_choice.current(next(i for i,x in enumerate(self.snapshot.characters) if x.folder_id==c.folder_id))
    self.mode.set('装備セット' if isinstance(value,int) else 'マクロ');self.change_mode()
    index=next(i for i,x in enumerate(self.navigation) if (x.number==value if isinstance(value,int) else x==(value.book,value.palette)))
    if isinstance(value,int):
     self.nav.selection_clear(0,'end');self.nav.selection_set(index);self.nav.see(index);self.select_navigation()
    else:
     item=f'palette-{value.book}-{value.palette}'
     self.macro_tree.selection_set(item);self.macro_tree.see(item);self.select_macro_palette()
    if not isinstance(value,int):
     macro=next(m for m in self.character.macros if (m.book,m.palette,m.bank,m.key)==value.address)
     self.inspect_macro(macro)
    window.destroy()
   ttk.Button(frame,text='選択した対象を開く',command=open_selected,state='normal' if rows else 'disabled').pack(pady=8)
   listing.bind('<Double-Button-1>',lambda event,command=open_selected:command())
 def show_unused_wardrobe(self):
  c=self.character
  if not c:return
  report=inspect_wardrobe_usage(self.snapshot,c)
  window=tk.Toplevel(self.app,background='#080f22');window.title('ワードローブの未参照アイテム');window.geometry('1000x680')
  counts=Counter(r.state for r in report)
  ttk.Label(window,text=f'{c.display_name or c.folder_id} · ワードローブ1〜8 · 未参照 {counts["unreferenced"]} / 参照候補あり {counts["possible"]} / 確認保留 {counts["incomplete"]}',padding=10).pack(anchor='w')
  ttk.Label(window,text='編集バッファの /equip と全装備セットを照合',padding=(10,0,10,8)).pack(anchor='w')
  choice=ttk.Combobox(window,state='readonly',values=('未参照','参照候補あり','確認保留'),width=22);choice.current(0);choice.pack(anchor='w',padx=10,pady=(0,8))
  frame=ttk.Frame(window);frame.pack(fill='both',expand=True,padx=10)
  listing=ttk.Treeview(frame,columns=('bag','slot','id','name'),show='headings',selectmode='browse',style='Macro.Treeview')
  for name,label,width in [('bag','収納',155),('slot','内部位置',85),('id','種類ID',85),('name','アイテム名',420)]:
   listing.heading(name,text=label);listing.column(name,width=width,anchor='w')
  bar=ttk.Scrollbar(frame,command=listing.yview);listing.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');listing.pack(fill='both',expand=True)
  detail=tk.Text(window,height=7,bg='#101b38',fg='#edf1fa',wrap='word',padx=12,pady=10);detail.pack(fill='x',padx=10,pady=8)
  visible=[]
  def select(event=None):
   selection=listing.selection()
   if not selection:return
   value=visible[int(selection[0])];row=value.item
   detail.configure(state='normal');detail.delete('1.0','end')
   detail.insert('end',self.item_name(row.item_id)+'\n'+BAGS[row.container]+f' / 内部位置 {row.index} / ID {row.item_id}\n')
   detail.insert('end','\n'.join(value.references) if value.references else '読み取れた /equip と全装備セットに参照がありません。')
   detail.configure(state='disabled')
  listing.bind('<<TreeviewSelect>>',select)
  def open_selected():
   selection=listing.selection()
   if not selection:return
   row=visible[int(selection[0])].item
   self.character_choice.current(next(i for i,x in enumerate(self.snapshot.characters) if x.folder_id==c.folder_id))
   self.open_inventory(row.container,row.index);window.destroy()
  open_button=ttk.Button(window,text='インベントリで開く',command=open_selected);open_button.pack(pady=(0,10))
  listing.bind('<Double-Button-1>',lambda event:open_selected())
  def populate(event=None):
   nonlocal visible
   state=('unreferenced','possible','incomplete')[choice.current()]
   visible=[r for r in report if r.state==state]
   listing.delete(*listing.get_children())
   detail.configure(state='normal');detail.delete('1.0','end');detail.insert('end','該当なし' if not visible else '');detail.configure(state='disabled')
   open_button.configure(state='normal' if visible else 'disabled')
   for i,value in enumerate(visible):
    row=value.item;listing.insert('','end',iid=str(i),values=(BAGS[row.container],row.index,row.item_id,self.item_name(row.item_id)))
   if visible:listing.selection_set('0');select()
  choice.bind('<<ComboboxSelected>>',populate);populate()
 def render_inventory(self,bag):
  rows=[r for r in self.character.inventory if r.container==bag];self.heading.configure(text=BAGS[bag]);self.subtitle.configure(text=f'{len(rows)} アイテム')
  if not rows:ttk.Label(self.cards,text='インベントリ保存情報に表示できるアイテム行がありません。').grid(row=0,column=0,pady=20)
  for i,row in enumerate(rows):self.card_widgets[row.index]=self.card(i,f'スロット {row.index}',self.item_name(row.item_id),lambda r=row:self.inspect_inventory(r),row.item_id,badge=f'ID {row.item_id}')
  self.show_detail(BAGS[bag],f'取得状態: {self.character.inventory_coverage.get(bag,"未取得")}\n\n{len(rows)}行を表示しています。\n内部スロット順で表示しています。\n数量とオーグメントは取得不可。')
 def inspect_inventory(self,row):
  refs=[(e.number,s.name,s.item_reference) for e in self.character.equipsets for s in e.slots if s.action=='equip' and (s.container,s.index)==(row.container,row.index)]
  text=f'種類ID: {row.item_id}\n収納: {BAGS[row.container]}\n内部スロット: {row.index}\n\n数量: 不明\nオーグメント: 取得不可\n\nこの保存位置を指定する装備セット\n'
  text+='\n'.join(f'{self.equipset_label(n)} / {SLOTS[key]}\n  {OBSERVATIONS.get(a.observation,a.observation)}' for n,key,a in refs) or 'なし'
  summary='\n'.join(f'{self.equipset_label(n)} / {SLOTS[key]}' for n,key,a in refs) or 'なし'
  self.show_detail(self.item_name(row.item_id),f'{BAGS[row.container]} / {row.index}\n種類ID: {row.item_id}\n\n参照している装備セット\n{summary}',evidence=text)
 def open_inventory(self,bag,index):
  self.mode.set('インベントリ');self.change_mode();self.nav.selection_clear(0,'end');i=self.navigation.index(bag);self.nav.selection_set(i);self.nav.see(i);self.select_navigation()
  row=next((r for r in self.character.inventory if r.container==bag and r.index==index),None)
  if row:
   self.inspect_inventory(row);self.app.update_idletasks();card=self.card_widgets[index];height=self.cards.winfo_height();self.canvas.yview_moveto(max(0,card.winfo_y()/max(1,height)));card.configure(highlightbackground='#fff1bc',highlightthickness=1)


def show(snapshot):
 app=tk.Tk();app.view=ReaderWindow(app,snapshot);app.mainloop()
