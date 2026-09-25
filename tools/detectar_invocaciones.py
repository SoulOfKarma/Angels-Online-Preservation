"""Encuentra invocaciones de otros jugadores coladas en las plantillas.

Al capturar habia otros jugadores en el mapa, y algunos usan habilidades que
crean criaturas que combaten a su lado: esqueletos, clones, espadachines.
Tecnicamente son monstruos y llegan en el mismo 0x0008 que el resto, asi que
acaban en la plantilla como si fueran poblacion fija del mapa. No lo son:
desaparecen a los minutos y no vuelven.

Hace falta una regla, no una lista, porque el usuario confirma que hay mas de
las que se recuerdan. Se probaron tres y fallaron dos:

  - Por npc_type invocable: INUTIL. El parametro 動態參數1 de magic.xml es
    generico y coincide por numero con cualquier cosa; daba "Lightgear Seller
    invocado por Killer Intent IV". Y aunque se filtre por hechizos con
    nombre de invocacion, un monstruo puede ser a la vez poblacion real Y
    invocable: blue_ocean tiene quince Sea Shark de verdad y existe un
    "Summon Sea Shark".
  - Por entity_id alto: INUTIL. Taiwan reparte ids muy dispersos y marcaba
    bichos reales como E-Hardworking Pig o Blue Ice Wing.
  - Por BLOQUES de entity_id: FUNCIONA. El servidor crea las entidades de un
    mapa de golpe al cargarlo, asi que sus ids salen en rachas contiguas. Una
    invocacion se crea despues, durante la partida, y cae sola en un id muy
    alejado de cualquier racha.

Para no marcar los totems y los Cupidos, que son legitimos y tambien van en su
propio bloque, se exige ademas que el npc_type lo invoque algun hechizo cuyo
NOMBRE diga que invoca. Las dos condiciones juntas dieron cuatro casos en las
160 plantillas, y los cuatro ids caben en un rango de 189: la misma tanda.

    python tools/detectar_invocaciones.py
    python tools/detectar_invocaciones.py --limpiar
"""
import argparse
import collections
import json
import pathlib
import re
import sqlite3

RAIZ = pathlib.Path(__file__).parent.parent
PLANTILLAS = RAIZ / 'server' / 'plantillas'

# Nombres que delatan a un hechizo de invocacion. Sin esto, el parametro
# 動態參數1 coincide por numero con medio juego.
INVOCA = re.compile(r'summon|clone|phantom|mirage|substitute|avatar'
                    r'|召喚|分身|幻影', re.I)

HUECO = 500      # dos ids a menos de esto se consideran del mismo bloque
LEJOS = 10000    # un bloque a mas de esto de cualquier otro esta aislado


def _sin_numeral(s):
    """'Ghostly Swordsman IV' -> 'ghostly swordsman'."""
    return re.sub(r'\s+[IVX]+$', '', (s or '').strip()).lower()


def invocables():
    """{npc_type: [hechizos que lo invocan]}, solo los de nombre creible.

    Dos formas de nombrar el hechizo, las dos vistas en los datos:

      - dice lo que hace: "Summon Skeleton I", "Deceptive Clone III"
      - se llama COMO LA CRIATURA que crea: el hechizo "Ghostly Swordsman IV"
        invoca al monstruo "Ghostly Swordsman". Esta segunda se escapaba, y
        era justo el cuarto caso del barrido.
    """
    db = RAIZ / 'corpus' / 'content.db'
    if not db.exists():
        return {}
    con = sqlite3.connect(db)
    bicho = {str(r[0]): r[1] for r in con.execute('select id, name from monster')}
    out = collections.defaultdict(set)
    for par, _id, nom in con.execute(
            'select 動態參數1, id, name from magic '
            'where 動態參數1 is not null and 動態參數1 != ""'):
        if not nom:
            continue
        mismo = _sin_numeral(nom) == _sin_numeral(bicho.get(str(par)))
        if INVOCA.search(nom) or mismo:
            out[str(par)].add(nom)
    con.close()
    return {k: sorted(v) for k, v in out.items()}


def bloques(ids):
    ids = sorted(ids)
    g = [[ids[0], ids[0], 1]]
    for i in ids[1:]:
        if i - g[-1][1] <= HUECO:
            g[-1][1] = i
            g[-1][2] += 1
        else:
            g.append([i, i, 1])
    return g


def sospechosos(plantilla, inv):
    """Spawns que estan SOLOS en su bloque de ids y son de tipo invocable."""
    sp = [e for e in (plantilla.get('spawns') or []) if isinstance(e, dict)]
    ids = [e['entity_id'] for e in sp if isinstance(e.get('entity_id'), int)]
    if len(ids) < 10:
        return []
    gs = bloques(ids)
    if len(gs) < 2 or max(g[2] for g in gs) < 20:
        return []
    fuera = []
    for g in gs:
        if g[2] != 1:
            continue
        dmin = min((g[0] - o[1]) if o[1] < g[0] else (o[0] - g[1])
                   for o in gs if o is not g)
        if dmin <= LEJOS:
            continue
        for e in sp:
            if e.get('entity_id') == g[0] and str(e['npc_type']) in inv:
                fuera.append((e, dmin, inv[str(e['npc_type'])][0]))
    return fuera


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limpiar', action='store_true',
                    help='sacarlas de spawns y guardarlas en _descartados')
    a = ap.parse_args()

    inv = invocables()
    print(f'npc_type invocables por hechizos con nombre de invocacion: {len(inv)}\n')
    total = 0
    for p in sorted(PLANTILLAS.glob('*.json')):
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        fuera = sospechosos(d, inv)
        if not fuera:
            continue
        total += len(fuera)
        print(f'  {p.stem}')
        for e, dmin, hech in fuera:
            print(f'      {e["nombre"]:<24} npc_type {e["npc_type"]:<7} '
                  f'tile {e["tile"]}  id {e["entity_id"]}')
            print(f'          solo en su bloque, a {dmin} del vecino; '
                  f'lo invoca "{hech}"')
        if a.limpiar:
            ids = {e['entity_id'] for e, _, _ in fuera}
            d['_descartados'] = (d.get('_descartados') or []) + [
                dict(e, _motivo='invocacion de otro jugador: estaba sola en su '
                                'bloque de entity_id, a %d del bloque vecino, y '
                                'su npc_type lo invoca "%s". Las entidades de un '
                                'mapa se crean juntas al cargarlo y salen en ids '
                                'contiguos; esta se creo durante la partida.'
                                % (dmin, hech))
                for e, dmin, hech in fuera]
            d['spawns'] = [e for e in d['spawns'] if e.get('entity_id') not in ids]
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                         encoding='utf-8')
    print(f'\ntotal: {total}')
    if total and not a.limpiar:
        print('Para sacarlas de las plantillas: --limpiar')


if __name__ == '__main__':
    main()
