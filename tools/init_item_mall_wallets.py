"""Authorize initial local AG for existing/new accounts, once, with an online backup."""
import argparse
import datetime as dt
import json
import pathlib
import sqlite3
import sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
import cuentas
import item_mall


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    db=cuentas.DB_PATH.resolve()
    if not db.is_file():raise SystemExit('Account database does not exist; refusing to create an empty replacement.')
    with sqlite3.connect('file:'+db.as_posix()+'?mode=ro',uri=True) as con:
        count=con.execute('SELECT COUNT(*) FROM cuentas').fetchone()[0]
        summary=con.execute('SELECT COUNT(*),MIN(ag),MAX(ag),SUM(ag) FROM item_mall_wallet').fetchone() if con.execute(
            "SELECT 1 FROM sqlite_master WHERE name='item_mall_wallet'").fetchone() else None
        grants=con.execute("SELECT COUNT(*) FROM item_mall_movimientos WHERE motivo='initial'").fetchone()[0] if summary else 0
    if not args.apply:
        print(json.dumps(dict(accounts=count,initial_ag=item_mall.datos()['initial_angel_gold'],apply=False,
                              wallets_count_min_max_sum=summary,initial_grants=grants)))
        return
    backups=ROOT/'data/backups';backups.mkdir(parents=True,exist_ok=True)
    target=backups/('before_item_mall_AG_'+dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.db')
    with sqlite3.connect('file:'+db.as_posix()+'?mode=ro',uri=True) as source,sqlite3.connect(target) as dest:
        source.backup(dest)
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE')
        created=item_mall.inicializar_cuentas(con)
        total=con.execute('SELECT COUNT(*) FROM item_mall_wallet').fetchone()[0]
    print(json.dumps(dict(accounts=count,wallets_created=created,wallets_total=total,
                         initial_ag=item_mall.datos()['initial_angel_gold'],backup=str(target.relative_to(ROOT)),
                         characters_modified=0,passwords_modified=0)))


if __name__=='__main__':main()
