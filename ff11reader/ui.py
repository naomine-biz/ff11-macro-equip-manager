"""Graphical workspace with explicit, guarded equipment reference saving."""
from collections import Counter
from datetime import datetime
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from .application import set_character_label, preview_reference_fixes, apply_reference_fixes
from .presentation import present_slot
from pathlib import Path
from .application import load_snapshot, prepare_game_save, save_game_plan, restore_game_backup

ACTION_STYLE = {
 'match': ('一致', '#101e36', '#89dda3'),
 'fixable': ('Fix可能', '#101e36', '#87bfff'),
 'multiple': ('候補が複数', '#101e36', '#f3ce77'),
 'missing': ('候補なし', '#101e36', '#ef9994'),
 'needs_review': ('要確認', '#101e36', '#c6a5ee'),
 'not_applicable': ('', '#0d172c', '#7e8ca9'),
}
OBSERVATIONS = {'cache_match':'保存位置と種類IDがインベントリ保存情報上で一致',
 'cache_item_mismatch':'保存位置の種類IDとインベントリ保存情報が異なる',
 'cache_position_empty':'保存位置にインベントリ保存情報行がない',
 'cache_unavailable':'対象収納のインベントリ保存情報を取得できていない',
 'invalid_reference':'保存された参照値が想定範囲外',
 'unknown_action':'装備動作の意味が未確認',
 'ambiguous_position':'同一位置の観測が重複', 'unassessed':'未評価', 'not_applicable':'対象外'}
BAGS={0:'マイバッグ',1:'モグ金庫',2:'収納家具',3:'一時アイテム',4:'ロッカー',5:'サッチェル',6:'サック',7:'ケース',8:'ワードローブ1',9:'モグ金庫2',**{i+8:f'ワードローブ{i}' for i in range(2,9)}}
SLOTS={'main':'メイン','sub':'サブ','range':'遠隔','ammo':'矢弾','head':'頭','neck':'首','ear1':'左耳','ear2':'右耳','body':'胴','hands':'両手','ring1':'左指','ring2':'右指','back':'背','waist':'腰','legs':'両脚','feet':'両足'}
GRID='main sub range ammo head neck ear1 ear2 body hands ring1 ring2 back waist legs feet'.split()


class ReaderWindow:
 def __init__(self, app, snapshot):
  self.app=app;self.snapshot=snapshot;self.fix_undo={};self.photos={};self.card_widgets={};self.navigation=[];self.selected=None
  self.last_backup=None
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
  header=ttk.Frame(app,padding=(18,14));header.pack(fill='x')
  ttk.Label(header,text='FINAL FANTASY XI   /   マクロ・装備',font=('MS Gothic',17,'bold')).pack(side='left')
  ttk.Label(header,text='ゲームへの保存は専用プレビューから / FF11・POL終了時のみ').pack(side='right')
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
  self.heading=ttk.Label(center,text='',font=('MS Gothic',16,'bold'));self.heading.pack(anchor='w')
  self.subtitle=ttk.Label(center,text='');self.subtitle.pack(anchor='w',pady=(4,10))
  self.canvas=tk.Canvas(center,bg='#080f22',highlightthickness=0,width=650)
  scroll=ttk.Scrollbar(center,command=self.canvas.yview);self.canvas.configure(yscrollcommand=scroll.set)
  scroll.pack(side='right',fill='y');self.canvas.pack(fill='both',expand=True)
  self.cards=tk.Frame(self.canvas,bg='#080f22');self.canvas_window=self.canvas.create_window(0,0,window=self.cards,anchor='nw')
  self.cards.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
  self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.canvas_window,width=e.width))
  self.canvas.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-int(e.delta/120),'units'))
  ttk.Button(right,text='Fix可能な参照をまとめて確認',command=self.preview_fixes).pack(fill='x',pady=(0,6))
  ttk.Button(right,text='直前のFixを戻す',command=self.undo_fix).pack(fill='x',pady=(0,10))
  ttk.Button(right,text='選択セットの自動補正をゲームに保存…',command=self.preview_game_save).pack(fill='x',pady=(0,6))
  ttk.Button(right,text='直前のゲーム保存を復元…',command=self.restore_game_save).pack(fill='x',pady=(0,6))
  ttk.Label(right,text='Item / Help',font=('MS Gothic',14,'bold')).pack(anchor='w',pady=(0,12))
  self.detail=tk.Text(right,width=38,wrap='word',font=('MS Gothic',10),bg='#101b38',fg='#edf1fa',insertbackground='white',selectbackground='#354b7a',relief='sunken',borderwidth=1,padx=12,pady=12,state='disabled')
  self.detail.pack(fill='both',expand=True)
  self.detail.tag_configure('title',font=('MS Gothic',13,'bold'),foreground='#fff1c0')
  self.evidence=None
  self.details_button=ttk.Button(right,text='注意・根拠などの詳細',command=self.show_evidence,state='disabled');self.details_button.pack(fill='x',pady=(8,0))
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
  window=tk.Toplevel(self.app);window.title('参照Fixのプレビュー / ゲームファイル変更なし');window.geometry('950x650')
  ttk.Label(window,text=f'{c.folder_id}  ·  更新案 {len(plan.changes)}枠  ·  保留 {len(plan.issues)}枠',padding=12).pack(anchor='w')
  ttk.Label(window,text='変更前と変更後を確認してください。適用先はアプリ内だけで、ゲームファイルには保存しません。',padding=8).pack(anchor='w')
  text=tk.Text(window,wrap='word',bg='#101b38',fg='#edf1fa',font=('MS Gothic',11),padx=12,pady=12)
  text.pack(fill='both',expand=True,padx=12)
  for x in plan.changes:
   text.insert('end',f'{self.equipset_label(x.equipset,c)} / {SLOTS[x.slot]}  {self.item_name(x.item_id)} (ID {x.item_id})\n  {BAGS.get(x.before[0],x.before[0])} / {x.before[1]} → {BAGS[x.after[0]]} / {x.after[1]}\n\n')
  reasons={'invalid_reference':'参照値不正','incomplete_inventory':'取得不足','not_observed':'候補なし','multiple_candidates':'同IDが複数','ambiguous_target':'候補位置が不正・重複','quantity_not_one':'数量が1ではない'}
  if plan.issues:
   text.insert('end','保留（変更しません）\n')
   for x in plan.issues:text.insert('end',f'{self.equipset_label(x.equipset,c)} / {SLOTS[x.slot]}: {reasons[x.reason]}\n')
  if not plan.changes:text.insert('end','適用できるFix案はありません。')
  text.configure(state='disabled')
  def apply():
   try:apply_reference_fixes(self.snapshot,c,plan)
   except ValueError as e:messagebox.showerror('適用できません',str(e),parent=window);return
   self.fix_undo.setdefault(c.folder_id,[]).append(c)
   window.destroy();self.change_mode()
   self.footer.configure(text=f'アプリ内の作業データだけに {len(plan.changes)}枠のFixを適用しました。ゲームファイルは変更していません。')
  ttk.Button(window,text='この案をアプリ内に適用（ゲームへの保存なし）',command=apply,state='normal' if plan.changes else 'disabled').pack(side='right',padx=12,pady=12)
  ttk.Button(window,text='閉じる',command=window.destroy).pack(side='right',pady=12)
 def undo_fix(self):
  c=self.character
  if not c or not self.fix_undo.get(c.folder_id):return
  i=self.character_choice.current();self.snapshot.characters[i]=self.fix_undo[c.folder_id].pop();self.change_mode()
  self.footer.configure(text='アプリ内Fixを戻しました。ゲームファイルは変更していません。')
 def reload_game(self,root):
  folder=self.character.folder_id
  self.snapshot=load_snapshot(root);self.fix_undo.clear();self.photos.clear()
  self.character_choice.configure(values=self.character_labels())
  self.character_choice.current(next(i for i,c in enumerate(self.snapshot.characters) if c.folder_id==folder))
  self.change_mode()
 def preview_game_save(self):
  if self.mode.get()!='装備セット' or not self.selected:return
  if any(self.fix_undo.values()):
   messagebox.showerror('保存できません','アプリ内だけのFixを取り消してから、ゲーム保存の案を確認してください。');return
  c=self.character
  try:plan=prepare_game_save(self.snapshot,c,self.selected.number)
  except (OSError,ValueError) as e:messagebox.showerror('保存できません',str(e));return
  window=tk.Toplevel(self.app);window.title('ゲームデータへの保存プレビュー');window.geometry('850x520')
  text=tk.Text(window,wrap='word',bg='#101b38',fg='#edf1fa',padx=12,pady=12);text.pack(fill='both',expand=True)
  text.insert('end',f'{c.display_name or c.folder_id} / {self.equipset_label(self.selected.number)}\n保存先: {plan.target}\n\nFF11・PlayOnlineを終了してください。保存中も起動しないでください。\n元ファイルをアプリのbackupsに保存し、このセットの位置情報だけを補正します。\n\n')
  for x in plan.changes:
   text.insert('end',f'{SLOTS[x.slot]}: {self.item_name(x.item_id)} (ID {x.item_id})\n{BAGS[x.before[0]]} / {x.before[1]} → {BAGS[x.after[0]]} / {x.after[1]}\n\n')
  text.configure(state='disabled')
  def save():
   try:self.last_backup=save_game_plan(plan)
   except (OSError,ValueError,RuntimeError) as e:messagebox.showerror('保存できません',str(e),parent=window);return
   window.destroy()
   try:self.reload_game(Path(plan.target).parent.parent.parent)
   except Exception as e:messagebox.showerror('保存済み・再表示に失敗',f'保存は完了しました。再起動してください。\n{e}');return
   self.footer.configure(text=f'{len(plan.changes)}枠をゲームファイルに保存・再読取検証済み。バックアップ: {self.last_backup}')
  ttk.Button(window,text='バックアップしてゲームファイルに保存',command=save).pack(side='right',padx=12,pady=12)
  ttk.Button(window,text='キャンセル',command=window.destroy).pack(side='right')
 def restore_game_save(self):
  if not self.last_backup:
   messagebox.showinfo('復元','この起動中のゲーム保存はありません。以前の保存はbackupsのreceipt.jsonから復元ツールで指定できます。');return
  if not messagebox.askyesno('元に戻す',f'直前の保存ファイル全体をバックアップへ戻します。\n{self.last_backup}\nFF11・POLを終了していますか？'):return
  try:
   target=restore_game_backup(self.last_backup);self.last_backup=None
   self.reload_game(target.parent.parent.parent)
  except (OSError,ValueError,RuntimeError) as e:messagebox.showerror('復元できません',str(e));return
  self.footer.configure(text='ゲームファイルをバックアップへ復元し、再読み込みしました。')
 def change_character(self,event=None):self.change_mode()
 def change_mode(self):
  if not self.character:return
  self.nav.delete(0,'end');c=self.character;mode=self.mode.get();self.navigation=[]
  self.fix_plan=preview_reference_fixes(self.snapshot,c)
  if mode=='装備セット':
   self.nav_title.configure(text='装備セット')
   self.navigation=c.equipsets
   for e in self.navigation:self.nav.insert('end',self.equipset_label(e.number))
  elif mode=='マクロ':
   self.nav_title.configure(text='ブック / パレット')
   self.navigation=sorted({(m.book,m.palette) for m in c.macros})
   for book,palette in self.navigation:
    title=c.books.get(book);self.nav.insert('end',f'{book:02}-{palette:02}  {title.display if title else ""}')
  else:
   self.nav_title.configure(text='収納')
   self.navigation=list(BAGS)
   counts=Counter(r.container for r in c.inventory)
   for bag in self.navigation:self.nav.insert('end',f'{BAGS[bag]}  ·  {counts[bag]}')
  if self.navigation:self.nav.selection_set(0);self.select_navigation()
  else:
   self.clear_cards();self.heading.configure(text=mode);self.subtitle.configure(text='読み取れたデータがありません。');self.show_detail('データなし','インベントリ保存情報や設定ファイルが未取得の場合もあります。')
 def clear_cards(self):
  for w in self.cards.winfo_children():w.destroy()
  self.card_widgets={};self.active_card=None
  for column in range(10):self.cards.columnconfigure(column,weight=0,minsize=0)
  self.canvas.yview_moveto(0)
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
  window=tk.Toplevel(self.app);window.title('詳細 / '+title);window.geometry('780x650')
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
  self.subtitle.configure(text='直したい枠をクリックしてください。')
  slots={s.name:s for s in equipset.slots}
  for i,key in enumerate(GRID):
   s=slots[key];caption=self.item_name(s.item_id) if s.action=='equip' else {'keep':'変更しない','remove':'装備を外す'}.get(s.action,'未知の動作')
   self.card_widgets[key]=self.card(i,SLOTS[key],caption,lambda slot=s:self.inspect_slot(slot),s.item_id if s.action=='equip' else None,present_slot(s,equipset.number,self.fix_plan).status)
  counts=Counter(ACTION_STYLE[present_slot(s,equipset.number,self.fix_plan).status][0] for s in equipset.slots if s.action=='equip')
  self.show_detail('装備セット '+self.equipset_label(equipset.number),'\n'.join(f'{k}: {v}枠' for k,v in counts.items())+'\n\nFix可能な枠は、上のボタンから変更案を確認できます。')
 def inspect_slot(self,slot):
  a=slot.item_reference;view=present_slot(slot,self.selected.number,self.fix_plan)
  label=ACTION_STYLE[view.status][0]
  text=f'{label}\n{view.instruction}\n\n'
  if slot.action in ('keep','remove'):text+='動作: '+('変更しない' if slot.action=='keep' else '装備を外す')
  else:
   text+=f'登録アイテム\n{self.item_name(slot.item_id)}\n種類ID: {slot.item_id}\n収納: {BAGS.get(slot.container,slot.container)}\n内部スロット: {slot.index}\n\n保存値の観測\n{OBSERVATIONS.get(a.observation,a.observation)}\n'
   for item in a.observed_item_ids:text+=f'指定位置のインベントリ保存情報: {item} {self.item_name(item)}\n'
   text+='\n同じ種類IDの候補\n'+('\n'.join(f'{BAGS.get(b,b)} / 内部スロット {i}' for b,i in a.candidates) or 'インベントリ保存情報内に候補なし')
   text+='\n\nゲーム実行時の装備可否は、このインベントリ保存情報照合では判定しません。'
  if a.inventory_source:
   source=a.inventory_source;stamp=datetime.fromtimestamp(source['mtime_ns']/1e9).astimezone().isoformat()
   text+=f'\n\nインベントリ保存情報更新日時\n{stamp}\n（サーバー観測日時ではありません）\n\n取得元\n{source["path"]}\n\nSHA-256\n{source["sha256"]}'
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
  text+='\n\n補足\nインベントリの保存情報の更新タイミングは未検証です。候補なしはロストを意味しません。オーグメントは未取得ですが、参照状態の判定条件には含めません。'
  self.show_detail(title,primary,actions[:8] if view.status in ('multiple','needs_review','fixable') else (),evidence=text)
 def render_macros(self,address):
  book,palette=address;self.heading.configure(text=f'ブック {book} / パレット {palette}');self.subtitle.configure(text='マクロをクリックすると全6行を表示します。')
  macros=[m for m in self.character.macros if (m.book,m.palette)==address]
  for row,title in [(0,'Ctrl'),(2,'Alt')]:
   tk.Label(self.cards,text=title,fg='#dce5ff',bg='#080f22',font=('MS Gothic',11,'bold'),anchor='w').grid(row=row,column=0,columnspan=10,sticky='ew',padx=4,pady=(12,2))
  for i,m in enumerate(macros):
   key=f'{m.key if m.key<10 else 0}'
   self.card(i,key,m.title.display or '（空欄）',lambda macro=m:self.inspect_macro(macro),badge=f'{sum(bool(l.display) for l in m.lines)} / 6 行',compact=True)
  self.show_detail('マクロパレット',f'ブック {book} / パレット {palette}\n\nマクロをクリックしてタイトルと各行を確認してください。')
 def inspect_macro(self,macro):
  self.show_detail(macro.title.display or '（空欄マクロ）','\n\n'.join(f'{i+1}  {line.display or "（空欄）"}' for i,line in enumerate(macro.lines)))
 def render_inventory(self,bag):
  rows=[r for r in self.character.inventory if r.container==bag];self.heading.configure(text=BAGS[bag]);self.subtitle.configure(text=f'{len(rows)} アイテム')
  if not rows:ttk.Label(self.cards,text='インベントリ保存情報に表示できるアイテム行がありません。').grid(row=0,column=0,pady=20)
  for i,row in enumerate(rows):self.card_widgets[row.index]=self.card(i,f'スロット {row.index}',self.item_name(row.item_id),lambda r=row:self.inspect_inventory(r),row.item_id,badge=f'ID {row.item_id}')
  self.show_detail(BAGS[bag],f'取得状態: {self.character.inventory_coverage.get(bag,"未取得")}\n\n{len(rows)}行を表示しています。\n内部スロット順です。ゲーム画面の並び順ではありません。\n数量とオーグメントは取得不可。')
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
