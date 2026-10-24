"""Offline, narrowly scoped recovery. Original rows are archived before changes."""
import argparse
import copy
import datetime
import json
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parents[1]


def recover(current, source):
    if current['char_id'] != source['char_id']:
        raise ValueError('Character identity mismatch')
    result = copy.deepcopy(current)
    inv = copy.deepcopy(source['inventario'])
    qty = copy.deepcopy(source.get('cantidades', {}))
    upgrades = {k: copy.deepcopy(v) for k, v in source.get('mejoras', {}).items() if k in inv}
    # Keep new bag contents and service slots; never sum duplicated snapshot stacks.
    for slot, item in current['inventario'].items():
        n = int(slot)
        if n < 20 or 166 <= n <= 175:
            continue
        dest = slot
        matching = [k for k, v in inv.items() if v == item and 20 <= int(k) <= 154]
        if 20 <= n <= 154 and len(matching) == 1:
            dest = matching[0]
        if dest in inv and inv[dest] != item:
            dest = next((str(i) for i in range(20, 93) if str(i) not in inv), None)
            if dest is None:
                raise ValueError('No room to preserve new bag contents')
        inv[dest] = item
        qty.pop(dest, None)
        if slot in current.get('cantidades', {}):
            qty[dest] = current['cantidades'][slot]
        if slot in current.get('mejoras', {}):
            upgrades[dest] = copy.deepcopy(current['mejoras'][slot])
    qty['0'] = current['oro']
    result.update(inventario=inv, cantidades=qty, mejoras=upgrades)
    pets = copy.deepcopy(source.get('mascotas', {}))
    pets.update(copy.deepcopy(current.get('mascotas', {})))
    result['mascotas'] = pets
    return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--apply-offline', action='store_true')
    args = parser.parse_args()
    with sqlite3.connect('file:' + (ROOT/'data/cuentas_backup_skills_pre.db').as_posix() + '?mode=ro', uri=True) as backup:
        source = json.loads(backup.execute("SELECT datos FROM personajes WHERE usuario='karmav3' AND ranura=0 AND char_id=1007").fetchone()[0])
    with sqlite3.connect(ROOT/'data/cuentas.db') as con:
        con.execute('BEGIN IMMEDIATE')
        rows = con.execute("SELECT usuario,ranura,nombre,datos FROM personajes WHERE (usuario='karmav3' AND ranura=0) OR (usuario='karmav2' AND ranura=2)").fetchall()
        assert len(rows) == 2
        updates = []
        for user, slot, name, raw in rows:
            data = json.loads(raw)
            assert data['char_id'] == 1007 and name == 'KarmaV6'
            if user == 'karmav3':
                assert data['nivel'] == 434
                fixed = recover(data, source)
                assert all(fixed.get(k) == data.get(k) for k in ('nombre','nivel','habilidades','exp','oro','logros','hechizos_aprendidos','barra'))
            else:
                assert not con.execute("SELECT 1 FROM personajes WHERE nombre='KarmaV7' COLLATE NOCASE").fetchone()
                fixed = copy.deepcopy(data)
                fixed['nombre'] = 'KarmaV7'
            updates.append((fixed, user, slot, raw))
            print(json.dumps({'account':user,'name':fixed['nombre'],'level':fixed['nivel'],'items_before':len(data['inventario']),'items_after':len(fixed['inventario']),'enhanced_items':sum(v.get('veces',0)>0 for v in fixed.get('mejoras',{}).values())}))
        if not args.apply_offline:
            con.rollback()
            return
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        archive = ROOT/'data/backups'/('manual_karmav6_'+stamp+'.json')
        with archive.open('x', encoding='utf-8') as f:
            json.dump({'source':'data/cuentas_backup_skills_pre.db','rows':[{'usuario':u,'ranura':r,'nombre':n,'datos':json.loads(d)} for u,r,n,d in rows]}, f, ensure_ascii=False, indent=2)
        for fixed,user,slot,raw in updates:
            cur = con.execute('UPDATE personajes SET nombre=?,datos=?,actualizado_en=CURRENT_TIMESTAMP WHERE usuario=? AND ranura=? AND datos=?', (fixed['nombre'],json.dumps(fixed,ensure_ascii=False),user,slot,raw))
            assert cur.rowcount == 1
        con.commit()
        print('Saved recovery archive:', archive.relative_to(ROOT))
    # Use the normal export/backup path, with no stale JSON import.
    import sys
    sys.path.insert(0, str(ROOT/'server'))
    import cuentas
    cuentas._exportar_json_disco()


if __name__ == '__main__':
    main()
