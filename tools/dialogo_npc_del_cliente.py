"""Que nodo del arbol del mapa abre cada NPC, sacado del .mpc del cliente.

EL DATO. En el registro de 74 bytes de cada objeto, el +22 es el id de NPC
(tools/npcs_del_cliente.py) y el **+30 (u32) es la raiz de su dialogo** en el
arbol del mapa. Se vio con los que ya estaban comprobados a mano:

    map176  Archeology Professor (8903)  +30 = 10000   (DIALOGO_DE_NPC)
    map077  Assoc. Pioneer       (2091)  +30 = 101     "It's really rare..."
    map077  Researcher Polo      (2092)  +30 = 102     "You scared me..."
    map079  Hank                 (2114)  +30 = 62501   mision Last Survivor

Esos tres de Gulp Room no tenian dialogo: su raiz no lleva el retrato del
NPC, asi que raiz_interactiva() no los encontraba.

Solo se apuntan las raices que EXISTEN en plantillas/dialogos_mapa.json para
ese stage. Escribe plantillas/dialogo_npc_mapa.json: {stage: {npc_type: raiz}}.

    python tools/dialogo_npc_del_cliente.py
"""
import json
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import mapa_del_cliente as mc          # noqa: E402
import npcs_del_cliente as ndc         # noqa: E402

OFF_DIALOGO = 30
SALIDA = RAIZ / 'server' / 'plantillas' / 'dialogo_npc_mapa.json'


def raices(stage, ruta, arbol, tabla):
    b = pathlib.Path(ruta).read_bytes()
    m = mc.Mapa(stage, ruta)
    salida = {}
    for ob in m.objetos:
        off = m.off_objetos + ob['i'] * 74
        nid = struct.unpack_from('<H', b, off + ndc.OFF_NPC)[0]
        if nid not in tabla:
            continue
        raiz = struct.unpack_from('<I', b, off + OFF_DIALOGO)[0]
        if raiz and str(raiz) in arbol:
            salida.setdefault(str(nid), raiz)
    return salida


def main():
    arboles = json.loads((RAIZ / 'server' / 'plantillas' / 'dialogos_mapa.json')
                         .read_text(encoding='utf-8'))
    tabla = ndc._npcs()
    todo = {}
    for stage, ruta in sorted(mc.mapas_del_cliente().items()):
        arbol = arboles.get(str(stage))
        if not arbol:
            continue
        try:
            r = raices(stage, ruta, arbol, tabla)
        except Exception as e:          # mapa que el lector no entiende
            print('stage %d: %s' % (stage, e))
            continue
        if r:
            todo[str(stage)] = r
    SALIDA.write_text(json.dumps(todo, ensure_ascii=False, indent=1, sort_keys=True) + '\n',
                      encoding='utf-8')
    print('%s: %d NPC en %d mapas' % (SALIDA.name, sum(len(v) for v in todo.values()), len(todo)))
    for st in ('77', '79', '176'):
        print('  ', st, todo.get(st))


if __name__ == '__main__':
    main()
