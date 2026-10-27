"""Preview or restore an equipment reference batch backup."""
import argparse
from ff11reader.equipment_saving import restore_equipment_backup

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('backup')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    for path in restore_equipment_backup(args.backup,args.apply):print(path)
