"""Quita de las plantillas POBLADAS DESDE EL CLIENTE los elfos elementales
que eran marcadores del .mpc (ver poblar_del_cliente.MARCADORES). Solo toca
esos spawns: el resto de cada plantilla, incluidos ajustes a mano, se queda."""
import json, pathlib, shutil, statistics, sys, time
R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'server'))
sys.path.insert(0, str(R / 'tools'))
import login
import poblar_del_cliente as pc
P = R / 'server' / 'plantillas'
bk = R / 'work' / 'backup' / ('marcadores_%s' % time.strftime('%Y%m%d_%H%M%S'))
total = 0
for st, fich in sorted(login.PLANTILLAS_POR_STAGE.items()):
    f = P / fich
    if not f.exists():
        continue
    d = json.loads(f.read_text(encoding='utf-8'))
    if 'POBLADO DESDE EL CLIENTE' not in d.get('_nota', ''):
        continue
    mobs = [e for e in d.get('spawns', []) if e.get('monstruo')]
    nv = [e.get('nivel') or 0 for e in mobs if e.get('npc_type') not in pc.MARCADORES]
    nivel = statistics.median(nv) if nv else 0
    quitar = [e for e in mobs if pc.es_marcador(e.get('npc_type'), nivel)]
    if not quitar:
        continue
    bk.mkdir(parents=True, exist_ok=True)
    shutil.copy2(f, bk / fich)
    d['spawns'] = [e for e in d['spawns'] if e not in quitar]
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    total += len(quitar)
    print('%4d %-28s -%d marcadores (nivel tipico %s)' % (st, fich, len(quitar), nivel))
print('total quitados:', total, '| respaldo:', bk if total else '-')
