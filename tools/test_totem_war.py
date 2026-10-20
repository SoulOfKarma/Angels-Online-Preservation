"""Totem War (server/totem_war.py): reloj GM, redireccion a las arenas,
el totem que la faccion duena no puede danar y la captura."""
import pathlib
import struct
import sys
import tempfile
import time

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app                      # noqa: E402
import combate                  # noqa: E402
import cuentas                  # noqa: E402
import login                    # noqa: E402
import totem_war as tw          # noqa: E402
import pytest                   # noqa: E402


@pytest.fixture(autouse=True)
def _modo_arena(monkeypatch):
    # Estas pruebas son del modo ARENA (las [TW] 200..207 del cliente nuevo);
    # el modo antiguo, el del totem en el campo, va en test_instancias_mecanicas.
    monkeypatch.setattr(tw, 'MODO', 'arena')


class Falsa:
    def __init__(self, nombre, faccion, stage=3):
        self.personaje = login.Personaje(nombre=nombre, char_id=hash(nombre) % 100000,
                                         nivel=300, rango=3, entity_id=5000 + len(nombre))
        self.personaje.faction = faccion
        self.personaje.stage = stage
        self.personaje.tile_x, self.personaje.tile_y = 50, 50
        self.enviados = []
        self.gid = cuentas.db_crear_gremio('Liga' + nombre, self.personaje.char_id, nombre, 300, 1)

    def enviar(self, *p):
        self.enviados.extend(p)

    enviar_inmediato = enviar

    def volcar(self):
        pass


def setup_function(_f=None):
    global _tmp, _orig
    _tmp = tempfile.TemporaryDirectory()
    _orig = (cuentas.BASE, cuentas.DB_PATH, cuentas.BACKUPS_DIR, cuentas.ARCHIVO,
             cuentas._notificar_cambio, app._tw_difundir, app._tw_sacar_de_las_arenas,
             app._tw_levantar_todos)
    cuentas.BASE = pathlib.Path(_tmp.name)
    cuentas.DB_PATH = cuentas.BASE / 'c.db'
    cuentas.BACKUPS_DIR = cuentas.BASE / 'b'
    cuentas.ARCHIVO = cuentas.BASE / 'c.json'
    cuentas._notificar_cambio = lambda: None
    cuentas._init_db()
    tw._DUENAS.clear()
    tw._DISPUTADAS.clear()
    tw._ESTADO.update(fin=0.0, por=None, arranque_horario=None)
    app._tw_difundir = lambda *p: _avisos.extend(p)
    app._tw_sacar_de_las_arenas = lambda: None
    app._tw_levantar_todos = lambda: None
    _avisos.clear()


_avisos = []


def teardown_function(_f=None):
    (cuentas.BASE, cuentas.DB_PATH, cuentas.BACKUPS_DIR, cuentas.ARCHIVO,
     cuentas._notificar_cambio, app._tw_difundir, app._tw_sacar_de_las_arenas,
     app._tw_levantar_todos) = _orig
    tw._ESTADO['fin'] = 0.0
    _tmp.cleanup()


def test_el_comando_arranca_30_min_y_repetirlo_resetea():
    assert not tw.iniciar()
    assert 29 * 60 < tw.restante() <= 30 * 60
    tw._ESTADO['fin'] = time.time() + 60
    assert tw.iniciar()                      # ya estaba: vuelve a 30
    assert tw.restante() > 29 * 60
    assert tw.terminar()
    assert not tw.activa()
    assert not tw.terminar()


def test_iniciar_no_teletransporta_y_salir_de_arena_vuelve():
    s = Falsa('Aurorano', 'Aurora', stage=3)
    assert tw.redirigir(s, 8, 30, 40) == (8, 30, 40)
    tw.iniciar()
    st, x, y = tw.redirigir(s, 8, 30, 40)
    assert (st, x, y) == (8, 30, 40)
    s.tw_origen = (8, 30, 40)
    s.personaje.stage = 200
    assert tw.redirigir(s, 8, 30, 40) == (8, 30, 40)   # salir por su tornado
    tw.terminar()
    assert tw.redirigir(s, 200, 1, 1) == (8, 30, 40)   # sin guerra: al campo
    assert tw.stage_para_guardar(200, 1, 1, s) == (8, 30, 40)


def test_la_faccion_duena_no_le_baja_vida_y_la_otra_si():
    tw.iniciar()
    tw.poner_faccion_duena(200, 1)
    m = tw.crear_totem(200)
    assert m.nombre == 'Aurora Totem' and m.hp == m.hp_max == 50_000_000
    combate.ATACANTE[0] = Falsa('Aurorano', 'Aurora')
    m.hp = m.hp - 1000
    assert m.hp == m.hp_max
    combate.ATACANTE[0] = Falsa('Bestia', 'Beasts')
    m.hp = m.hp - 1000
    assert m.hp == m.hp_max - 1000
    tw.terminar()
    m.hp = 0
    assert m.vivo, 'fuera de la guerra no se le pega'
    combate.ATACANTE[0] = None


def test_romperlo_da_el_mapa_a_la_faccion_y_avisa():
    tw.iniciar()
    m = tw.crear_totem(205)
    s = Falsa('Sombra', 'Shadow', stage=205)
    app._tw_totem_roto(s, m, 'test')
    assert tw.faccion_duena(205) == 4
    assert cuentas.db_obtener_dueno_de_territorio(205) is None
    tw.terminar()
    assert cuentas.db_obtener_dueno_de_territorio(205) == s.gid
    # Con liga duena el totem lleva el nombre de la liga (Celestia: "Moonlights").
    assert tw.nombre_totem(205) == 'LigaSombra'
    assert any(b'Thorn Wasteland' in p for p in _avisos)


def test_la_sala_de_la_arena_trae_el_totem():
    bichos = app._monstruos_de(203)
    assert tw.eid_totem(203) in bichos
    assert getattr(bichos[tw.eid_totem(203)], 'generado', False)
    assert tw.eid_totem(8) not in app._monstruos_de(8)


def test_comandos_gm():
    assert app._gm_parsear('twstart') == ('tw', ['start'])
    assert app._gm_parsear('twstart 45') == ('tw', ['start', '45'])
    assert app._gm_parsear('twstop') == ('tw', ['stop'])


if __name__ == '__main__':
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith('test_') and callable(fn):
            setup_function(fn)
            try:
                fn()
                print('  OK    %s' % nombre)
            except AssertionError as e:
                fallos += 1
                print('  FALLA %s: %s' % (nombre, e))
            finally:
                teardown_function(fn)
    print('fallos:', fallos)
    raise SystemExit(1 if fallos else 0)
