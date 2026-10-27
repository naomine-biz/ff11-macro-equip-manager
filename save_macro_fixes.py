"""Preview by default. --apply explicitly writes the reviewed macro storage fixes."""
import argparse
from pathlib import Path
from ff11reader.application import installations, load_snapshot
from ff11reader.edit_application import Editor
from ff11reader.macro_saving import restore_macro_backup


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path)
    parser.add_argument('--character')
    parser.add_argument('--restore',type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if args.restore:
        for target in restore_macro_backup(args.restore,args.apply):print(target)
        print('復元完了' if args.apply else '復元プレビュー')
        return
    if not args.character:parser.error('--character is required')
    roots=[args.root] if args.root else installations()
    if len(roots)!=1:parser.error('Specify --root')
    editor=Editor(load_snapshot(Path(roots[0])))
    plan=editor.prepare_macro_save(args.character)
    for file in plan.files:
        print(file.target)
        for change in file.changes:print(f'{change.address} / {change.line}: {change.before}\n  -> {change.after}')
    print(f'{len(plan.files)}ファイル / {sum(len(f.changes) for f in plan.files)}行 / その他の編集 {plan.deferred}件')
    if args.apply:
        backup=editor.save_macros(plan,Path(__file__).resolve().parent/'backups'/'macros')
        print(f'保存・検証完了。バックアップ: {backup}')


if __name__=='__main__':main()
