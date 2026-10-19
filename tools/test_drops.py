"""Que los monstruos suelten algo, y que la plantilla de drops cargue.

Esto estuvo roto mucho tiempo sin que se notara: `json` no estaba importado
en combate.py, el NameError caia en un `except Exception` y los 12.715
drops de drops_monstruos.json quedaban muertos EN SILENCIO. El sintoma era
que de la region de Forest/Desert en adelante los bichos solo daban exp y
oro.
"""
import glob
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import combate as cb


def test_la_plantilla_de_drops_carga():
    """Lo que fallaba: volvia {} y nadie se enteraba."""
    pl = cb._cargar_drops_plantilla()
    assert pl, 'drops_monstruos.json no carga'
    for clave in ('drops', 'por_nombre', 'por_nivel'):
        assert pl.get(clave), 'falta o esta vacio: %s' % clave


def test_combate_importa_json():
    """El import que faltaba. Sin el, lo de arriba vuelve a pasar."""
    assert hasattr(cb, 'json'), 'combate.py no importa json'


def _monstruos_de_las_plantillas():
    vistos = {}
    for f in glob.glob(str(RAIZ / 'server' / 'plantillas' / '*.json')):
        try:
            d = json.loads(pathlib.Path(f).read_text(encoding='utf-8'))
        except Exception:
            continue
        sp = d.get('spawns') if isinstance(d, dict) else None
        if not isinstance(sp, list):
            continue
        for s in sp:
            if (isinstance(s, dict) and s.get('monstruo')
                    and s.get('nivel') and s.get('npc_type')):
                vistos[(s['npc_type'], s.get('nombre', ''), s['nivel'])] = f
    return vistos


def test_ningun_monstruo_se_queda_sin_botin():
    """Incluidos los de nivel alto, que caen en el respaldo por nivel."""
    vistos = _monstruos_de_las_plantillas()
    assert len(vistos) > 1000, 'no se leyeron las plantillas de mapa'
    sin = []
    for nt, nom, nv in vistos:
        cb.botin_items(nt, nom, nv)
        if not cb._DROPS_CACHE.get(nt):
            sin.append((nom, nv))
    assert not sin, '%d monstruos sin botin, p.ej. %s' % (len(sin), sin[:5])


def test_los_de_nivel_alto_tienen_de_donde_soltar():
    """El tramo que se quejaba el usuario: Forest/Desert en adelante.

    Se mira que TENGAN candidatos, no cuantas veces caen: cuanto cae lo
    decide TASA_DROP_BASE, que es del gusto de cada quien. Comprobando la
    tirada, el test se rompia solo con bajar la tasa.
    """
    for nt, nom, nv in ((20770, 'Emerald Croc', 322), (23459, 'Playful Imp', 381)):
        cb.botin_items(nt, nom, nv)
        assert cb._DROPS_CACHE.get(nt), '%s (nivel %d) no tiene nada que soltar' % (nom, nv)


def test_la_tasa_de_drop_manda_en_cuanto_cae():
    """Con la tasa alta cae casi siempre; con la baja, casi nunca.

    OJO con el bicho que se elija: tiene que NO ser jefe. Antes esto usaba
    el Emerald Croc, que lleva 王=是 en content.db, asi que desde que los
    jefes sueltan siempre daba 300 de 300 con cualquier tasa.
    """
    import configuracion as cf
    assert not cb.es_jefe(23765), 'el bicho de la prueba no puede ser jefe'
    original = cf.TASA_DROP_BASE
    try:
        cf.TASA_DROP_BASE = 10.5
        alto = sum(1 for _ in range(300) if cb.botin_items(23765, 'Hardworking Pig', 390))
        cf.TASA_DROP_BASE = 0.01
        bajo = sum(1 for _ in range(300) if cb.botin_items(23765, 'Hardworking Pig', 390))
    finally:
        cf.TASA_DROP_BASE = original
    assert alto > 240, 'con tasa 10.5 solo cayo %d de 300' % alto
    assert bajo < 60, 'con tasa 0.01 cayo %d de 300' % bajo


def test_el_botin_pega_con_el_nivel_del_bicho():
    """Un bicho de nivel 390 no puede soltar equipo de nivel 300.

    Los cubos de nivel se cortaban en 300 en los dos sitios -- al generar
    drops_monstruos.json y al elegir cubo en botin_items -- asi que TODA la
    ultima region (Clink Harbor va de 390 a 403) caia en el cubo de 300.
    Esos bichos no tienen tabla propia: su drop_id (27336 a 27343) no esta
    ni en drop.xml ni en drop_table, asi que acaban siempre en el fallback.
    """
    import sqlite3
    import sys, pathlib as _pl
    RZ = _pl.Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(RZ / 'server'))
    import combate
    con = sqlite3.connect(RZ / 'corpus' / 'content.db')

    def nivel_item(iid):
        for t in ('item', 'item2', 'item3', 'item4', 'item5', 'item6',
                  'item7', 'item8', 'item9'):
            try:
                r = con.execute('select 物品等級 from %s where id=?' % t,
                                (str(iid),)).fetchone()
            except Exception:
                continue
            if r and str(r[0] or '').isdigit():
                return int(r[0])
        return None

    for npc_type, nombre, nivel in ((23765, 'Hardworking Pig', 390),
                                    (23771, 'E-Hardworking Pig', 401),
                                    (23770, 'Icy Automaton', 399)):
        combate._DROPS_CACHE.clear()
        combate.botin_items(npc_type, nombre, nivel)
        cands = combate._DROPS_CACHE.get(npc_type) or []
        assert cands, nombre
        niveles = [nivel_item(i) for i, _ in cands]
        niveles = [n for n in niveles if n]
        assert niveles, nombre
        # ni un escalon entero por debajo del bicho
        assert min(niveles) >= nivel - 20, (nombre, nivel, min(niveles))


def test_los_cubos_llegan_hasta_el_ultimo_bicho():
    """El monstruo mas alto del juego es de nivel 485."""
    import sys, pathlib as _pl
    sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent / 'server'))
    import combate
    cubos = sorted(int(k) for k in combate._cargar_drops_plantilla()['por_nivel'])
    assert max(cubos) >= 470, cubos[-5:]


def test_los_jefes_fuera_de_chaos_sueltan_siempre():
    """Un jefe no se va nunca con las manos vacias.

    Los marca la columna 王 ("rey") de la tabla monster de content.db: son
    1.513. Antes pasaban por la misma tirada que cualquier bicho, que con
    TASA_DROP_BASE = 0.01 es menos del 1%, asi que matar un jefe no daba
    nada casi nunca.
    """
    import sys, pathlib as _pl
    sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent / 'server'))
    import combate
    # Speedy Automaton (nivel 470) y Court Eagle Cassidy, los dos con 王
    for npc_type, nombre, nivel in ((23837, 'Speedy Automaton', 470),
                                    (23838, 'Court Eagle Cassidy', 470)):
        assert combate.es_jefe(npc_type), nombre
        combate._DROPS_CACHE.clear()
        for _ in range(200):
            assert combate.botin_items(npc_type, nombre, nivel), nombre


def test_mobs_chaos_no_sueltan_siempre_aunque_tengan_marca_rey():
    """La marca 王 de los mobs Chaos no los convierte en bosses de drop."""
    import configuracion as cf
    original = cf.TASA_DROP_BASE
    try:
        cf.TASA_DROP_BASE = 0.0
        for npc_type, nombre, nivel in (
                (23673, 'C-Barren Warrior', 218),
                (23694, 'C-Chef Hoppler', 445)):
            cb._DROPS_CACHE.pop(npc_type, None)
            cb._DROP_OFICIAL_CACHE.pop(npc_type, None)
            assert not cb.botin_items(npc_type, nombre, nivel)
            assert cb._DROPS_CACHE.get(npc_type), 'debe conservar fallback por nivel'
            assert not cb._DROP_OFICIAL_CACHE.get(npc_type)
    finally:
        cf.TASA_DROP_BASE = original


def test_bosses_de_ambas_areas_chaos_sueltan_siempre():
    """Todos los bosses de progresion de las dos areas conservan el 100%."""
    import configuracion as cf
    original = cf.TASA_DROP_BASE
    try:
        cf.TASA_DROP_BASE = 0.0
        for npc_type, nombre, nivel in (
                (23684, 'C-Bosen Dino', 235),
                (23685, 'C-Magic Dragon Ambassador', 240),
                (23687, 'C-Cartastolov', 245),
                (23688, 'C-Dragon Emperor', 250),
                (23724, "Ba'shin's Gaze", 250),
                (23709, 'C-Angry Rabbit', 456),
                (23710, 'C-Meister', 458),
                (23711, 'C-Oathbound Messenger', 459),
                (23712, 'C-Ghost King', 460),
                (23713, 'C-Fallen Swordsman', 460),
                (23714, 'C-Time Lady', 460),
                (23745, "Ba'shin's Gaze", 460),
                (23839, "Ba'shin", 470)):
            cb._DROPS_CACHE.pop(npc_type, None)
            cb._DROP_OFICIAL_CACHE.pop(npc_type, None)
            assert cb.botin_items(npc_type, nombre, nivel), nombre
    finally:
        cf.TASA_DROP_BASE = original


def test_invocaciones_y_mobs_de_end_time_no_son_drop_garantizado():
    """CE, soldados, simbolos y Axialus no llenan la bolsa al matarlos."""
    import configuracion as cf
    original = cf.TASA_DROP_BASE
    try:
        cf.TASA_DROP_BASE = 0.0
        for npc_type, nombre, nivel in (
                (23704, 'CE-Chef Hoppler', 455),
                (23715, 'C-Ghost Rabbit Soldier', 450),
                (23718, 'C-Axialus Shade', 460),
                (23721, 'C-Symbol of Healing', 450)):
            cb._DROPS_CACHE.pop(npc_type, None)
            cb._DROP_OFICIAL_CACHE.pop(npc_type, None)
            assert not cb.botin_items(npc_type, nombre, nivel), nombre
    finally:
        cf.TASA_DROP_BASE = original


def test_npc_type_no_colisiona_con_id_de_tabla_ajena():
    """C-Dragon Emperor 23688 usa drop_id 27233, no tabla 23688."""
    cb._DROPS_CACHE.pop(23688, None)
    cb._DROP_OFICIAL_CACHE.pop(23688, None)
    cb.botin_items(23688, 'C-Dragon Emperor', 250)
    esperado = [tuple(x) for x in cb._cargar_drops_plantilla()['por_nivel']['250']]
    assert cb._DROPS_CACHE[23688] == esperado
    assert not cb._DROP_OFICIAL_CACHE[23688]


def test_los_bichos_normales_no_son_jefes():
    import sys, pathlib as _pl
    sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent / 'server'))
    import combate
    for npc_type in (23765, 23766, 23767):   # los cerdos de Clink Harbor
        assert not combate.es_jefe(npc_type), npc_type
    assert len(combate._JEFES) > 1000, len(combate._JEFES)


if __name__ == '__main__':
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith('test_') and callable(fn):
            try:
                fn()
                print('  OK   %s' % nombre)
            except AssertionError as e:
                fallos += 1
                print('  FALLA %s: %s' % (nombre, e))
    print('fallos:', fallos)
