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
_CMDS_SKILLS = ('skills', 'spells')
_CMDS_SKILLSALL = ('skillsall', 'learnall', 'skillall')
_CMDS_SKILLS5 = ('skills5', 'skill5')
_CMDS_CLEARSKILLS = ('clearskills', 'clearskill')
_CMDS_PET = ('pet', 'mascota')
_CMDS_QUEST = ('quest', 'mision')
_CMDS_BALL = ('ball', 'baile', 'fiesta')
_CMDS_GUILDLEVEL = ('guildlevel', 'glevel', 'gldlevel', 'gldlvl', 'guildlvl', 'glvl', 'guildrank', 'grank', 'setguildlevel')
_CMDS_GUILDREP = ('guildrep', 'grep', 'gldrep')
_CMDS_GUILD = ('guild', 'gremio', 'liga')
_CMDS_TW = ('settw', 'settotemwar', 'tw', 'totemwar', 'twstart', 'twstop',
            'notice', 'aviso', 'anuncio', 'gmsg', 'twtotem')
_CMDS_FARM = ('plant', 'sembrar', 'farm', 'granja')
_CMDS = frozenset(('help',) + _CMDS_ITEM + _CMDS_LEVEL + _CMDS_LEVELALL
                  + _CMDS_SKILLS + _CMDS_SKILLSALL + _CMDS_SKILLS5
                  + _CMDS_CLEARSKILLS + _CMDS_PET + _CMDS_QUEST + _CMDS_BALL
                  + _CMDS_GUILDLEVEL + _CMDS_GUILDREP + _CMDS_GUILD
                  + _CMDS_TW + _CMDS_FARM)

AYUDA = ("GM: /item <id> [qty]  /level <n>  /levelall <n>  /guildlevel <1..10>  /guildrep <n>  "
         "/skills [lv]  /skillsall [lv]  /skills5  /clearskills  "
         "/pet level|exp|path|evolve  /ball reset  /quest <id> <step>  "
         "/rango [1..20]  /estacion <normal|navidad|halloween|sakura|verano>  /farm enter  /plant <id>  "
         "/twstart [min]  /twstop  /tw  /settw <campo> <liga>  /twtotem <1..8>  /notice <texto>")


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
        _cl.aviso(f"Level set to {p.nivel}.", tipo=0, msg_id=_cl.MSG_TEXTO),
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
            tipo=0, msg_id=_cl.MSG_TEXTO))
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
        _cl.aviso(f"All current skills set to Level {n}.", tipo=0, msg_id=_cl.MSG_TEXTO),
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


def dar_hechizos_ramas(ses, nivel_tope: int | None = None, todos: bool = False,
                       solo_rango: int | None = None) -> str:
    """Grant equipped class skills and the matching common skills.

    By default each line keeps only the highest rank whose skill requirement
    is within nivel_tope. Chain Lightning is rank I at 145 and rank V at 177.
    todos grants every rank that fits the cap. solo_rango grants only that
    rank, so 5 is Chain Lightning V and not I-IV. Warriors (sword, axe,
    spear, bow, shadowblade, shield) also get the fighter common set: every
    common stance, plus Panther Killing, Bloody Storm and Crazy Roar. Mages
    get the caster common set and not those three.
    """
    import clases as _cl
    p = getattr(ses, 'personaje', None)
    if p is None:
        return "no character in world yet"
    ids = [h[0] if isinstance(h, (list, tuple)) else h for h in (p.habilidades or [])]
    if not ids:
        return "no skill sets equipped"
    hech = _cl.hechizos_de_ramas_activas(
        ids, solo_maximo=False, max_rank=None,
        nivel_tope=nivel_tope, incluir_comunes=True,
        todos_los_rangos=todos, solo_rango=solo_rango,
    )
    if not hech:
        return "no learnable spells on the equipped skill sets"
    if not getattr(p, 'hechizos_aprendidos', None):
        p.hechizos_aprendidos = set()
    for mid, _name, _lv in hech:
        p.hechizos_aprendidos.add(mid)
    nombres = [_cl.nombre_de_rama(sid) for sid in ids]
    yo = p.entity_id
    if solo_rango is not None:
        texto = f"Learned {len(hech)} rank-{solo_rango} spells from {', '.join(nombres)}."
    elif nivel_tope is None:
        texto = f"Learned {len(hech)} spells from {', '.join(nombres)}."
    elif todos:
        texto = (f"Learned {len(hech)} spells, every rank up to skill level "
                 f"{nivel_tope}, from {', '.join(nombres)}.")
    else:
        texto = (f"Learned {len(hech)} current-rank spells up to skill level "
                 f"{nivel_tope} from {', '.join(nombres)}.")
    salida = [
        _cl.aviso(texto, tipo=0, msg_id=_cl.MSG_TEXTO),
    ]
    salida.extend(_cl.otorgar_hechizos(yo, [(m, lv) for m, _n, lv in hech]))
    ses.enviar(*salida)
    if getattr(ses, 'usuario', None):
        cuentas.guardar_hechizos(ses.usuario, p.char_id, list(p.hechizos_aprendidos))
    return f"granted {len(hech)} spells for {', '.join(nombres)}"


def limpiar_hechizos(ses) -> str:
    """Drop every spell /skills granted and the spell slots on the hotbar.

    Equipped class branches stay. The three starter spells of each branch
    are not in this list; the client puts them back the next time it enters
    the world. Icons already on screen stay until that login, because the
    client only has a grant packet.
    """
    import login as _lg
    p = getattr(ses, 'personaje', None)
    if p is None:
        return "no character in world yet"
    previos = set(getattr(p, 'hechizos_aprendidos', None) or [])
    p.hechizos_aprendidos = set()
    barra = []
    for x in list(getattr(p, 'barra', None) or [])[:24]:
        tipo, _mid = _lg.entrada_barra(x)
        barra.append(0 if tipo == 1 else x)
    p.barra = barra
    if getattr(ses, 'usuario', None):
        cuentas.guardar_hechizos(ses.usuario, p.char_id, [])
        cuentas.guardar_barra(ses.usuario, p.char_id, p.barra)
    import clases as _cl
    texto = (f"Cleared {len(previos)} learned spells. "
             "Log in again to drop the old icons.")
    aviso = _cl.aviso(texto, tipo=0, msg_id=_cl.MSG_TEXTO)
    if p.barra:
        ses.enviar(aviso, _lg._barra(p, b''))
    else:
        ses.enviar(aviso)
    return f"cleared {len(previos)} learned spells"


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
        if off > 0 and (32 <= cuerpo[off - 1] < 127):
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
    if cmd in _CMDS_SKILLS + _CMDS_SKILLSALL + _CMDS_SKILLS5:
        if cmd in _CMDS_SKILLSALL:
            kind = 'skillsall'
        elif cmd in _CMDS_SKILLS5:
            kind = 'skills5'
        else:
            kind = 'skills'
        if len(parts) >= 2:
            try:
                n = int(parts[1], 0)
            except ValueError:
                return ('err', 'skill level must be a number')
            if n < NIVEL_MIN or n > _nivel_max():
                return ('err', f'skill level must be {NIVEL_MIN}-{_nivel_max()}')
            return (kind, n)
        return (kind, None)
    if cmd in _CMDS_CLEARSKILLS:
        return ('clearskills',)
    if cmd in _CMDS_PET:
        return ('pet', parts[1:])
    if cmd in _CMDS_QUEST:
        # /quest <id> <paso>: paso en la numeracion del SERVIDOR (1 = primer
        # paso), 999 = terminada, 0 = quitarla.
        if len(parts) < 3:
            return ('err', 'usage: /quest <id> <step>  (1 = first step, 999 = done, 0 = remove)')
        try:
            return ('quest', int(parts[1], 0), int(parts[2], 0))
        except ValueError:
            return ('err', 'quest id and step must be numbers')
    if cmd in _CMDS_BALL:
        sub = parts[1].lower() if len(parts) > 1 else 'reset'
        return ('ball', sub)
    if cmd in _CMDS_GUILDLEVEL:
        if len(parts) < 2:
            return ('err', 'usage: /guildlevel <1..10>')
        try:
            return ('guildlevel', int(parts[1], 0))
        except ValueError:
            return ('err', 'usage: /guildlevel <1..10>')
    if cmd in _CMDS_GUILDREP:
        if len(parts) < 2:
            return ('err', 'usage: /guildrep <amount>')
        try:
            return ('guildrep', int(parts[1], 0))
        except ValueError:
            return ('err', 'usage: /guildrep <amount>')
    if cmd in _CMDS_GUILD:
        if len(parts) >= 3 and parts[1].lower() in ('level', 'rank', 'lvl', 'nv', 'nivel'):
            try:
                return ('guildlevel', int(parts[2], 0))
            except ValueError:
                return ('err', 'usage: /guild level <1..10>')
        if len(parts) >= 3 and parts[1].lower() in ('rep', 'reputacion', 'fame'):
            try:
                return ('guildrep', int(parts[2], 0))
            except ValueError:
                return ('err', 'usage: /guild rep <amount>')
        return ('guild', parts[1:] if len(parts) > 1 else [])
    return None


def poner_quest(ses, qid: int, paso: int) -> str:
    """Pone una mision en ese paso (o la quita con 0) y lo guarda."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return "no character in world yet"
    qs = [tuple(q) for q in (getattr(p, 'quests', None) or []) if q[0] != qid]
    if paso:
        qs.append((qid, paso))
    p.quests = qs
    try:
        import cuentas
        cuentas.guardar_quests(getattr(ses, 'usuario', None), p.char_id, qs)
    except Exception:
        log.exception("GM /quest")
    msg = (f"quest {qid} -> step {paso}" if paso else f"quest {qid} removed") + " (relog to refresh the journal)"
    _avisar(ses, msg)
    return msg


def _avisar(ses, msg: str):
    import clases as _cl
    try:
        ses.enviar(_cl.aviso(msg, tipo=0, msg_id=_cl.MSG_TEXTO))
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
    if kind in ('skills', 'skillsall', 'skills5'):
        tope = parsed[1] if len(parsed) > 1 else None
        return dar_hechizos_ramas(
            ses, tope, todos=(kind == 'skillsall'),
            solo_rango=(5 if kind == 'skills5' else None),
        )
    if kind == 'clearskills':
        return limpiar_hechizos(ses)
    if kind == 'skilllevel':
        return poner_skills(ses, parsed[1])
    if kind == 'quest':
        return poner_quest(ses, parsed[1], parsed[2])
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
    if kind == 'ball':
        p = getattr(ses, 'personaje', None)
        if not p:
            return "no character in world yet"
        import casas as _cs_gm, cuentas as _cta_gm
        _c_gm = _cs_gm.obtener_o_crear_casa(p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
        _c_gm.ball_cooldown_until = 0
        _c_gm.ball_active = False
        _c_gm.ball_end_time = 0
        p.casa = _c_gm.serializar()
        if getattr(ses, 'usuario', None):
            _cta_gm.guardar_casa(ses.usuario, p.char_id, _c_gm)
        msg = "House ball cooldown has been reset! You can host a ball now."
        _avisar(ses, msg)
        return msg
    if kind == 'guildlevel':
        import gremios as _grm_cmd
        p = getattr(ses, 'personaje', None)
        if not p:
            return "no character in world yet"
        g = _grm_cmd.obtener_gremio_de(p.char_id)
        if not g:
            _avisar(ses, "You are not in a league.")
            return "not in a league"
        target_lvl = max(1, min(10, int(parsed[1])))
        umbrales = _grm_cmd.umbrales_nivel()
        target_rep = umbrales[target_lvl - 1]
        with cuentas._LOCK:
            con = cuentas._get_conn()
            try:
                con.execute('UPDATE gremios SET nivel = ?, reputacion = max(reputacion, ?) WHERE guild_id = ?',
                            (target_lvl, target_rep, g['guild_id']))
                con.commit()
                cuentas._notificar_cambio()
            finally:
                con.close()
        actualizado = cuentas.db_obtener_gremio(g['guild_id'])
        mundos = getattr(ses, 'mundos_ref', None) or [ses]
        for s_m in _grm_cmd.miembros_online_de(g['guild_id'], mundos):
            s_m.enviar(_grm_cmd.paquete_datos_gremio(actualizado, s_m.personaje.char_id))
        ses.enviar(_grm_cmd.paquete_datos_gremio(actualizado, p.char_id))
        msg = f"League '{g['nombre']}' promoted to level/rank {target_lvl} (Rep: {actualizado['reputacion']})."
        _avisar(ses, msg)
        return msg
    if kind == 'guildrep':
        import gremios as _grm_cmd
        p = getattr(ses, 'personaje', None)
        if not p:
            return "no character in world yet"
        g = _grm_cmd.obtener_gremio_de(p.char_id)
        if not g:
            _avisar(ses, "You are not in a league.")
            return "not in a league"
        rep_val = max(0, int(parsed[1]))
        calc_lvl = _grm_cmd.nivel_por_reputacion(rep_val)
        with cuentas._LOCK:
            con = cuentas._get_conn()
            try:
                con.execute('UPDATE gremios SET reputacion = ?, nivel = max(nivel, ?) WHERE guild_id = ?',
                            (rep_val, calc_lvl, g['guild_id']))
                con.commit()
                cuentas._notificar_cambio()
            finally:
                con.close()
        actualizado = cuentas.db_obtener_gremio(g['guild_id'])
        mundos = getattr(ses, 'mundos_ref', None) or [ses]
        for s_m in _grm_cmd.miembros_online_de(g['guild_id'], mundos):
            s_m.enviar(_grm_cmd.paquete_datos_gremio(actualizado, s_m.personaje.char_id))
        ses.enviar(_grm_cmd.paquete_datos_gremio(actualizado, p.char_id))
        msg = f"League '{g['nombre']}' reputation set to {rep_val} (Level: {actualizado['nivel']})."
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
