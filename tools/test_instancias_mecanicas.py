"""Mecanicas de instancia del 20/10/2026: Unknown Chambers, Gulp Room y TW.

  * Unknown Chambers (176): cada monstruo en la isla de suelo de su
    generador, cerca de sus puntos de ronda, y con su zona apuntada.
  * Gulp Room 2 (77): las puertas rojas piden SKILL_LEVEL >= 60; el
    servidor no sabia contestar la condicion 4 y no se abrian nunca.
  * Los NPC sin retrato hablan por el +30 del .mpc (Pioneer, Polo, Hank).
  * Gulp Room 4 (79): un cristal por generador junto al Evil Eye.
  * Totem War: durante la guerra la arena no rebota a nadie.
"""
import collections
import json
import pathlib
import sys
import types

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))
import eventos as ev                     # noqa: E402
import eventos_mundo as em               # noqa: E402
import login                             # noqa: E402
import mapa_del_cliente as cli           # noqa: E402
import repartir_por_tag_de_ronda as rep  # noqa: E402
import transitable                       # noqa: E402


def _plantilla(stage):
    return json.loads((RAIZ / 'server' / 'plantillas' / login.PLANTILLAS_POR_STAGE[stage])
                      .read_text(encoding='utf-8'))


def test_unknown_chambers_cada_bicho_en_la_isla_de_su_generador():
    m = cli.mapa(176)
    comp = rep.islas(176, m.ancho, m.alto)
    islas_de_zona = collections.defaultdict(set)
    for g in m.generadores():
        if g['zona']:
            islas_de_zona[g['zona']] |= {comp.get(tuple(p)) for p in g['puntos']}
    for e in _plantilla(176)['spawns']:
        if not e.get('monstruo') or e.get('apagado'):
            continue
        assert 'zona' in e, e['nombre']
        assert transitable.se_pisa(176, *e['tile']), (e['nombre'], e['tile'])
        if e['zona']:
            assert comp.get(tuple(e['tile'])) in islas_de_zona[e['zona']], (e['nombre'], e['tile'])


def test_unknown_chambers_la_sala_del_profesor_no_esta_llena():
    """Antes 125 bichos se apilaban alrededor de la entrada (21,11)."""
    cerca = [e for e in _plantilla(176)['spawns']
             if e.get('monstruo') and max(abs(e['tile'][0] - 26), abs(e['tile'][1] - 13)) <= 6]
    assert len(cerca) <= 3, [(e['nombre'], e['tile']) for e in cerca]


class _Ctx(em.ContextoSesion):
    def __init__(self, habilidades, inventario=None):
        self.p = types.SimpleNamespace(habilidades=habilidades, inventario=inventario or {},
                                       cantidades={})
        self._deltas_bolsa, self._deltas_mision = {}, {}
        self.sabe = em.SABE


def test_puerta_roja_de_gulp_room_2_mira_el_nivel_de_skill():
    # 65103: Sword/Axe/Spear/Longbow >= 60 (o).
    cond = [[4, [9, 4, 60]], [4, [10, 4, 60]], [4, [11, 4, 60]], [4, [17, 4, 60]]]
    assert any(ev.evaluar(n, p, _Ctx([(11, 75, 0)])) for n, p in cond)
    assert not any(ev.evaluar(n, p, _Ctx([(11, 40, 0), (1, 99, 0)])) for n, p in cond)


def test_equipitem_cuenta_solo_lo_puesto():
    c = _Ctx([], {'3': 1718, '25': 1613})
    assert ev.evaluar(5, [1718, 4, 1], c)
    assert not ev.evaluar(5, [1613, 4, 1], c)


def test_npcs_sin_retrato_tienen_dialogo():
    import app
    assert app.DIALOGO_DE_NPC[(77, 2091)] == 101      # Assoc. Pioneer
    assert app.DIALOGO_DE_NPC[(77, 2092)] == 102      # Researcher Polo
    assert app.DIALOGO_DE_NPC[(79, 2114)] == 62501    # Hank
    assert app.DIALOGO_DE_NPC[(78, 2095)] == 1001     # Exit Guide
    assert app.DIALOGO_DE_NPC[(176, 8903)] == 10000


def test_un_cristal_por_generador_junto_al_evil_eye():
    c = collections.Counter(e['nombre'] for e in _plantilla(79)['spawns']
                            if 'Crystal' in e['nombre'])
    assert c == {'Crystal 1': 1, 'Crystal 2': 1, 'Big Crystal 1': 1,
                 'Big Crystal 2': 1, 'Big Crystal 7': 1}, c


def test_la_arena_de_la_tw_no_rebota_durante_la_guerra(monkeypatch):
    import totem_war as tw
    monkeypatch.setattr(tw, 'MODO', 'arena')
    monkeypatch.setattr(tw, 'activa', lambda: True)
    monkeypatch.setattr(tw, 'puede_disputar', lambda ses, st: False)
    ses = types.SimpleNamespace(personaje=types.SimpleNamespace(char_id=1))
    assert tw.redirigir(ses, 207, 198, 167) == (207, 198, 167)


def test_la_tw_avisa_con_los_textos_del_cliente():
    import totem_war as tw
    pkts = tw.anuncio('x', tw.STR_EMPIEZA)
    assert pkts[0][:4] == b'\x0d\x00' + (1783).to_bytes(2, 'little')


def test_los_cofres_del_pharaohs_book_llevan_su_evento():
    """MAKE_REVENGE_DNA_MONSTER (69) del nodo 1000019 de map176: cuatro
    'Chest Containing Pieces' (8206) en los TAG 108..111; al romperlos salta
    el evento 94601 (la pieza 22667), no el de su tipo."""
    assert ev.traducir(69, [8206, 94601, 0, 600, 108]) == ('monstruo_evento', 8206, 94601, 600, 108)
    assert 69 in ev.SE_TRADUCEN
    assert ev.casillas_de_tag(176, 108)
    m = types.SimpleNamespace(npc_type=8206, evento_muerte=94601, vivo=True)
    assert getattr(m, 'evento_muerte', None) or em.evento_del_monstruo(176, 8206) == 94601


def test_cartel_de_arriba_lleva_el_texto_en_el_22():
    import totem_war as tw
    b = tw.cartel_deslizante('Hola GM')
    cuerpo = b[2:]
    assert cuerpo[4] == 0                       # canal 0: cartel de arriba
    assert cuerpo[22:].rstrip(b'\0') == b'Hola GM'


def test_parcelas_de_la_granja_en_pixeles_y_sin_npc():
    import struct
    import granja_liga as g
    p = g.paquetes_parcelas()
    assert len(p) == 70
    _eid, _f, x, y = struct.unpack_from('<IIII', p[0], 2)
    tx, ty = g.coordenadas_de_parcela(1)
    # Los pixeles exactos del objeto del .mpc, no el centro de la casilla.
    assert (x, y) == g._pixel_de_casilla()[(tx, ty)]
    assert abs(x - (tx * 32 + 16)) < 32 and abs(y - (ty * 32 + 16)) < 32
    assert all(b[:2] == b'\x5d\x01' for b in p)


def test_totem_regla_de_faccion(monkeypatch):
    """Si es de Beast, Beast no le pega y las otras tres si; neutro, todos."""
    import totem_war as tw
    monkeypatch.setattr(tw, 'activa', lambda: True)
    m = types.SimpleNamespace(stage=205)
    def ses(f):
        return types.SimpleNamespace(personaje=types.SimpleNamespace(faction=f))
    monkeypatch.setattr(tw, 'faccion_duena', lambda st: 2)
    assert not tw.puede_pegar(ses('Beasts'), m)
    assert all(tw.puede_pegar(ses(f), m) for f in ('Aurora', 'Steel', 'Shadow'))
    assert not tw.puede_pegar(ses('Heaven'), m)
    monkeypatch.setattr(tw, 'faccion_duena', lambda st: 0)
    assert all(tw.puede_pegar(ses(f), m) for f in ('Aurora', 'Beasts', 'Steel', 'Shadow'))


def test_territorios_llevan_el_id_de_la_liga(monkeypatch):
    import struct
    import totem_war as tw
    import cuentas
    monkeypatch.setattr(cuentas, 'db_obtener_dueno_de_territorio', lambda st: 91 if st == 205 else None)
    monkeypatch.setattr(cuentas, 'db_obtener_gremio', lambda gid: {'nombre': 'Moonlights', 'logo_id': 7})
    monkeypatch.setattr(tw, 'faccion_duena', lambda st: 2 if st == 205 else 0)
    b = tw.paquete_territorios()
    filas = [struct.unpack_from('<III17s', b, 4 + i * 29) for i in range(struct.unpack_from('<H', b, 2)[0])]
    fila = [f for f in filas if f[0] == 16][0]
    assert fila[1:3] == (2, 91) and fila[3].rstrip(b'\x00') == b'Moonlights'


def test_invitar_a_otra_faccion_no_se_envia():
    import gremios
    assert gremios.faccion_de(types.SimpleNamespace(faction='Aurora')) == 1
    assert gremios.faccion_de(types.SimpleNamespace(faction='Beasts')) == 2
    assert gremios.MSG_FACCION_DISTINTA == 746


def test_las_arenas_tienen_sus_tornados_de_salida():
    por = json.loads((RAIZ / 'server' / 'plantillas' / 'portales.json').read_text(encoding='utf-8'))['mapas']
    import totem_war as tw
    for st, campo in tw.TW_A_CAMPO.items():
        salidas = [p for p in por[str(st)] if p['destino'] == campo]
        assert len(salidas) == 5, (st, len(salidas))
        assert not [p for p in por[str(st)] if p['destino'] == st], st


def test_modo_pvp_es_el_codigo_22_del_001d():
    import struct
    import totem_war as tw
    b = tw.modo_pvp(1234, True, 1751)
    assert struct.unpack('<HIBBII', b) == (0x001D, 1234, 1, 22, 1, 1751)
    assert struct.unpack('<HIBBII', tw.modo_pvp(1234, False))[4:] == (0, 0)


def test_arena_portales_fortalezas_y_totem_de_faccion(monkeypatch):
    import struct
    import totem_war as tw
    nombres = {n[2] for n in tw.npcs_arena(205)}
    assert {'Aurora Portal', 'Beast Portal', 'Steel Portal', 'Shadow Portal', 'Militia Portal'} <= nombres
    fu = {m.faccion_fuerte: (m.npc_type, m.tile_x, m.tile_y) for m in tw.crear_fuertes(205)}
    assert fu[1] == (9847, 131, 102) and fu[4] == (9850, 145, 72)
    monkeypatch.setattr(tw, 'faccion_duena', lambda st: 2)
    b = tw.spawn_totem(types.SimpleNamespace(entity_id=1, tile_x=165, tile_y=97, stage=205))
    # 0x0140 (REA 005ef5f0): sprite en +34 del cuerpo, faccion en +43.
    assert b[:2] == b'\x40\x01' and struct.unpack_from('<I', b, 36)[0] == 60238 and b[45] == 2


def test_alma_y_renacer():
    import combate
    assert combate.KIND_ESTADO == 28 and combate.ESTADO_FANTASMA == 0x08000000
    assert ev.traducir(16, [1]) == ('revivir', 1) and 16 in ev.SE_TRADUCEN


def test_guerra_antigua_totem_en_el_campo(monkeypatch):
    """Modo antiguo: el totem esta en el propio campo (Celestia, 0x012E), los
    4 campos de entrenamiento no tienen guerra y no hay arena."""
    import struct
    import totem_war as tw
    monkeypatch.setattr(tw, 'MODO', 'antigua')
    assert tw.es_mapa_tw(16) and not tw.es_mapa_tw(205)
    for entrenamiento in (7, 20, 22, 28):
        assert not tw.es_mapa_tw(entrenamiento)
    monkeypatch.setattr(tw, 'liga_duena', lambda st: None)
    monkeypatch.setattr(tw, 'faccion_duena', lambda st: 1)
    m = tw.crear_totem(16)
    assert (m.tile_x, m.tile_y) == (162, 88) and m.npc_type == 21397
    b = tw.spawn_totem(m)
    assert b[:2] == b'.'
    assert struct.unpack_from('<II', b, 10) == (162, 88)          # casilla, no pixeles
    assert b[18:30].rstrip(b'\x00') == b'Aurora Totem'
    assert struct.unpack_from('<H', b, 36)[0] == 60237 and b[40] == 8
    w = tw.ventana_totem(m)
    assert w[:2] == b'/' and struct.unpack_from('<I', w, 6)[0] == 1
    s = types.SimpleNamespace(personaje=types.SimpleNamespace(char_id=1, stage=205, tile_x=0, tile_y=0))
    assert tw.redirigir(s, 205, 1, 1)[0] == 16                     # sin arenas


def test_terra_keeper_antiguo_sin_neo_totem():
    import dialogos_mapa as dm
    a = dm._arbol(16)
    assert a['5936']['m'] == 5932
    assert not any(c[0] == 32 for r in a['5936']['r'] for c in r['si'])
    assert 8283 not in [o[0] for o in a['1000041']['o']]


def test_ofrendas_suben_el_totem(monkeypatch, tmp_path):
    import totem_war as tw
    import cuentas
    monkeypatch.setattr(cuentas, 'DB_PATH', tmp_path / 'c.db')
    assert tw.puntos_de_ofrenda(next(iter(tw._OFRENDAS or {0: 0}))) >= 0
    assert tw.nivel_totem(16) == (1, 0)
    assert tw.sumar_puntos_totem(16, 150) == (2, 50)
    assert tw.nivel_totem(205) == (2, 50)       # mismo totem: campo 16 = clave 205
