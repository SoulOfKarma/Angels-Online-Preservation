"""Periodic EXP and Skill EXP distribution for active Daily Event battle stages.

While inside any active Daily Event map during the battle phase, participating
players receive periodic character experience and skill experience bonuses.
Amounts scale with character level and active buff multipliers.
"""
import struct
import time

INTERVAL = 10  # Seconds between periodic ticks
EXP_PER_LEVEL = 4800  # Character EXP per level (~2M at level 410)
EXP_CAP = 2_000_000  # Maximum character EXP per tick
EXP_MINIMUM = 50_000  # Minimum character EXP per tick
SKILL_EXP_AMOUNT = 100  # Skill EXP awarded to skills per interval (~100)


def tick(r, stamp, interval=INTERVAL):
    """Deliver periodic EXP and Skill EXP to all players inside the active battle round."""
    if stamp < r.get('_exp_tick', 0) + interval:
        return
    r['_exp_tick'] = stamp

    import app
    import clases
    import combate
    import configuracion

    sessions = __import__('daily_events')._sessions(r)
    if not sessions:
        return

    for ses in sessions:
        p = getattr(ses, 'personaje', None)
        if not p or getattr(ses, 'muerto', False) or not getattr(p, 'vivo', True):
            continue

        # Character EXP: scale with level up to ~2M, no 0x000B fake damage/healing numbers
        mult_exp = configuracion.multiplicador_exp(getattr(p, 'buffs', None))
        exp_gain = min(EXP_CAP, max(EXP_MINIMUM, int(p.nivel * EXP_PER_LEVEL * mult_exp)))

        p.exp = max(int(p.exp or 0), combate.exp_para_nivel(p.nivel)) + exp_gain
        subio_nivel = False
        while p.nivel < combate.nivel_maximo() and p.exp >= combate.exp_para_nivel(p.nivel + 1):
            p.nivel += 1
            p.hp_max += 25
            p.mp_max += 15
            subio_nivel = True
            ses.enviar(combate.atributo(p.entity_id, p.nivel, 29),
                       combate.efecto_level_up(p.entity_id))

        actual_exp, siguiente_exp = combate.exp_para_barra(p.nivel, p.exp)
        u64 = lambda v: max(0, min(int(v or 0), 0xFFFFFFFFFFFFFFFF))
        pkts = [
            struct.pack('<HIB', 0x001D, p.entity_id, 4)
            + struct.pack('<BQ', 29, u64(p.nivel))
            + struct.pack('<BQ', 30, u64(combate.exp_para_nivel(p.nivel)))
            + struct.pack('<BQ', 31, u64(siguiente_exp))
            + struct.pack('<BQ', 32, u64(actual_exp)),
            clases.aviso(str(int(exp_gain)), tipo=0, msg_id=clases.MSG_EXP)
        ]

        if subio_nivel:
            try:
                pkts.append(app._stats_ses(ses))
            except Exception:
                pass

        # Skill EXP: ~100 per interval, no 0x000B fake damage/healing numbers
        mult_skill = configuracion.multiplicador_skill_exp(getattr(p, 'buffs', None))
        skill_gain = max(10, int(round(SKILL_EXP_AMOUNT * mult_skill)))
        nuevas_habs = []
        subio_skill = False
        for h in getattr(p, 'habilidades', []) or []:
            sid, slv, sexp = h[0], h[1], h[2]
            sexp += skill_gain
            max_lv = (p.nivel + 11) if sid in range(20, 32) else p.nivel
            req = max(1, clases.exp_requerida_skill(slv, sid))
            while sexp >= req and slv < max_lv:
                sexp -= req
                slv += 1
                req = max(1, clases.exp_requerida_skill(slv, sid))
                subio_skill = True
                pkts.append(combate.efecto_level_up(p.entity_id, es_skill=True))
                pkts.append(clases.aviso_doble(clases.MSG_SKILL_SUBE, clases.nombre(sid)))
            if slv >= max_lv:
                sexp = min(sexp, req)
            pkts.append(struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 0, sid, sexp & 0xFFFFFFFF))
            pkts.append(clases.aviso_doble(clases.MSG_SKILL_EXP, clases.nombre(sid), str(skill_gain)))
            nuevas_habs.append((sid, slv, sexp))

        if nuevas_habs:
            p.habilidades = nuevas_habs
            if subio_skill:
                pkts.append(clases.arbol(p.habilidades))

        ses.enviar(*pkts)
