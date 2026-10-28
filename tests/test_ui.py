"""Real Tk interactions for the unified graphical workspace."""
from unittest.mock import patch
import tkinter as tk
from tkinter import ttk
import unittest
import os
import tempfile
import hashlib
from pathlib import Path
from ff11reader.edit_application import Editor
from ff11reader.application import load_snapshot, installations
from ff11reader.ui import show, ACTION_STYLE
from ff11reader.presentation import present_slot
from ff11reader.domain import ItemReferenceState


@unittest.skipUnless(os.environ.get("FF11_RUN_GAME_INTEGRATION") == "1", "Set FF11_RUN_GAME_INTEGRATION=1 for installed-game UI checks")
class GraphicalWorkspaceTests(unittest.TestCase):
 def test_character_modes_slot_details_and_candidate_navigation(self):
  snapshot=load_snapshot(installations()[0]);errors=[]
  def run(app):
   app.withdraw();app.report_callback_exception=lambda *args:errors.append(args)
   try:
    view=app.view;app.update_idletasks()
    self.assertEqual(view.mode.get(),'装備セット')
    selected_slot=view.selected.slots[4]
    view.inspect_slot(selected_slot)
    self.assertIsNotNone(view.evidence)
    self.assertNotIn('SHA-256',view.detail.get('1.0','end'))
    view.show_evidence();app.update()
    evidence_window=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
    evidence_text=next(w for w in evidence_window.winfo_children() if isinstance(w,tk.Text)).get('1.0','end')
    self.assertIn('SHA-256',evidence_text)
    evidence_window.destroy()

    original=view.character
    view.preview_fixes();app.update()
    dialog=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
    buttons=[w for w in dialog.winfo_children() if isinstance(w,ttk.Button)]
    apply=next(w for w in buttons if 'この案を' in w.cget('text'))
    self.assertNotIn('disabled',apply.state())
    apply.invoke();app.update()
    self.assertIsNot(view.character,original)
    self.assertEqual(view.editor.session.cursor,1)
    view.undo_fix();app.update();self.assertEqual(view.character,original)

    app.update()
    cards=list(view.card_widgets.values());geometry=[(w.winfo_x(),w.winfo_y(),w.winfo_width(),w.winfo_height()) for w in cards]
    children=tuple(str(w) for w in view.actions.winfo_children())
    for slot in view.selected.slots:
     view.activate_card(view.card_widgets[slot.name],lambda value=slot:view.inspect_slot(value));app.update()
     self.assertEqual(geometry,[(w.winfo_x(),w.winfo_y(),w.winfo_width(),w.winfo_height()) for w in cards])
     self.assertEqual(children,tuple(str(w) for w in view.actions.winfo_children()))
     self.assertTrue(all(not w.winfo_children() for w in cards))

    for index,c in enumerate(snapshot.characters):
     view.mode.set('装備セット')
     view.character_choice.current(index);view.character_choice.event_generate('<<ComboboxSelected>>');app.update()
     if c.equipsets:
      self.assertEqual(len(view.card_widgets),16)
      for slot in c.equipsets[0].slots:
       view.inspect_slot(slot)
       self.assertIn(ACTION_STYLE[present_slot(slot,c.equipsets[0].number,view.fix_plan).status][0],view.detail.get('1.0','end'))
       self.assertNotIn('SHA-256',view.detail.get('1.0','end'))
       self.assertNotIn('鮮度',view.detail.get('1.0','end'))
     view.mode.set('マクロ');view.change_mode();app.update()
     if c.macros:
      macro=c.macros[0];view.inspect_macro(macro)
      text=view.detail.get('1.0','end');self.assertIn('6  ',text)
     view.mode.set('インベントリ');view.change_mode();app.update()
     self.assertEqual(len(view.card_widgets),sum(r.container==0 for r in c.inventory))
     if c.inventory:
      row=c.inventory[-1];view.open_inventory(row.container,row.index);app.update()
      self.assertEqual(view.selected,row.container)
      self.assertIn(f'種類ID: {row.item_id}',view.detail.get('1.0','end'))
    self.assertGreater(len([p for p in view.photos.values() if p is not None]),0)
    self.assertEqual(errors,[])
    for source in snapshot.sources:
     self.assertEqual(hashlib.sha256(Path(source['path']).read_bytes()).hexdigest(),source['sha256'])
   finally:app.destroy()
  root=Path(__file__).resolve().parents[1]/'work'/'ui-tests';root.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(dir=root) as tmp, patch('ff11reader.ui.Editor',side_effect=lambda snap:Editor(snap,Path(tmp)/'draft.json')), patch.object(tk.Tk,'mainloop',run):show(snapshot)


if __name__=='__main__':unittest.main()
