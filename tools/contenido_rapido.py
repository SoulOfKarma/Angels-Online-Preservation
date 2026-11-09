"""Para los exportadores: las funciones del servidor abren corpus/content.db en
cada llamada y consultan `where id=?` sin indice, lo que con decenas de
miles de ids tarda horas. `activar()` hace que toda conexion a content.db
devuelva UNA copia en memoria con indices por `id` (la real no se toca y
el resultado de cada consulta es el mismo: el indice ordena por rowid).
"""
import pathlib
import sqlite3

_abrir = sqlite3.connect
_compartida = {}


class _Conexion:
    def __init__(self, con):
        self._con = con

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, k):
        return getattr(self._con, k)


def _connect(ruta, *a, **k):
    if str(ruta).endswith('content.db'):
        if 'c' not in _compartida:
            src = _abrir(pathlib.Path(ruta).resolve().as_uri() + '?mode=ro', uri=True)
            mem = _abrir(':memory:')
            src.backup(mem)
            src.close()
            for (t,) in mem.execute("select name from sqlite_master where type='table'").fetchall():
                if 'id' in [c[1] for c in mem.execute('pragma table_info("%s")' % t)]:
                    mem.execute('create index "ix_%s_id" on "%s"(id)' % (t, t))
            _compartida['c'] = mem
        return _Conexion(_compartida['c'])
    return _abrir(ruta, *a, **k)


def activar():
    sqlite3.connect = _connect
