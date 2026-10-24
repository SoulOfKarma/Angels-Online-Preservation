"""Resolve old non-global character IDs without ever selecting another account."""
import json


def fila(con, cid, miembro):
    user = miembro.get('usuario')
    if user:
        rows = con.execute('SELECT usuario,ranura,datos FROM personajes WHERE char_id=? AND usuario=?',
                           (int(cid),user)).fetchall()
    else:
        rows = con.execute('SELECT usuario,ranura,datos FROM personajes WHERE char_id=?', (int(cid),)).fetchall()
        if len(rows) > 1:
            rows = [row for row in rows if json.loads(row[2]).get('nombre') == miembro.get('nombre')
                    and json.loads(row[2]).get('nivel') == miembro.get('nivel')]
    return rows[0] if len(rows) == 1 else None


def coincide(miembro, ses):
    user = miembro.get('usuario')
    return user.casefold() == ses.usuario.casefold() if user else miembro.get('nombre') == ses.personaje.nombre
