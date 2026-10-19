"""Banco de liga (s2c 0x0059) con permisos por rango.

Sacado con REA del cliente el 19/10/2026: el 0x0059 (manejador 0x607670) es
el banco de la liga, con el mismo formato que el almacen personal 0x004E, y
abre CreateBankWnd con el tipo 1 (BANK_TYPE_GUILD). Los permisos son los de
script/guild.l: GUILD_PERM_WITHDRAW_ITEM = 1 y GUILD_PERM_WITHDRAW_MONEY = 2.
"""
import pathlib
import json
import struct
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app                      # noqa: E402
import cuentas                  # noqa: E402
import dialogos                 # noqa: E402
import gremios                  # noqa: E402
import login                    # noqa: E402


class Falsa:
    def __init__(self, cid, nombre):
        self.personaje = login.Personaje(nombre=nombre, char_id=cid, nivel=50, rango=3, entity_id=1000 + cid)
        self.personaje.oro = 1_000_000
        self.oro = 1_000_000
        self.inventario = {20: 4, 21: 5}
        self.cantidades = {}
        self.usuario = nombre
        self.enviados = []
        self.banco_activo = 'liga'

    def enviar(self, *p):
        self.enviados.extend(p)

    def ops(self):
        return [struct.unpack_from('<H', x)[0] for x in self.enviados]


def _liga():
    cuentas._init_db()
    for cid in (9901, 9902):
        g = gremios.obtener_gremio_de(cid)
        if g:
            cuentas.db_disolver_gremio(g['guild_id'])
    jefe, miembro = Falsa(9901, 'BancoJefe'), Falsa(9902, 'BancoMiembro')
    with cuentas._get_conn() as con:
        for ses in (jefe, miembro):
            con.execute('INSERT OR IGNORE INTO cuentas(usuario) VALUES (?)', (ses.usuario,))
            con.execute('INSERT OR IGNORE INTO personajes(usuario, char_id, ranura, nombre, datos) '
                        'VALUES (?, ?, ?, ?, ?)',
                        (ses.usuario, ses.personaje.char_id, 0, ses.personaje.nombre, json.dumps({})))
    cuerpo = 'BancoTest'.encode().ljust(17, b'\0') + struct.pack('<I', 1)
    gremios.procesar_crear_gremio(jefe, cuerpo, [jefe, miembro])
    g = gremios.obtener_gremio_de(9901)
    cuentas.db_agregar_miembro_gremio(g['guild_id'], 9902, 'BancoMiembro', 50, 1, rango=3)
    return jefe, miembro, g


def setup_function(_func=None):
    global _tmp, _original
    _tmp = tempfile.TemporaryDirectory()
    _original = (cuentas.BASE, cuentas.DB_PATH, cuentas.BACKUPS_DIR,
                 cuentas.ARCHIVO, cuentas._notificar_cambio)
    cuentas.BASE = pathlib.Path(_tmp.name)
    cuentas.DB_PATH = cuentas.BASE / 'cuentas.db'
    cuentas.BACKUPS_DIR = cuentas.BASE / 'backups'
    cuentas.ARCHIVO = cuentas.BASE / 'cuentas.json'
    cuentas._notificar_cambio = lambda: None
    cuentas._init_db()


def teardown_function(_func=None):
    (cuentas.BASE, cuentas.DB_PATH, cuentas.BACKUPS_DIR,
     cuentas.ARCHIVO, cuentas._notificar_cambio) = _original
    _tmp.cleanup()


def test_el_banquero_abre_el_almacen_de_la_liga():
    r = dialogos.respuesta_a(5238, entidad=1, val=0, nombre='Bao Clerk', stage=3,
                             nivel=50, faccion='Aurora', graduado=False)
    assert r[0][:2] == struct.pack('<H', 0x0059)


def test_el_paquete_es_el_del_almacen_con_otro_opcode():
    jefe, _, g = _liga()
    p = gremios.paquete_banco_gremio(g, 9901, jefe.personaje.entity_id)
    assert struct.unpack_from('<H', p)[0] == 0x0059
    assert struct.unpack_from('<I', p, 2)[0] // 1000 == 2      # abre la ventana


def test_depositar_y_que_el_miembro_sin_permiso_no_saque():
    jefe, miembro, g = _liga()
    app._banco_liga_depositar(jefe, 't', 0, 0, 5000)
    app._banco_liga_depositar(jefe, 't', 20, 0, 0)
    g = gremios.obtener_gremio_de(9901)
    assert g['fondos'] == 5000
    banco = cuentas.db_banco_gremio(g['guild_id'])
    assert list(banco.values()) == [(4, 1)]
    casilla = list(banco)[0]
    # El miembro (rango 3, permiso 0 por defecto) no puede sacar
    app._banco_liga_retirar(miembro, 't', casilla, 0, 0)
    assert cuentas.db_banco_gremio(g['guild_id']), 'el miembro saco sin permiso'
    # El jefe si
    app._banco_liga_retirar(jefe, 't', casilla, 0, 0)
    assert not cuentas.db_banco_gremio(g['guild_id'])
    assert 4 in jefe.inventario.values()
    app._banco_liga_retirar(jefe, 't', 0, 0, 2000)
    assert gremios.obtener_gremio_de(9901)['fondos'] == 3000
    cuentas.db_disolver_gremio(g['guild_id'])


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
