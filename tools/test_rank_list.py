"""El Rank List (WND_HITPARADEWIN): formato sacado con REA, ver server/ranking.py."""
import json
import pathlib
import struct
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import cuentas                  # noqa: E402
import ranking                  # noqa: E402


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
    with cuentas._get_conn() as con:
        for i, (nom, niv, fac) in enumerate((('Alto', 300, 'Aurora'), ('Bajo', 10, 'Beasts'),
                                             ('Medio', 120, 'Aurora'))):
            con.execute('INSERT INTO cuentas(usuario) VALUES (?)', (nom,))
            con.execute('INSERT INTO personajes(usuario, char_id, ranura, nombre, datos) VALUES (?,?,?,?,?)',
                        (nom, 100 + i, 0, nom, json.dumps({'nivel': niv, 'exp': niv * 10 ** 9,
                                                           'faction': fac, 'creditos': i})))


def teardown_function(_func=None):
    (cuentas.BASE, cuentas.DB_PATH, cuentas.BACKUPS_DIR,
     cuentas.ARCHIVO, cuentas._notificar_cambio) = _original
    _tmp.cleanup()


def _filas(p):
    op, _x, tipo, ali, pag, n = struct.unpack_from('<HIBBIH', p)
    assert op == 0x0133 and len(p) == 14 + 49 * n
    out = []
    for i in range(n):
        a, b, nom, niv, seg, fac, pts, f = struct.unpack_from('<II17sIIIQI', p, 14 + 49 * i)
        out.append((nom.split(b'\0')[0].decode(), niv, fac, pts))
    return tipo, ali, pag, out


def test_abre_la_ventana_con_el_codigo_26():
    assert ranking.abrir_ventana(7) == struct.pack('<HIBBII', 0x001D, 7, 1, 26, 0, 0)


def test_pagina_de_exp_de_todas_las_facciones():
    tipo, ali, pag, filas = _filas(ranking.respuesta(struct.pack('<BII', 26, 0, 4 * 10 + 0)))
    assert (tipo, ali, pag) == (0, 4, 0)
    assert [f[0] for f in filas] == ['Alto', 'Medio', 'Bajo']
    assert filas[0][1] == 300 and filas[0][3] == 300 * 10 ** 9
    assert filas[2][2] == 1                     # Beasts en la columna Faction


def test_filtrar_por_faccion():
    _, ali, _, filas = _filas(ranking.respuesta(struct.pack('<BII', 26, 0, 0 * 10 + 0)))
    assert ali == 0 and [f[0] for f in filas] == ['Alto', 'Medio']


def test_otro_comando_no_es_del_ranking():
    assert ranking.respuesta(struct.pack('<BII', 27, 0, 0)) is None


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
