"""One-time offline recovery from the actual pre-death inventory packet."""
import copy
import datetime
import json
import pathlib
import sqlite3
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
import inventario


def packet_inventory(body):
    count = struct.unpack_from('<I',body)[0]
    pos = 4
    inv,qty,upgrades = {},{},{}
    for _ in range(count):
        length = 86+struct.unpack_from('<H',body,pos+51)[0]
        e = body[pos:pos+length]
        assert len(e) == length and length >= 86
        slot = str(struct.unpack_from('<H',e,38)[0])
        item = struct.unpack_from('<I',e,9)[0]
        inv[slot] = item
        qty[slot] = struct.unpack_from('<I',e,40)[0]
        meta = {}
        times = e[inventario.OFF_MEJORA]
        if times:
            meta['veces'] = times
        extra = inventario.leer_extras(e)
        if extra:
            meta['extra'] = extra
        holes,gems = inventario.leer_huecos(e)
        if holes:
            meta.update(huecos=holes,gemas=gems)
        if e[58] & 1:
            meta['vinculacion'] = dict(item_id=item,dueno=struct.unpack_from('<I',e,53)[0],restantes=e[57])
        if meta:
            upgrades[slot] = meta
        pos += length
    assert pos == len(body)
    return inv,qty,upgrades


def main():
    assert sys.argv[1:] == ['--apply-offline']
    original = json.loads((ROOT/'data/backups/manual_karmav6_20261022_221918.json').read_text(encoding='utf8'))
    rows = {r['usuario']:r['datos'] for r in original['rows']}
    inventory_packet = None
    path = ROOT/'logs/sesiones/127_0_0_1_16769_20261022_222417_orden.jsonl'
    for line in path.open(encoding='utf8'):
        r = json.loads(line)
        if r['dir']=='s2c' and r['opcode']==26 and r['t']<404:
            inventory_packet = bytes.fromhex(r['hex'])
    inv,qty,meta = packet_inventory(inventory_packet)
    assert len(inv)==36 and inv['3']==69578 and qty['0']==1892008122
    with sqlite3.connect(ROOT/'data/cuentas.db') as con:
        con.execute('BEGIN IMMEDIATE')
        current = con.execute("SELECT usuario,ranura,nombre,datos FROM personajes WHERE char_id=1007").fetchall()
        damaged = next(raw for user,slot,name,raw in current if user=='karmav3' and slot==0)
        assert json.loads(damaged)['nombre']=='KarmaV7', 'Already recovered or unexpected state; refusing replay'
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        archive = ROOT/'data/backups'/('manual_arena_collision_'+stamp+'.json')
        with archive.open('x',encoding='utf8') as f:
            json.dump({'rows':current,'reason':'competition achievement cross-account overwrite'},f,ensure_ascii=False,indent=2)
        for user,slot,name,raw in current:
            data = json.loads(raw)
            if user=='karmav3':
                fixed = copy.deepcopy(rows[user])
                for key in ('nivel','exp','habilidades','hp','mp','hp_max','mp_max','sp'):
                    if key in data:
                        fixed[key] = data[key]
                fixed.update(nombre='KarmaV6',inventario=inv,cantidades=qty,mejoras=meta,oro=qty['0'],stage_id=114,tile_x=22,tile_y=36)
            elif user=='karmav2':
                fixed = copy.deepcopy(data)
                fixed['nombre'] = 'KarmaV7'
                for key in ('logros','logros_cont','titulo'):
                    if key in rows[user]:fixed[key] = copy.deepcopy(rows[user][key])
                    else:fixed.pop(key,None)
            else:
                raise ValueError('Unexpected character identity')
            con.execute('UPDATE personajes SET nombre=?,datos=?,actualizado_en=CURRENT_TIMESTAMP WHERE usuario=? AND ranura=? AND datos=?',
                        (fixed['nombre'],json.dumps(fixed),user,slot,raw))
        rid = 'd4d6c0eea21f4cbeb10bff4bd83939a8'
        result = json.loads(con.execute('SELECT datos FROM competiciones_resultados WHERE ronda=?',(rid,)).fetchone()[0])
        result['miembros']['1007']['usuario'] = 'karmav3'
        # Correct winner account is resolved explicitly below, not assumed.
        candidates = con.execute("SELECT usuario FROM personajes WHERE char_id=1005 AND nombre='KarmaV3'").fetchall()
        assert len(candidates)==1
        result['miembros']['1005']['usuario'] = candidates[0][0]
        con.execute('DELETE FROM competiciones_logros WHERE ronda=? AND char_id=1007',(rid,))
        import competicion_logros
        competicion_logros.aplicar(con,result)
        con.execute('UPDATE competiciones_resultados SET datos=? WHERE ronda=?',(json.dumps(result),rid))
        con.execute('UPDATE competiciones SET datos=? WHERE stage=240 AND json_extract(datos,\'$.id\')=?',(json.dumps(result),rid))
        con.commit()
    import cuentas
    cuentas._exportar_json_disco()
    print('Recovered KarmaV6: 36 items, original upgrades, 1892008122 gold, level434, lobby114; KarmaV7 isolated.')
    print('Archive:',archive.relative_to(ROOT))


if __name__=='__main__':main()
