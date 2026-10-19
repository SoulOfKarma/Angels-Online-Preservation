"""Ajustes de instancia pedidos por el usuario el 19/10/2026.

  * Solo los JEFES sueltan botin al 100%: en Leviathan's Bedroom, Botti
    Palace o la Dinosaur Arena casi todo lleva la marca 王 y la mochila se
    llenaba. Lo que sale en tropa (mas de 2 por mapa) es un bicho comun.
  * Las lineas y objetos que saltan al tocarlos salen UNA vez al llegar y no
    se repiten mientras el jugador siga al lado ("Wahahaha, you are walking
    willingly to your death..." de Leviathan's Bedroom).
  * Los monstruos de instancia no se van de su sitio: pasean poco y vuelven a
    su casilla al soltar la persecucion.
"""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import combate as cb            # noqa: E402

FUENTE = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')


def test_los_jefes_de_verdad_siguen_siendo_jefes():
    for t in (8151, 1257, 1391, 817, 888, 890, 798):   # Dragon Emperor, Hicalu, Mendun...
        assert cb.es_jefe(t) and not cb.es_de_tropa(t), t


def test_lo_que_sale_en_tropa_no_suelta_al_100():
    assert cb.es_jefe(8146) and cb.es_de_tropa(8146)   # Flaming Turtle Dragon
    fuente = (RAIZ / 'server' / 'combate.py').read_text(encoding='utf-8')
    assert 'es_jefe(npc_type) and not es_de_tropa(npc_type)' in fuente


def test_tocar_un_objeto_salta_una_vez():
    assert "ses._ev_tocando = ahora" in FUENTE
    assert "in (getattr(ses, '_ev_tocando', None) or ())" in FUENTE


def test_los_monstruos_de_instancia_vuelven_a_su_sitio():
    assert 'def _volver_a_casa(' in FUENTE
    assert '_rango = PASEO_INSTANCIA' in FUENTE
    assert '_d_casa > CORREA_INSTANCIA' in FUENTE


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
