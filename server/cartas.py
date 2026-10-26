"""El album de cartas (Alt+C): card.xml.

459 cartas en el pak vigente (update25), cada una con su sprite, nombre,
estrellas y categoria. Se consiguen matando al bicho que las suelta.

OJO con el pak: card.xml esta en once, y leyendo el equivocado salen 121
en vez de 459. Ver tools/paks.py.
"""
import json
import pathlib
import struct
import sqlite3
import copy
import logging
from types import SimpleNamespace

_TABLA = None
_SETS = None
log = logging.getLogger('cartas')
BASE = pathlib.Path(__file__).parent.parent


def tabla() -> list:
    global _TABLA
    if _TABLA is None:
        f = pathlib.Path(__file__).parent / 'plantillas' / 'cartas.json'
        try:
            _TABLA = json.loads(f.read_text(encoding='utf-8'))['filas']
        except Exception:
            _TABLA = []
    return _TABLA


def de_id(cid: int):
    for c in tabla():
        if c.get('id') == int(cid):
            return c
    return None


def por_categoria() -> dict:
    out = {}
    for c in tabla():
        out.setdefault(c.get('categoria') or '?', []).append(c)
    return out


def resumen(tengo) -> dict:
    """Cuantas lleva de cada categoria y el total."""
    ids = set(int(x) for x in (tengo or []))
    out = {}
    for cat, cs in por_categoria().items():
        out[cat] = {'tengo': sum(1 for c in cs if c['id'] in ids),
                    'de': len(cs)}
    out['total'] = {'tengo': len(ids & {c['id'] for c in tabla()}),
                    'de': len(tabla())}
    return out


def estrellas_de(tengo) -> int:
    """La suma de estrellas de las cartas que tiene."""
    ids = set(int(x) for x in (tengo or []))
    return sum(int(c.get('estrellas') or 0) for c in tabla() if c['id'] in ids)


def sets() -> dict:
    global _SETS
    if _SETS is None:
        f = BASE / 'server' / 'plantillas' / 'cardsets.json'
        _SETS = {int(s['id']): s for s in
                 json.loads(f.read_text(encoding='utf-8'))['filas']}
    return _SETS


def carta_de_item(item_id: int):
    """Only category 卡片, dynamic-data1 = card id; names are not types."""
    import inventario
    con = sqlite3.connect('file:' + (BASE / 'corpus' / 'content.db').as_posix()
                          + '?mode=ro', uri=True)
    try:
        r = inventario.fila_item(con, '"物品類別", "動態資料1"', int(item_id))
    finally:
        con.close()
    if r and r[0] == '卡片':
        try:
            return de_id(int(r[1]))
        except (TypeError, ValueError):
            pass
    return None


def atributo(entity_id: int, kind: int, indice: int, valor: int = 1) -> bytes:
    """IGG sub_5F0EF0: kind 27 -> card, kind 33 -> redeemed set.

    sub_60D5A0/sub_60D700 receive an index and operation (1=set, 0=clear).
    These are NINE-byte attributes, not the shorter HP/MP layout.
    """
    return struct.pack('<HIBBII', 0x001D, entity_id, 1, kind, indice, valor)


def bitmap(ids, limite: int) -> bytes:
    b = bytearray(limite // 8)
    for i in ids or []:
        i = int(i)
        if 0 < i < limite:
            b[i // 8] |= 1 << (i % 8)
    return bytes(b)


def perfil(crudo: bytearray, p) -> None:
    """IGG sub_5E9C90; offsets INCLUDE the 2-byte opcode.

    Replace captured account data even for an empty new Card Book.
    """
    if len(crudo) < 4119:
        raise ValueError('Profile too short for IGG Card Book bitmaps')
    crudo[3959:4087] = bitmap(getattr(p, 'cartas', []), 1024)
    crudo[4087:4119] = bitmap(getattr(p, 'cartas_canjes', []), 256)


def premios(set_id: int, eleccion: int, tengo, canjeados) -> list:
    s = sets().get(int(set_id))
    if s is None:
        raise ValueError('Unknown card set.')
    if int(set_id) in set(int(x) for x in (canjeados or [])):
        raise ValueError('This card set has already been exchanged.')
    if not set(s['cartas']).issubset(set(int(x) for x in (tengo or []))):
        raise ValueError('Collect all cards in this set first.')
    if s['elegir']:
        opciones = [r for r in s['premios'] if r[0] == eleccion]
        if not opciones:
            raise ValueError('Select a valid reward first.')
    else:
        # Lua passes -1 as an unsigned byte when all rewards apply.
        if eleccion not in (-1, 255, 0, 1, 2):
            raise ValueError('Invalid reward selection.')
        opciones = s['premios']
    if not opciones or any(int(r[2]) <= 0 for r in opciones):
        raise ValueError('This card set has no supported rewards.')
    return [(int(r[1]), int(r[2])) for r in opciones]


def _copia(ses):
    """Plan mutations off-session. A full bag or failed save changes nothing."""
    return SimpleNamespace(
        inventario=copy.deepcopy(ses.inventario),
        cantidades=copy.deepcopy(getattr(ses, 'cantidades', {}) or {}),
        instancias=copy.deepcopy(getattr(ses, 'instancias', {}) or {}),
        personaje=copy.deepcopy(ses.personaje),
    )


def _confirmar(ses, plan):
    import app, cuentas
    if not getattr(ses, 'usuario', None):
        raise ValueError('An authenticated character is required.')
    cuentas.guardar_cardbook(ses.usuario, ses.personaje.char_id, plan)
    # Preserve the live personaje identity used by combat/presence.
    ses.inventario.clear()
    ses.inventario.update(plan.inventario)
    ses.cantidades = plan.cantidades
    ids = app._instancias(ses)
    ids.clear()
    ids.update(plan.instancias)
    for nombre in ('cartas', 'cartas_canjes', 'mejoras', 'mascota', 'mascotas'):
        nuevo = getattr(plan.personaje, nombre, {})
        if getattr(ses.personaje, nombre, None) != nuevo:
            setattr(ses.personaje, nombre, nuevo)
    ses.personaje.inventario = ses.inventario
    ses.personaje.cantidades = ses.cantidades


def registrar(ses, ranura: int, sacar, refrescar) -> bool:
    """Consume exactly one genuine card, persist and update the native UI."""
    import clases
    item = ses.inventario.get(int(ranura))
    c = carta_de_item(item) if item else None
    if c is None:
        return False
    try:
        if int(ranura) < 20 or int(ranura) > 496:
            raise ValueError('Use a card from your inventory.')
        if c['id'] in set(int(x) for x in (ses.personaje.cartas or [])):
            raise ValueError('This card is already registered.')
        plan = _copia(ses)
        if sacar(plan, ranura, 1) != 1:
            raise ValueError('The card is no longer available.')
        plan.personaje.cartas = sorted(set(plan.personaje.cartas or []) | {c['id']})
        _confirmar(ses, plan)
    except ValueError as exc:
        ses.enviar(clases.aviso(str(exc), tipo=0))
        return True
    except Exception:
        log.exception('Card registration failed before confirmation')
        ses.enviar(clases.aviso('Card Book could not be saved. Try again.', tipo=0))
        return True
    ses.enviar(*refrescar(ses, [ranura]),
               atributo(ses.personaje.entity_id, 27, c['id']))
    log.info('Registered card %s (item %s, slot %s)', c['id'], item, ranura)
    return True


def canjear(ses, cuerpo: bytes, meter, refrescar) -> None:
    import clases
    if len(cuerpo) != 2:
        log.warning('Rejected malformed Card Book exchange (%s bytes)', len(cuerpo))
        return
    set_id, eleccion = cuerpo
    try:
        recompensas = premios(set_id, eleccion, ses.personaje.cartas,
                              getattr(ses.personaje, 'cartas_canjes', []))
        plan = _copia(ses)
        tocadas = []
        for item, n in recompensas:
            r = meter(plan, item, n)
            if r is None:
                raise ValueError('Your backpack has no room for all rewards.')
            tocadas.append(r)
        plan.personaje.cartas_canjes = sorted(
            set(getattr(plan.personaje, 'cartas_canjes', []) or []) | {set_id})
        _confirmar(ses, plan)
    except ValueError as exc:
        ses.enviar(clases.aviso(str(exc), tipo=0))
        return
    except Exception:
        log.exception('Card set exchange failed before confirmation')
        ses.enviar(clases.aviso('Card Book could not be saved. Try again.', tipo=0))
        return
    ses.enviar(*refrescar(ses, tocadas),
               atributo(ses.personaje.entity_id, 33, set_id))
    log.info('Exchanged card set %s -> %s', set_id, recompensas)
