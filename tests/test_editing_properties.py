"""PT-13..18: generated edits against an independent value/history model."""
from copy import deepcopy
from dataclasses import replace
import random
import json
import unittest
from unittest.mock import patch
from ff11reader.domain import Character, Macro, Equipset, Slot, Text, InventoryRow, Snapshot
from ff11reader.edit_application import Editor
from ff11reader.editing import Edit, Change, plan_macro_fixes, plan_equipment_edit
from ff11reader.fixes import plan_fixes
from ff11reader.references import assess_equipment
from tests.property_support import isolated, seeds, check_sequence

PARTS='main sub range ammo head body hands legs feet neck waist ear1 ear2 ring1 ring2 back'.split()


def source(base):
    marker=base/'source.dat';marker.write_bytes(b'synthetic source')
    characters=[]
    for name in ('a','b'):
        macros=[Macro(1,1,'ctrl',key,Text('Base','','test'),tuple(Text(s,'','test') for s in ['/equip body Robe','','','','',''])) for key in (1,2)]
        slots=tuple(Slot(p,'equip',100,8,3,'') if p=='body' else Slot(p,'keep',None,None,None,'') for p in PARTS)
        characters.append(Character(name,macros=macros,equipsets=[Equipset(1,Text('Set','','test'),slots)],
                                    inventory=[InventoryRow(8,5,100)],inventory_coverage={i:'loaded' for i in range(17)}))
    for c in characters:c.equipsets=assess_equipment(c)
    return Snapshot('id','now',characters,{100:{'name':'Robe'}},[{'path':str(marker),'sha256':'synthetic'}],[],'property')


def values(snapshot):
    result={}
    for c in snapshot.characters:
        for m in c.macros:result[c.folder_id,'m',m.key]=(m.title.display,tuple(x.display for x in m.lines))
        for e in c.equipsets:result[c.folder_id,'e',e.number]=(e.title.display,tuple((s.name,s.action,s.item_id,s.container,s.index) for s in e.slots))
    return result


class Model:
    def __init__(self):
        self.value={}
        for char in ('a','b'):
            for key in (1,2):self.value[char,'m',key]=('Base',('/equip body Robe','','','','',''))
            self.value[char,'e',1]=('Set',tuple((p,'equip',100,8,3) if p=='body' else (p,'keep',None,None,None) for p in PARTS))
        self.saved=deepcopy(self.value);self.history=[];self.cursor=0

    def apply(self, changes):
        after={**self.value,**changes}
        if after==self.value:return
        self.history[self.cursor:]=[(deepcopy(self.value),deepcopy(after))]
        self.value=after;self.cursor+=1

    def undo(self):
        if self.cursor:self.cursor-=1;self.value=deepcopy(self.history[self.cursor][0])

    def redo(self):
        if self.cursor<len(self.history):self.value=deepcopy(self.history[self.cursor][1]);self.cursor+=1


def change(editor, key, content):
    char,kind,number=key;c=next(c for c in editor.snapshot().characters if c.folder_id==char)
    if kind=='m':
        old=next(m for m in c.macros if m.key==number)
        new=replace(old,title=Text(content[0],'','draft'),lines=tuple(Text(x,'','draft') for x in content[1]))
        return Change(char,'macros',(1,1,'ctrl',number),old,new)
    old=c.equipsets[0]
    new=replace(old,title=Text(content[0],'','draft'),slots=tuple(replace(s,action=v[1],item_id=v[2],container=v[3],index=v[4]) for s,v in zip(old.slots,content[1])))
    return Change(char,'equipsets',(number,),old,new)


class EditingProperties(unittest.TestCase):
    def replay(self, operations):
        with isolated() as base:
            snapshot=source(base);editor=Editor(snapshot,base/'draft.json');model=Model()
            keys=list(model.value)
            for step,(op,target,number) in enumerate(operations):
                key=keys[target%len(keys)]
                title,contents=model.value[key]
                edited=(f'Name{number}',contents)
                if key[1]=='m':edited=(title,(f'/echo {number}',)+contents[1:])
                else:edited=(title,tuple((p,a,i,b,5 if number%2 else 3) if p=='body' else (p,a,i,b,n) for p,a,i,b,n in contents))
                updates={key:edited}
                if op=='batch':updates[keys[(target+1)%len(keys)]]=(f'Batch{number}',model.value[keys[(target+1)%len(keys)]][1])
                if op in ('edit','batch'):
                    editor.apply(Edit(op,tuple(change(editor,k,v) for k,v in updates.items())));model.apply(updates)
                elif op=='noop':editor.apply(Edit(op,(change(editor,key,model.value[key]),)))
                elif op=='undo':editor.undo();model.undo()
                elif op=='redo':editor.redo();model.redo()
                elif op=='restart':
                    editor=Editor(snapshot,base/'draft.json');self.assertIsNone(editor.blocked)
                elif op=='fail':
                    before=(base/'draft.json').read_bytes() if (base/'draft.json').exists() else None
                    with patch.object(editor.store,'save',side_effect=OSError('synthetic full disk')):
                        with self.assertRaises(OSError):
                            if number%3==0:editor.undo()
                            elif number%3==1:editor.redo()
                            else:editor.apply(Edit('fail',(change(editor,key,edited),)))
                    self.assertEqual(before,(base/'draft.json').read_bytes() if (base/'draft.json').exists() else None)
                elif op=='invalid':
                    # Two distinct targets; do not accidentally test only duplicate rejection.
                    persisted=(base/'draft.json').read_bytes() if (base/'draft.json').exists() else None
                    other=keys[(target+1)%len(keys)]
                    valid=change(editor,key,edited);bad=change(editor,other,(f'Bad{number}',model.value[other][1]))
                    mode=number%4
                    if mode==0:bad=replace(bad,before=replace(bad.before,title=Text('stale','','draft')))
                    elif mode==1:bad=replace(bad,character='absent')
                    elif mode==2:bad=replace(bad,after=replace(bad.after,lines=bad.after.lines[:5]) if bad.kind=='macros' else replace(bad.after,slots=bad.after.slots[:15]))
                    else:bad=valid
                    pair=(valid,bad) if number%2 else (bad,valid)
                    with self.assertRaises(ValueError):editor.apply(Edit('invalid',pair))
                    self.assertEqual(persisted,(base/'draft.json').read_bytes() if (base/'draft.json').exists() else None)
                elif op=='fix':
                    char=key[0];c=next(c for c in editor.snapshot().characters if c.folder_id==char)
                    macro=plan_macro_fixes(c,snapshot.items);equipment=plan_equipment_edit(c,plan_fixes(c))
                    editor.apply(Edit('batch fix',macro.changes+equipment.changes))
                    expected={}
                    for k,(name,data) in model.value.items():
                        if k[0]!=char:continue
                        if k[1]=='m':expected[k]=(name,tuple('/equip body Robe 1' if line=='/equip body Robe' else line for line in data))
                        else:expected[k]=(name,tuple((p,a,i,b,5) if p=='body' else (p,a,i,b,n) for p,a,i,b,n in data))
                    model.apply(expected)
                self.assertEqual(values(editor.snapshot()),model.value,(step,op))
                self.assertEqual(values(editor.session.saved),model.saved)
                self.assertEqual(editor.edit_status(),(model.cursor,len(model.history),model.value!=model.saved))
                # Independent reference predicate for the generated one-item world.
                for c in editor.snapshot().characters:
                    slot=c.equipsets[0].slots[5]
                    self.assertEqual(slot.item_reference.state,'match' if slot.index==5 else 'same_type_elsewhere')
                self.assertEqual((base/'source.dat').read_bytes(),b'synthetic source')
            return deepcopy(model.value)

    def test_generated_operation_sequences(self):
        for seed in seeds():
            rng=random.Random(seed)
            prefix=[('edit',0,1),('edit',3,2),('undo',0,0),('noop',0,0),('redo',0,0),('undo',0,0),('batch',0,4),('fix',0,0),('restart',0,0)]
            ops=prefix+[(rng.choice(['edit','batch','fix','undo','redo','noop','invalid','fail','restart']),rng.randrange(6),rng.randrange(100)) for _ in range(45)]
            with self.subTest(seed=seed):check_sequence('PT-13-17',seed,ops,self.replay)

    def test_generated_full_undo_redo_roundtrip(self):
        for seed in seeds():
            rng=random.Random(seed);ops=[('batch',rng.randrange(6),n+1) for n in range(1+rng.randrange(12))]
            with self.subTest(seed=seed):
                check_sequence('PT-14',seed,ops+[('undo',0,0)]*len(ops)+[('restart',0,0)]+[('redo',0,0)]*len(ops),self.replay)

    def test_external_update_restart_archives_previous_work(self):
        for seed in seeds():
            with self.subTest(seed=seed),isolated() as base:
                snap=source(base);editor=Editor(snap,base/'draft.json')
                model=Model();key=('a','m',1)
                editor.apply(Edit('edit',(change(editor,key,('Edited',model.value[key][1])),)))
                old=(base/'draft.json').read_bytes()
                fresh=deepcopy(snap);fresh.sources[0]['sha256']=str(seed)
                fresh.characters[0].macros[0]=replace(fresh.characters[0].macros[0],title=Text('External','','test'))
                reopened=Editor(fresh,base/'draft.json');self.assertIsNotNone(reopened.blocked)
                reopened.start_fresh()
                self.assertEqual(values(reopened.snapshot()),values(fresh))
                self.assertEqual(next(base.glob('draft.archived-*.json')).read_bytes(),old)
                self.assertEqual((base/'source.dat').read_bytes(),b'synthetic source')

    def test_legacy_work_versions_and_invalid_baseline(self):
        for version in (1,2,3):
            with self.subTest(version=version),isolated() as base:
                snap=source(base);editor=Editor(snap,base/'draft.json');model=Model();key=('a','m',1)
                edited=('Changed',model.value[key][1])
                editor.apply(Edit('edit',(change(editor,key,edited),)));editor.undo()
                data=json.loads((base/'draft.json').read_text(encoding='utf-8'))
                data['version']=version
                if version<3:data.pop('baseline')
                (base/'draft.json').write_text(json.dumps(data),encoding='utf-8')
                reopened=Editor(snap,base/'draft.json');self.assertIsNone(reopened.blocked)
                self.assertEqual(values(reopened.snapshot()),model.value)
                reopened.redo();model.apply({key:edited});self.assertEqual(values(reopened.snapshot()),model.value)
                self.assertEqual(json.loads((base/'draft.json').read_text())['version'],3)
        with isolated() as base:
            snap=source(base);editor=Editor(snap,base/'draft.json');editor.undo()
            data=json.loads((base/'draft.json').read_text());data['baseline'].pop('a')
            (base/'draft.json').write_text(json.dumps(data));before=(base/'draft.json').read_bytes()
            reopened=Editor(snap,base/'draft.json');self.assertIsNotNone(reopened.blocked)
            with self.assertRaises(ValueError):reopened.redo()
            self.assertEqual((base/'draft.json').read_bytes(),before)
