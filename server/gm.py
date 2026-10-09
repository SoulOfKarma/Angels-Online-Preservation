"""GM chat / console / data/gm.txt commands.

Kept out of app.py so a GitHub pull can overwrite the upstream file and
tools/update_from_github.py can stitch these hooks back in.
"""
from __future__ import annotations

import asyncio
import logging
import pathlib
import sqlite3
import struct
import sys

import cuentas

log = logging.getLogger('app')

NIVEL_MIN = 1


def _nivel_max() -> int:
    """Character and skill cap. level.xml ends at 471, which is past the old 300."""
    import combate as _cb
    return int(getattr(_cb, 'NIVEL_MAXIMO', 471))

_CMDS_ITEM = ('item', 'give', 'i')
_CMDS_LEVEL = ('level', 'lvl', 'lv')
_CMDS_LEVELALL = ('levelall', 'lvlall')
_CMDS_SKILLS = ('skills', 'learnall', 'spells', 'skillall')
_CMDS_PET = ('pet', 'mascota')
_CMDS = frozenset(('help',) + _CMDS_ITEM + _CMDS_LEVEL + _CMDS_LEVELALL + _CMDS_SKILLS + _CMDS_PET)

AYUDA = ("GM: /item <id> [qty]  /level <n>  /levelall <n>  "
         "/skills [n]  /pet level|exp|path|evolve  "
         "/rango [1..20]  /estacion <normal|navidad|halloween|sakura|verano>")


def _app():
    import app as _a
    return _a


def _item_existe(item_id: int) -> bool:
    import inventario as _iv
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if not db.exists():
        return False
    try:
        con = sqlite3.connect(db)
        r = _iv.fila_item(con, 'id', item_id)
        con.close()
        return r is not None
    except Exception:
        return False


def _clamp_nivel(n: int) -> int:
    return max(NIVEL_MIN, min(_nivel_max(), int(n)))


def dar_item(ses, item_id: int, n: int = 1) -> str:
    a = _app()
    if getattr(ses, 'inventario', None) is None or not getattr(ses, 'personaje', None):
        return "no character in world yet"
    item_id = int(item_id)
    n = max(1, min(9999, int(n)))
    if not _item_existe(item_id):
        return f"unknown item id {item_id}"
    ranura = a._meter(ses, item_id, n)
    if ranura is None:
        return "inventory full"
    import clases as _cl
    nom = a._nombre_item(item_id)
    cartel = nom if n == 1 else f"{n}x {nom}"
    ses.enviar(_cl.aviso(cartel, tipo=0, msg_id=_cl.MSG_ITEM))
    ses.enviar(*a._refrescar(ses, [ranura]))
    a._guardar_bolsa(ses, ses.personaje.char_id)
    return f"gave {n}x {nom} ({item_id}) slot {ranura}"


def poner_nivel(ses, n: int) -> str:
    """Same packets as an Advancement Stone, but GM may set any level."""
    a = _app()
    import combate as _cb
    import clases as _cl
    p = getattr(ses, 'personaje', None)
    if p is None:
        return "no character in world yet"
    n = _clamp_nivel(n)
    yo = p.entity_id
    cid = p.char_id
    p.nivel = n
    p.exp = 0
    p.hp_max = max(p.hp_max, 500 + p.nivel * 25)
    p.mp_max = max(p.mp_max, 300 + p.nivel * 15)
    p.hp = a._vida_max(p)
    p.mp = a._mana_max(p)
    import skills as _sk
    if not getattr(p, 'banco_habilidades', None):
        p.banco_habilidades = {}
    nuevas, added = _sk.completar_ranuras_extra(
        p.habilidades, p.nivel, p.banco_habilidades)
    if added:
        p.habilidades = nuevas
        p.class_id = _sk.calcular_class_id([h[0] for h in p.habilidades])
    exp_sig = min(0xFFFFFFFF, _cb.exp_para_nivel(p.nivel + 1))
    paquetes = [
        _cl.aviso(f"Level set to {p.nivel}.", tipo=0, msg_id=_cl.MSG_ITEM),
        _cb.atributo(yo, p.hp, _cb.KIND_HP),
        _cb.atributo(yo, p.mp, _cb.KIND_MP),
        struct.pack('<HIB', 0x001D, yo, 4)
        + struct.pack('<BII', 29, p.nivel, 0)
        + struct.pack('<BII', 30, min(0xFFFFFFFF, p.exp), 0)
        + struct.pack('<BII', 31, exp_sig, 0)
        + struct.pack('<BII', 32, min(0xFFFFFFFF, p.exp), 0),
        _cb.efecto_level_up(yo, es_skill=False),
        a._stats_ses(ses),
    ]
    for i, (sid, _nv, _xp) in enumerate(added):
        ranura = len(p.habilidades) - len(added) + i + 1
        paquetes.append(_cl.aviso(_sk.nombre_rama(sid), tipo=7, msg_id=424))
        for nid, nom in (_sk.hechizos_de_rama(sid) or []):
            paquetes.append(struct.pack('<HIB', 0x001D, yo, 1)
                            + struct.pack('<BII', _cl.KIND_HECHIZO, nid, 1))
            paquetes.append(_cl.aviso(nom, tipo=7, msg_id=_cl.MSG_HECHIZO))
        paquetes.append(_cl.aviso(
            'Skill slot %d unlocked (%s). Change it at the Skill Angel.'
            % (ranura, _sk.nombre_rama(sid)),
            tipo=0, msg_id=_cl.MSG_ITEM))
    if added:
        paquetes.append(_cl.arbol(p.habilidades, banco=p.banco_habilidades))
    ses.enviar(*paquetes)
    if getattr(ses, 'usuario', None):
        cuentas.guardar_progreso(ses.usuario, cid, p.nivel, p.exp,
                                 p.hp, p.mp, p.habilidades,
                                 hp_max=p.hp_max, mp_max=p.mp_max)
        if added:
            cuentas.guardar_clase(ses.usuario, cid, p.class_id)
            cuentas.guardar_banco_habilidades(ses.usuario, cid, p.banco_habilidades)
    extra = f", {len(added)} extra skill slot(s)" if added else ""
    return f"level {p.nivel}{extra}"


def poner_skills(ses, n: int) -> str:
    """Same packets as a Skill Leveling Stone, forced to n (exp reset to 0)."""
    a = _app()
    import clases as _cl
    p = getattr(ses, 'personaje', None)
    if p is None:
        return "no character in world yet"
    n = _clamp_nivel(n)
    yo = p.entity_id
    cid = p.char_id
    nuevas = []
    for h in (p.habilidades or []):
        sid = h[0] if isinstance(h, (list, tuple)) else h
        nuevas.append((sid, n, 0))
    p.habilidades = nuevas
    if getattr(p, 'banco_habilidades', None):
        for bh_id in list(p.banco_habilidades):
            p.banco_habilidades[bh_id] = (n, 0)
    salida = [
        _cl.aviso(f"All current skills set to Level {n}.", tipo=0, msg_id=_cl.MSG_ITEM),
        _cl.arbol(p.habilidades, banco=getattr(p, 'banco_habilidades', None)),
    ]
    _ids = [h[0] for h in p.habilidades]
    _hech = _cl.hechizos_iniciales(_ids)
    _todos = [num for num, _ in _hech]
    if getattr(p, 'hechizos_aprendidos', None):
        _todos = list(set(_todos) | set(p.hechizos_aprendidos))
    if _todos:
        # otorgar_hechizos returns one packet per batch. Nesting that list
        # makes the whole send throw, so the skill tree never reaches the client.
        salida.extend(_cl.otorgar_hechizos(yo, _todos))
    for h in p.habilidades:
        salida.append(struct.pack('<HIBBII', 0x001D, yo, 1, 53, h[0], 0))
    salida.append(a._stats_ses(ses))
    ses.enviar(*salida)
    if getattr(ses, 'usuario', None):
        cuentas.guardar_progreso(ses.usuario, cid, p.nivel, p.exp,
                                 p.hp, p.mp, p.habilidades,
                                 hp_max=p.hp_max, mp_max=p.mp_max)
        if getattr(p, 'banco_habilidades', None):
            cuentas.guardar_banco_habilidades(ses.usuario, cid, p.banco_habilidades)
    return f"skills {n} ({len(p.habilidades)} current)"


def dar_hechizos_ramas(ses) -> str:
    """Grant every non-test spell of the skill trees currently equipped."""
    a = _app()
    import clases as _cl
    p = getattr(ses, 'personaje', None)
    if p is None:
        return "no character in world yet"
    ids = [h[0] if isinstance(h, (list, tuple)) else h for h in (p.habilidades or [])]
    if not ids:
        return "no skill sets equipped"
    hech = _cl.hechizos_de_ramas_activas(ids, solo_maximo=True)
    if not hech:
        return "no learnable spells on the equipped skill sets"
    if not getattr(p, 'hechizos_aprendidos', None):
        p.hechizos_aprendidos = set()
    for mid, _name, _lv in hech:
        p.hechizos_aprendidos.add(mid)
    nombres = [_cl.nombre_de_rama(sid) for sid in ids]
    yo = p.entity_id
    salida = [
        _cl.aviso(
            f"Learned {len(hech)} spells from {', '.join(nombres)}.",
            tipo=0, msg_id=_cl.MSG_ITEM,
        ),
    ]
    salida.extend(_cl.otorgar_hechizos(yo, [(m, lv) for m, _n, lv in hech]))
    ses.enviar(*salida)
    if getattr(ses, 'usuario', None):
        cuentas.guardar_hechizos(ses.usuario, p.char_id, list(p.hechizos_aprendidos))
    return f"granted {len(hech)} spells for {', '.join(nombres)}"


def _ficha_pet(ses):
    """Summoned pet, else the egg in slot 9, else the first egg in the bag."""
    a = _app()
    import inventario as _iv
    p = ses.personaje
    activa = getattr(p, 'mascota', None)
    if isinstance(activa, dict) and activa.get('fuera'):
        return activa
    inv = getattr(ses, 'inventario', None) or {}
    if inv.get(9) and _iv.es_mascota(inv.get(9)):
        return a._pet_ficha(ses, 9)
    for slot, iid in list(inv.items()):
        try:
            slot_i = int(slot)
        except (TypeError, ValueError):
            continue
        if _iv.es_mascota(iid):
            return a._pet_ficha(ses, slot_i)
    return None


def _pet(ses, args) -> tuple:
    """/pet level <n> [exp] | /pet exp <n> | /pet path 1|2 | /pet evolve 1|2."""
    import mascotas as _ms
    uso = 'usage: /pet level <n> [exp] | /pet exp <n> | /pet path 1|2 | /pet evolve 1|2'
    if not args:
        return uso, []
    sub = str(args[0]).lower()
    f = _ficha_pet(ses)
    if not f:
        return 'no pet in the bag', []
    ramas = {'1': 'mean', 'mean': 'mean', '2': 'nice', 'nice': 'nice'}
    if sub in ('level', 'nivel', 'lv', 'lvl'):
        if len(args) < 2:
            return 'usage: /pet level <n> [exp]', []
        n = int(args[1], 0)
        tope = _ms.nivel_maximo(f.get('sprite'))
        n = max(1, min(tope, n))
        _app()._pet_subir(f, n)
        barra = int(_ms.exp_para_subir(n, f.get('sprite')) or 0)
        exp = 0
        if len(args) >= 3:
            exp = int(args[2], 0)
            if barra > 0:
                exp = max(0, min(barra - 1, exp))
        f['exp'] = exp
        msg = f'pet level {n} exp {exp}'
    elif sub in ('exp', 'xp'):
        if len(args) < 2:
            return 'usage: /pet exp <n>', []
        n = int(f.get('nivel', 1) or 1)
        barra = int(_ms.exp_para_subir(n, f.get('sprite')) or 0)
        exp = int(args[1], 0)
        if barra > 0:
            exp = max(0, min(barra - 1, exp))
        f['exp'] = exp
        msg = f'pet exp {exp}'
    elif sub in ('path', 'rama', 'branch'):
        if len(args) < 2 or str(args[1]).lower() not in ramas:
            return 'usage: /pet path 1|2', []
        f['rama'] = ramas[str(args[1]).lower()]
        msg = f'pet path {f["rama"]}'
    elif sub in ('evolve', 'evolucionar'):
        if len(args) < 2 or str(args[1]).lower() not in ramas:
            return 'usage: /pet evolve 1|2', []
        _ms.evolucionar(f, ramas[str(args[1]).lower()])
        f.pop('rama', None)
        msg = f'pet evolved to {f.get("nombre")} ({f.get("sprite")})'
    else:
        return uso, []
    try:
        _app()._guardar_bolsa(ses, ses.personaje.char_id)
    except Exception:
        log.exception('GM /pet save')
    return msg, [_ms.armar(f)]


def texto_de(cuerpo: bytes):
    if not cuerpo:
        return None
    for off in (0, 1, 2, 4):
        if len(cuerpo) <= off:
            continue
        chunk = cuerpo[off:]
        nul = chunk.find(b'\x00')
        if nul >= 0:
            chunk = chunk[:nul]
        if not chunk or not all(32 <= b < 127 for b in chunk):
            continue
        t = chunk.decode('ascii').strip()
        if not t:
            continue
        head = t[1:] if t.startswith('/') else t
        word = head.split()[:1]
        if t.startswith('/') or (word and word[0].lower() in _CMDS):
            return t
    return None


def parsear(texto: str):
    t = texto.strip().lstrip('\ufeff')
    if t.startswith('/'):
        t = t[1:]
    parts = t.split()
    if not parts:
        return None
    cmd = parts[0].lower()
    if cmd == 'help':
        return ('help',)
    if cmd in _CMDS_ITEM:
        if len(parts) < 2:
            return ('err', 'usage: /item <id> [qty]')
        try:
            iid = int(parts[1], 0)
        except ValueError:
            return ('err', 'item id must be a number')
        qty = 1
        if len(parts) >= 3:
            try:
                qty = int(parts[2], 0)
            except ValueError:
                return ('err', 'qty must be a number')
        return ('item', iid, qty)
    if cmd in _CMDS_LEVEL + _CMDS_LEVELALL:
        kind = 'levelall' if cmd in _CMDS_LEVELALL else 'level'
        if len(parts) < 2:
            return ('err', f'usage: /{kind} <n>')
        try:
            n = int(parts[1], 0)
        except ValueError:
            return ('err', 'level must be a number')
        if n < NIVEL_MIN or n > _nivel_max():
            return ('err', f'level must be {NIVEL_MIN}-{_nivel_max()}')
        return (kind, n)
    if cmd in _CMDS_SKILLS:
        if len(parts) >= 2:
            try:
                n = int(parts[1], 0)
            except ValueError:
                return ('err', 'skill level must be a number')
            if n < NIVEL_MIN or n > _nivel_max():
                return ('err', f'skill level must be {NIVEL_MIN}-{_nivel_max()}')
            return ('skilllevel', n)
        return ('skills',)
    if cmd in _CMDS_PET:
        return ('pet', parts[1:])
    return None


def _avisar(ses, msg: str):
    import clases as _cl
    try:
        ses.enviar(_cl.aviso(msg, tipo=0, msg_id=_cl.MSG_ITEM))
    except Exception:
        pass


def aplicar(ses, parsed) -> str:
    kind = parsed[0]
    if kind == 'help':
        _avisar(ses, AYUDA)
        return AYUDA
    if kind == 'err':
        _avisar(ses, parsed[1])
        return parsed[1]
    if kind == 'item':
        msg = dar_item(ses, parsed[1], parsed[2])
        if not msg.startswith('gave '):
            _avisar(ses, msg)
        return msg
    if kind == 'level':
        return poner_nivel(ses, parsed[1])
    if kind == 'levelall':
        n = parsed[1]
        a = poner_nivel(ses, n)
        b = poner_skills(ses, n)
        return f"{a}; {b}"
    if kind == 'skills':
        return dar_hechizos_ramas(ses)
    if kind == 'skilllevel':
        return poner_skills(ses, parsed[1])
    if kind == 'pet':
        if getattr(ses, 'inventario', None) is None or not getattr(ses, 'personaje', None):
            return "no character in world yet"
        try:
            msg, pk = _pet(ses, parsed[1])
        except Exception as e:
            log.exception("GM /pet")
            msg, pk = f"pet error: {e!r}", []
        if pk:
            ses.enviar(*pk)
        _avisar(ses, msg)
        return msg
    return "unknown"


def probar(ses, cuerpo, addr) -> bool:
    texto = texto_de(cuerpo)
    if not texto:
        return False
    parsed = parsear(texto)
    if parsed is None:
        return False
    msg = aplicar(ses, parsed)
    log.info(f"[{addr}] GM {msg}")
    return True


def sesion_mundo(serv):
    for s in reversed(getattr(serv, 'mundos', []) or []):
        if getattr(s, 'personaje', None) and getattr(s, 'inventario', None) is not None:
            return s
    return None


def ejecutar_linea(serv, linea: str) -> str:
    parsed = parsear(linea)
    if parsed is None:
        t = linea.strip().lstrip('\ufeff')
        return f"GM unknown: {t}  (try: {AYUDA})" if t else ""
    if parsed[0] == 'help':
        return f"GM {AYUDA}"
    if parsed[0] == 'err':
        return f"GM {parsed[1]}"
    ses = sesion_mundo(serv)
    if ses is None:
        return "GM: no character in world yet"
    return f"GM {aplicar(ses, parsed)}"


async def consola(serv):
    loop = asyncio.get_running_loop()
    try:
        if not sys.stdin or not sys.stdin.isatty():
            return
    except Exception:
        return
    while True:
        try:
            linea = await loop.run_in_executor(None, sys.stdin.readline)
        except Exception:
            return
        if linea == '':
            return
        msg = ejecutar_linea(serv, linea)
        if msg:
            log.info(msg)


async def cola(serv):
    ruta = pathlib.Path(__file__).parent.parent / 'data' / 'gm.txt'
    while True:
        await asyncio.sleep(0.5)
        try:
            if not ruta.exists():
                continue
            texto = ruta.read_text(encoding='utf-8', errors='replace').lstrip('\ufeff')
            if not texto.strip():
                continue
            ruta.write_text('', encoding='utf-8')
            for linea in texto.splitlines():
                msg = ejecutar_linea(serv, linea)
                if msg:
                    log.info(msg)
        except Exception as e:
            log.debug("GM queue: %s", e)


def apply_app_hooks(app_path) -> bool:
    """Idempotent inserts so a fresh GitHub app.py gets GM again."""
    path = pathlib.Path(app_path)
    text = path.read_text(encoding='utf-8')
    orig = text
    if '\nimport gm\n' not in text and not text.startswith('import gm\n'):
        text = text.replace('import messages  # noqa\n',
                            'import messages  # noqa\nimport gm\n', 1)
    if 'self.mundos' not in text:
        text = text.replace('        self.sesiones = 0\n',
                            '        self.sesiones = 0\n        self.mundos = []\n', 1)
    regen = ("        ses.regen_task = asyncio.create_task(self._bucle_regeneracion(ses))"
             " if rol == 'mundo' else None\n")
    if 'self.mundos.append' not in text and regen in text:
        text = text.replace(
            regen,
            regen + "        if rol == 'mundo':\n            self.mundos.append(ses)\n",
            1)
    fin = "        finally:\n            if getattr(ses, 'patrulla_task', None):\n"
    if 'self.mundos.remove' not in text and fin in text:
        text = text.replace(
            fin,
            "        finally:\n            if ses in getattr(self, 'mundos', []):\n"
            "                self.mundos.remove(ses)\n"
            "            if getattr(ses, 'patrulla_task', None):\n",
            1)
    man = ('    def manejar(self, ses, opcode, m, d, addr, cuerpo=b\'\'):\n'
           '        """Login: responde MOTD + personajes + redirect. Mundo: entra al juego."""\n'
           '        if opcode == 0x0002 and ses.rol == \'login\':\n')
    if 'gm.probar' not in text and man in text:
        text = text.replace(
            man,
            '    def manejar(self, ses, opcode, m, d, addr, cuerpo=b\'\'):\n'
            '        """Login: responde MOTD + personajes + redirect. Mundo: entra al juego."""\n'
            '        if (ses.rol == \'mundo\' and getattr(ses, \'personaje\', None)\n'
            '                and gm.probar(ses, cuerpo, addr)):\n'
            '            return\n'
            '        if opcode == 0x0002 and ses.rol == \'login\':\n',
            1)
    xml = '        log.info("server.xml del cliente ya apunta aca (ip=127.0.0.1 port=16768)")\n'
    if 'gm.consola' not in text and xml in text:
        text = text.replace(
            xml,
            xml + '        log.info("GM: /item <id> [qty]  /level <n>  /levelall <n>'
            '  (also console or data/gm.txt)")\n'
            '        tareas.append(gm.consola(self))\n'
            '        tareas.append(gm.cola(self))\n',
            1)
    if text == orig:
        return False
    path.write_text(text, encoding='utf-8')
    return True
