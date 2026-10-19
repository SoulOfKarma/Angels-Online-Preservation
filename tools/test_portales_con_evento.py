"""Portales de instancia que el CLIENTE condiciona, y la Dinosaur Arena.

Lo vio el usuario el 19/10/2026: en Cloud-top Land, Botti Palace o la
Dinosaur Arena los tornados dejaban pasar sin hacer la mecanica, y el de la
Dinosaur Arena devolvia a la entrada en vez de llevar al Dragon Emperor.
"""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import eventos as ev            # noqa: E402
import eventos_mundo as em      # noqa: E402
import dialogos_mapa as dm      # noqa: E402

PORTALES = json.loads((RAIZ / 'server' / 'plantillas' / 'portales.json')
                      .read_text(encoding='utf-8'))['mapas']


class Ctx(ev.Contexto):
    sabe = em.SABE

    def __init__(self, vivos, var=0):
        self.v, self.var = vivos, var

    def vivos_del_generador(self, tag):
        return self.v

    def variable_de_mapa(self, mapa, var):
        return self.var


def test_los_portales_condicionados_estan_marcados():
    marcados = [(st, p['tile']) for st in ('111', '145', '168', '413')
                for p in PORTALES.get(st, []) if p.get('evento_cliente')]
    assert len(marcados) >= 20, marcados


def test_con_bichos_no_se_pasa_y_con_la_sala_limpia_si():
    """Cloud-top Land (67,50): zona 76 con bichos -> dialogo 10001; limpia ->
    GOTO al TAG 5."""
    e = ev.evento_en(111, 67, 50)
    vivo = (ev.PISAR, ev.CHOCAR)
    assert ev.ejecutar(111, e, vivo, Ctx(5)) == [('dialogo', 10001)]
    assert ('ir_a_tag', 5) in ev.ejecutar(111, e, vivo, Ctx(0))


def test_el_vivo_no_dispara_los_de_alma():
    """Dinosaur Arena (154,117): con el Dragon Emperor vivo, al VIVO solo le
    sale el aviso; el GOTO a la entrada es del alma."""
    e = ev.evento_en(168, 154, 117)
    vivo = ev.ejecutar(168, e, (ev.PISAR, ev.CHOCAR), Ctx(1))
    alma = ev.ejecutar(168, e, (ev.ALMA_PISA, ev.ALMA_CHOCA), Ctx(1))
    assert not any(x[0] == 'ir_a_tag' for x in vivo), vivo
    assert ('ir_a_tag', 1) in alma, alma
    fuente = (RAIZ / 'server' / 'eventos_mundo.py').read_text(encoding='utf-8')
    assert 'disparo = (ev.PISAR, ev.CHOCAR) if not ctx.es_alma' in fuente


def test_los_guardias_de_la_arena_abren_su_dialogo():
    import app
    for st in (168, 413):
        assert app.DIALOGO_DE_NPC[(st, 8802)] == 10007
        arbol = dm._arbol(st)
        # "Go to challenge the Dragon Emperor" -> GOTO_TAG 2, dentro del asiento
        opc = dict(arbol['10007']['o'])
        assert arbol[str(opc[28289])]['a'] == [[53, [2]]]
    assert ev.casillas_de_tag(168, 2)


def test_las_zonas_de_plantilla_cuadran_con_el_cliente():
    """Los Sky Soldier de la zona 76 de Cloud-top Land son 15 y los 15 cuentan
    para la puerta (por cercania se contaban 3)."""
    import login
    d = json.loads((RAIZ / 'server' / 'plantillas' / login.PLANTILLAS_POR_STAGE[111])
                   .read_text(encoding='utf-8'))
    assert sum(1 for e in d['spawns'] if e.get('zona') == 76) == 15


if __name__ == '__main__':
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith('test_') and callable(fn):
            try:
                fn()
                print('  OK    %s' % nombre)
            except AssertionError as e:
                fallos += 1
                print('  FALLA %s: %s' % (nombre, e))
    print('fallos:', fallos)
    raise SystemExit(1 if fallos else 0)
