"""Regresion TCP Python de Exposed Plot / Treatment for Food Poisoning.

Solo SQLite TEMP: entrega correcta, falta de materiales, mision previa y
premio del Inspector. No ejecuta ni compila Rust ni toca el cliente.
"""
import json
import os
import pathlib
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import comparar_login as cl
import probar_arena as arena
from probar_combate import enviar
from probar_avatar_clon import leer
from probar_mercenario import Cliente

USER = 'karma'
ITEMS = {4580: 3, 4581: 5, 4582: 5, 4583: 1}
BASE_EXP = int(json.loads((ROOT / 'server/plantillas/level_curves.json').read_text(encoding='utf-8'))['curva_nivel']['200'])


def datos(db):
    with sqlite3.connect(db) as con:
        return json.loads(con.execute('SELECT datos FROM personajes WHERE usuario=? AND ranura=0', (USER,)).fetchone()[0])


def preparar(db, case):
    p = datos(db)
    p.update(stage_id=28 if case == 'premio' else 41, tile_x=53 if case == 'premio' else 95,
             tile_y=160 if case == 'premio' else 106, nivel=200, exp=BASE_EXP, oro=1000,
             creditos=0, rango=1, buffs={}, mascota=None, quest_kills={})
    p['quests'] = [[601, 2], [602, 6], [603, 5], [604, 2 if case == 'previa' else 3]]
    if case != 'previa':
        p['quests'].append([605, {'entrega': 2, 'incompleta': 1, 'premio': 3}[case]])
    p['inventario'] = {r: i for r, i in p.get('inventario', {}).items() if int(r) < 497}
    p['cantidades'] = {r: n for r, n in p.get('cantidades', {}).items() if int(r) < 497}
    p['inventario']['501'], p['cantidades']['501'] = 4577, 7  # Token ajeno.
    if case == 'entrega':
        for slot, (item, count) in enumerate(ITEMS.items(), 506):
            p['inventario'][str(slot)], p['cantidades'][str(slot)] = item, count
    if case == 'previa':
        p['inventario']['20'], p['cantidades']['20'] = 4579, 1
    with sqlite3.connect(db) as con:
        con.execute('UPDATE personajes SET datos=? WHERE usuario=? AND ranura=0', (json.dumps(p), USER))


def mids(packets):
    return [int.from_bytes(b[2:6], 'little') for b in packets if len(b) >= 11 and int.from_bytes(b[:2], 'little') == 0x12]


def flujo(lp, wp, case, trace):
    login = Cliente(lp)
    world = None
    packets = []
    try:
        login.enviar(2, cl.auth(USER, 'x'))
        login.enviar(6, b'\0\\chr\\i263g\\20263_Wait.spr' + bytes(8))
        world = Cliente(wp)
        world.s.settimeout(.05)
        enviar(world, 2, cl.auth(USER, 'x'))
        deadline = time.monotonic() + 60
        received = []
        while not any(int.from_bytes(b[:2], 'little') == 2 for b in received):
            assert time.monotonic() < deadline, 'entrada al mundo'
            received += leer(world, .2)
        enviar(world, 9, bytes(8))
        leer(world, 2)

        def action(name, opcode, payload, expected=None):
            enviar(world, opcode, payload)
            received, end = [], time.monotonic() + (12 if expected else .6)
            while time.monotonic() < end:
                enviar(world, 17, b'')
                received += leer(world, .15)
                if expected in mids(received):
                    break
            packets.extend(received)
            trace.append({'step': name, 'messages': mids(received), 'packets': [b.hex() for b in received]})
            if expected:
                assert expected in mids(received), (case, name, expected, mids(received))

        entity = 121921 if case == 'premio' else 52
        expected = {'entrega': 60509, 'incompleta': 60504, 'previa': 60413, 'premio': 60514}[case]
        action('hablar', 5, struct.pack('<I', entity), expected)
        if case == 'entrega':
            action('entregar', 0xB, b'\x0a', 60511)
            action('siguiente', 0xB, b'\x01', 60512)
            action('cerrar', 0xB, b'\0')
            action('volver a hablar', 5, struct.pack('<I', entity), 60513)
        elif case == 'previa':
            action('dar plato', 0xB, b'\x0a', 60415)
            for message in (60416, 60501, 60502, 60503):
                action('siguiente %d' % message, 0xB, b'\x01', message)
            action('cerrar', 0xB, b'\0')
            action('segunda visita', 5, struct.pack('<I', entity), 60504)
        elif case == 'premio':
            for message in (60515, 60516, 60517):
                action('siguiente %d' % message, 0xB, b'\x01', message)
            action('cerrar', 0xB, b'\0')
            action('segunda visita', 5, struct.pack('<I', entity))
        else:
            action('cerrar', 0xB, b'\0')
    finally:
        if world:
            world.cerrar()
        login.cerrar()
    time.sleep(.7)
    return packets


def main():
    out = pathlib.Path(tempfile.mkdtemp(prefix='ao_healing_lecturer_'))
    print('Evidencia:', out, flush=True)
    results = {}
    for case in ('entrega', 'incompleta', 'previa', 'premio'):
        db = out / case / 'cuentas.db'
        cl.copiar_base(ROOT / 'data/cuentas.db', db)
        preparar(db, case)
        lp, wp = arena.puerto(), arena.puerto()
        trace = []
        with (out / (case + '.log')).open('wb') as log:
            proc = subprocess.Popen([sys.executable, '-I', str(ROOT / 'tools/servidor_daily_py.py'),
                                     cl.HOST, str(lp), str(wp)], cwd=ROOT,
                                    env=dict(os.environ, AO_DATOS=str(db.parent), PYTHONIOENCODING='utf8'),
                                    stdout=log, stderr=log)
            try:
                cl.esperar_puerto(wp, proc)
                flujo(lp, wp, case, trace)
            finally:
                proc.terminate()
                proc.wait(timeout=15)
                (out / (case + '_trace.json')).write_text(json.dumps(trace, indent=1), encoding='utf-8')
        p = datos(db)
        quests = dict(p['quests'])
        counts = {int(item): int(p['cantidades'].get(str(slot), 1))
                  for slot, item in p['inventario'].items() if int(slot) >= 497}
        assert counts.get(4577) == 7
        if case == 'entrega':
            assert quests[605] == 3 and all(i not in counts for i in ITEMS)
            assert (p['exp'] - BASE_EXP, p['creditos'], p['oro']) == (0, 0, 1000)
        elif case == 'incompleta':
            assert quests[605] == 1 and (p['exp'] - BASE_EXP, p['creditos'], p['oro']) == (0, 0, 1000)
        elif case == 'previa':
            assert quests[604] == 3 and quests[605] == 1
            assert 4579 not in p['inventario'].values()
            assert (p['exp'] - BASE_EXP, p['creditos'], p['oro']) == (6000, 80, 1000)
        else:
            assert quests[605] == 4 and (p['exp'] - BASE_EXP, p['creditos'], p['oro']) == (18000, 225, 9000)
        results[case] = {'quests': quests, 'exp': p['exp'], 'creditos': p['creditos'], 'oro': p['oro']}
        print(case, 'OK', flush=True)
    (out / 'resultado.json').write_text(json.dumps(results, indent=1), encoding='utf-8')
    print('Healing Lecturer TCP: 4 escenarios OK', flush=True)


if __name__ == '__main__':
    main()
