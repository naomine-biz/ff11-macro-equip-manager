"""Isolated synthetic evaluation; never imported by the application.
Run: python -B experiments/persistent_edit_store.py
Dependencies: work/undo-prototype/deps (see requirements-undo.txt).
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'work/undo-prototype/deps'), str(ROOT)]
from copy import deepcopy
from dataclasses import replace
from statistics import median
from time import perf_counter_ns
import gc
import json
import random
import tracemalloc
from importlib.metadata import version
from immutables import Map
from pyrsistent import pmap
from ff11reader.domain import Macro, Text, Equipset, Slot, ItemReference


class Store:
    """Own private values. Only copied values cross the boundary.

    The stored domain objects are unchanged, and may contain mutable fields.
    Internal code must NEVER mutate stored values; all writes replace entries.
    Persist receives detached values and must succeed before state publication.
    This is a prototype, not a replacement for EditSession validation/recovery.
    """
    def __init__(self, values, backend):
        self.backend = backend
        owned = deepcopy(values)
        self._root = owned if backend == 'deepcopy' else (Map(owned) if backend == 'immutables' else pmap(owned))
        self._baseline = self._root
        self._saved = self._root
        self._history = []
        self.cursor = 0

    def _updated(self, root, replacements):
        if self.backend == 'deepcopy':
            result = deepcopy(root)
            result.update(deepcopy(replacements))
            return result
        builder = root.mutate() if self.backend == 'immutables' else root.evolver()
        for key, value in replacements.items(): builder[key] = deepcopy(value)
        return builder.finish() if self.backend == 'immutables' else builder.persistent()

    def read(self, key): return deepcopy(self._root[key])
    def export(self): return deepcopy(dict(self._root))
    def saved(self): return deepcopy(dict(self._saved))
    def baseline(self): return deepcopy(dict(self._baseline))

    def edit(self, replacements, persist=lambda values: None):
        for key in replacements:
            if key not in self._root: raise KeyError(key)
        replacements = {key: value for key, value in replacements.items() if value != self._root[key]}
        if not replacements: return
        candidate = self._updated(self._root, replacements)
        history = self._history[:self.cursor] + [(self._root, candidate, tuple(replacements))]
        persist(deepcopy(replacements))
        self._root, self._history, self.cursor = candidate, history, self.cursor + 1

    def undo(self, persist=lambda values: None):
        if not self.cursor: return
        before, after, keys = self._history[self.cursor-1]
        persist(deepcopy({key: before[key] for key in keys}))
        self._root, self.cursor = before, self.cursor-1

    def redo(self, persist=lambda values: None):
        if self.cursor == len(self._history): return
        before, after, keys = self._history[self.cursor]
        persist(deepcopy({key: after[key] for key in keys}))
        self._root, self.cursor = after, self.cursor+1

    def mark_saved(self, keys, persist=lambda values: None):
        changes = {key:self._root[key] for key in keys}
        candidate = self._updated(self._saved, changes)
        persist(deepcopy(changes))
        self._saved = candidate


def fixtures(count):
    values={}
    for i in range(count):
        c, local = divmod(i,4000)
        book, local = divmod(local,200)
        palette, local = divmod(local,20)
        bank, key = divmod(local,10)
        values[c,'macro',i] = Macro(book+1,palette+1,('ctrl','alt')[bank],key+1,
            Text(f'Macro {i}',f'{i:08x}','synthetic'),
            tuple(Text(f'/echo {i} line {line}',f'{i:08x}{line:02x}','synthetic') for line in range(6)))
    for c in range(max(1,(count+3999)//4000)):
        for number in range(1,11):
            reference=ItemReference(inventory_source={'metadata':{'values':[1,2,3]}})
            slots=tuple(Slot(str(i),'equip',100+i,8,i,'00',reference) for i in range(16))
            values[c,'equip',number]=Equipset(number,Text('Set','','synthetic'),slots)
    return values


def fail(_): raise OSError('synthetic persistence failure')


def validate():
    checks=0
    for backend in ('immutables','pyrsistent'):
        # Negative control: a persistent container does NOT freeze its leaves.
        value=fixtures(1)[0,'equip',1]
        root=Map({'x':value}) if backend=='immutables' else pmap({'x':value})
        other=root.set('y',0)
        value.slots[0].item_reference.inventory_source['metadata']['values'].append(99)
        assert root['x'].slots[0].item_reference.inventory_source['metadata']['values'][-1]==99
        assert other['x'].slots[0].item_reference.inventory_source['metadata']['values'][-1]==99
        for seed in (0,1,7,19,42,127):
            rng=random.Random(seed)
            original=fixtures(30)
            store=Store(original,backend)
            expected=deepcopy(original); saved=deepcopy(original); history=[]; cursor=0
            keys=list(original)
            # Mutating the input and returned domain values cannot affect state.
            original[0,'equip',1].slots[0].item_reference.inventory_source['metadata']['values'].append(100)
            detached=store.read((0,'equip',1))
            detached.slots[0].item_reference.inventory_source['metadata']['values'].clear()
            assert store.export()==expected
            for step in range(200):
                action=rng.choice(('edit','edit','batch','undo','redo','saved','fail','invalid'))
                if action in ('edit','batch','fail'):
                    selected=rng.sample(keys,1 if action!='batch' else 4)
                    replacements={key:replace(store.read(key),title=Text(f'{seed}:{step}','','synthetic')) for key in selected}
                    if action=='fail':
                        try:store.edit(replacements,fail)
                        except OSError:pass
                        else:raise AssertionError('failure not propagated')
                    else:
                        before=deepcopy(expected); expected.update(deepcopy(replacements))
                        history[cursor:]=[(before,deepcopy(expected))];cursor+=1
                        store.edit(replacements)
                elif action=='undo':
                    store.undo()
                    if cursor: cursor-=1; expected=deepcopy(history[cursor][0])
                elif action=='redo':
                    store.redo()
                    if cursor<len(history):expected=deepcopy(history[cursor][1]);cursor+=1
                elif action=='saved':
                    selected=rng.sample(keys,2);store.mark_saved(selected)
                    saved.update({key:deepcopy(expected[key]) for key in selected})
                else:
                    try:store.edit({keys[0]:store.read(keys[0]),'missing':0})
                    except KeyError:pass
                    else:raise AssertionError('missing key accepted')
                assert store.export()==expected,(backend,seed,step,action)
                assert store.saved()==saved
                assert store.baseline()==fixtures(30)
                assert store.cursor==cursor and len(store._history)==len(history)
                checks+=1
            for method in (store.undo,store.redo,lambda callback:store.mark_saved(keys[:1],callback)):
                before=(store.export(),store.saved(),store.cursor,len(store._history))
                try:method(fail)
                except OSError:pass
                assert before==(store.export(),store.saved(),store.cursor,len(store._history))
            before=len(store._history);store.edit({keys[0]:store.read(keys[0])});assert len(store._history)==before
            # Exercise both failure boundaries with a guaranteed available operation.
            key=keys[0]
            store.edit({key:replace(store.read(key),title=Text('failure boundary','','synthetic'))})
            for operation in (store.undo,):
                before=(store.export(),store.saved(),store.cursor,len(store._history))
                try:operation(fail)
                except OSError:pass
                else:raise AssertionError('undo persistence must fail')
                assert before==(store.export(),store.saved(),store.cursor,len(store._history))
            store.undo()
            before=(store.export(),store.saved(),store.cursor,len(store._history))
            try:store.redo(fail)
            except OSError:pass
            else:raise AssertionError('redo persistence must fail')
            assert before==(store.export(),store.saved(),store.cursor,len(store._history))
            # A callback receiving copies cannot corrupt stored state/history.
            key=(0,'equip',1)
            replacement=replace(store.read(key),title=Text('callback','','synthetic'))
            def mutate(payload):payload[key].slots[0].item_reference.inventory_source['metadata']['values'].clear()
            store.edit({key:replacement},mutate)
            replacement.slots[0].item_reference.inventory_source['metadata']['values'].clear()
            assert store.read(key).slots[0].item_reference.inventory_source['metadata']['values']==[1,2,3]
    return checks


def measure(action, repeat=5):
    times=[]
    for _ in range(repeat):
        start=perf_counter_ns();action();times.append((perf_counter_ns()-start)/1e6)
    return round(median(times),3)


def benchmark():
    results=[]
    for count in (400,8000):
        values=fixtures(count)
        for backend in ('deepcopy','immutables','pyrsistent'):
            gc.collect();store=Store(values,backend);key=(0,'macro',0);counter=0
            def edit():
                nonlocal counter
                counter+=1
                value=replace(store.read(key),title=Text(str(counter),'','synthetic'))
                store.edit({key:value})
            edit() # warm-up
            row={'macros':count,'backend':backend,'edit_ms':measure(edit),
                 'undo_redo_ms':measure(lambda:(store.undo(),store.redo())),
                 'read_one_ms':measure(lambda:store.read(key)),
                 'export_all_ms':measure(store.export,3)}
            # Allocation experiment separately, so tracing does not bias timings.
            store=Store(values,backend);gc.collect();tracemalloc.start()
            for _ in range(10):edit()
            current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            row.update(retained_10_edits_mib=round(current/1048576,3),peak_10_edits_mib=round(peak/1048576,3))
            results.append(row)
    return results


if __name__=='__main__':
    result={'versions':{name:version(name) for name in ('pyrsistent','immutables')},
        'generated_steps':validate(),'results':benchmark(),
        'scope':'Synthetic private store only. Excludes domain validation/reassessment, disk persistence, restart recovery and GUI. Deepcopy is a comparison store, not the production Editor.'}
    output=ROOT/'work/undo-prototype/results.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
