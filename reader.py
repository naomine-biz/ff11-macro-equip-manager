"""Workspace entry point. Game writes require a dedicated save preview."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path)
    parser.add_argument('--export',type=Path)
    args=parser.parse_args()
    if not args.export:
        from ff11reader.startup import launch
        launch(args.root)
        return
    from ff11reader.application import installations, load_snapshot
    roots=installations() if args.root is None else [str(args.root)]
    if len(roots)!=1: parser.error('Specify --root; discovered: '+str(roots))
    root=Path(roots[0]).resolve()
    if args.export:
        target=args.export.resolve()
        if target.is_relative_to(root): parser.error('Export inside game installation is forbidden')
        if target.exists(): parser.error('Export target already exists')
    snapshot=load_snapshot(root)
    if args.export:
        with args.export.open('x',encoding='utf-8') as f:
            json.dump(asdict(snapshot),f,ensure_ascii=False,indent=2)
        print(json.dumps({'characters':len(snapshot.characters),
            'macros':sum(len(c.macros) for c in snapshot.characters),
            'equipsets':sum(len(c.equipsets) for c in snapshot.characters),
            'inventory':sum(len(c.inventory) for c in snapshot.characters),
            'diagnostics':len(snapshot.diagnostics),'sources':len(snapshot.sources)},indent=2))


if __name__=='__main__': main()
