"""Benchmark the actual Editor with synthetic files; no game installation access.
Run with .venv/Scripts/python -B experiments/benchmark_editor.py
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dataclasses import replace
from time import perf_counter_ns
from statistics import median
import json
from tests.test_editing_properties import source
from tests.property_support import isolated
from ff11reader.edit_application import Editor


def benchmark():
    rows=[];initialization=[]
    for count in (400,8000):
        with isolated() as base:
            snapshot=source(base)
            for c in snapshot.characters:
                template=c.macros[0]
                c.macros=[replace(template,book=i//200+1,palette=i//20%10+1,
                    bank=('ctrl','alt')[i//10%2],key=i%10+1) for i in range(count//2)]
            start=perf_counter_ns()
            editor=Editor(snapshot,base/'draft.json');view=editor.snapshot()
            initialization.append(dict(macros=count,elapsed_ms=round((perf_counter_ns()-start)/1e6,3)))
            for i in range(6):
                plan=editor.prepare_macro_edit('a',(1,1,'ctrl',1),f'Edit{i}',['/equip body Robe','','','','',''])
                for name,operation in [('edit',lambda:editor.apply(plan)),('undo',editor.undo),('redo',editor.redo)]:
                    start=perf_counter_ns();operation();applied=perf_counter_ns()
                    view=editor.snapshot(view);shown=perf_counter_ns()
                    editor.edit_status();end=perf_counter_ns()
                    rows.append(dict(macros=count,iteration=i,operation=name,
                        apply_and_persist_ms=(applied-start)/1e6,view_ms=(shown-applied)/1e6,total_ms=(end-start)/1e6))
            reopened=Editor(snapshot,base/'draft.json')
            assert reopened.blocked is None and reopened.snapshot()==editor.snapshot()
    summary=[]
    for count in (400,8000):
        for name in ('edit','undo','redo'):
            selected=[r for r in rows if r['macros']==count and r['operation']==name and r['iteration']>0]
            summary.append(dict(macros=count,operation=name,**{k:round(median(r[k] for r in selected),3)
                for k in ('apply_and_persist_ms','view_ms','total_ms')}))
    return dict(initialization=initialization,first_operations=[r for r in rows if r['iteration']==0],medians=summary,
        scope='Actual Editor including v3 draft fsync, incremental view and dirty; excludes GUI drawing and game saving. Five warm repetitions, first operations reported separately.')

if __name__=='__main__':
    result=benchmark()
    path=ROOT/'work/undo-prototype/editor-results.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
