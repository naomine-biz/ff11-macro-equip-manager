"""Explicit single-slot save and guarded recovery CLI."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path
from ff11reader.application import installations, load_snapshot
from ff11reader.adapters import LocalReader
from ff11reader.domain import Snapshot
from ff11reader.saving import prepare_save, execute_save, restore_backup, digest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path)
    parser.add_argument('--character')
    parser.add_argument('--set',dest='number',type=int)
    parser.add_argument('--slot')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--expect-before')
    parser.add_argument('--expect-after')
    parser.add_argument('--restore',type=Path)
    args=parser.parse_args()
    if args.restore:
        if not args.apply:parser.error('Restore requires --apply')
        print(json.dumps({'restored':str(restore_backup(args.restore))}));return
    roots=[str(args.root)] if args.root else installations()
    if len(roots)!=1 or not args.character or not args.number or not args.slot:
        parser.error('Specify installation, character, set and slot')
    reader=LocalReader(roots[0])
    characters=reader.load_characters()
    if reader.verify_unchanged():raise RuntimeError('Sources changed during read')
    snapshot=Snapshot('save-cli','',[*characters],{},reader.sources,reader.diagnostics)
    character=next(c for c in snapshot.characters if c.folder_id==args.character)
    plan=prepare_save(snapshot,character,args.number,args.slot)
    result={'target':plan.target,'before':digest(plan.original),'after':digest(plan.replacement),
            'changes':[asdict(x) for x in plan.changes]}
    if args.apply:
        if (args.expect_before,args.expect_after)!=(result['before'],result['after']):
            parser.error('Preview hashes required and must match')
        result['backup']=str(execute_save(plan,Path(__file__).resolve().parent/'backups'))
        result['changed_sources']=[s['path'] for s in snapshot.sources
                                  if digest(Path(s['path']).read_bytes())!=s['sha256']]
        result['only_target_changed']=set(result['changed_sources'])=={plan.target}
        (Path(result['backup'])/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
