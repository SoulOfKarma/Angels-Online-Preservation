"""Las 18 lineas TW 390/400: ejecutar sus subhechizos, no solo el tooltip.

Los IDs delimitan las lineas aprendibles; potencias, probabilidades, radios,
duraciones y encadenados vienen de magic.xml (client_tables.json). Los
callbacks mantienen personaje, sala y vida para no golpear tras un viaje,
una reconexion o el respawn del objetivo.
"""
import asyncio
import logging
import math
import random
import struct
import time

import combate as cb

log = logging.getLogger('taiwan_skills')
LINEAS = dict(zip((16832, 16837, 16842, 16847, 16852, 16857, 16862, 16867,
                   16872, 16877, 16887, 16892, 16897, 16902, 16907, 16912,
                   16922, 16927),
                  ('sword', 'slashes', 'earthsplit', 'skull', 'armor', 'charge',
                   'retreat', 'barrage', 'deathcall', 'knife', 'rescue', 'heal',
                   'command', 'burst', 'rift', 'brand', 'rockskin', 'beak')))


def linea(mid):
    return next((kind for start, kind in LINEAS.items() if start <= mid < start + 5), None)


def raw(mid):
    return cb._magic_xml().get(int(mid), {})


def num(row, key, default=0):
    return int(float(row.get(key) or default))


def body(target):
    return getattr(target, 'personaje', target)


def pos(target):
    p = body(target)
    return p.tile_x, p.tile_y


def distance(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def alive(target):
    return body(target) is not None and body(target).hp > 0 and not getattr(target, 'muerto', False)


def generation(target):
    return (id(body(target)), getattr(target, 'competicion_vida', 0),
            getattr(target, 'vida_combate', 0))


def inmovilizado(ses):
    return any(isinstance(b, dict) and b.get('tw_root') and b.get('fin', 0) > time.time()
               for b in (getattr(getattr(ses, 'personaje', None), 'buffs', None) or {}).values())


def bloquear_movimiento(ses):
    if not inmovilizado(ses):
        return False
    import app
    p = ses.personaje
    move = app.Msg.registry[(0x0005, 's2c', '*')]
    ses.enviar(app.Msg.registry[(0x006d, 's2c', '*')].build(),
               struct.pack('<HIII', 3, p.entity_id, p.tile_x, p.tile_y),
               move.build(entity_id=p.entity_id, cur_x=p.tile_x * 32, cur_y=p.tile_y * 32,
                          dst_x=p.tile_x * 32, dst_y=p.tile_y * 32, speed=0))
    return True


class Lanzamiento:
    def __init__(self, ses, mid, addr):
        import presencia
        self.ses, self.mid, self.addr = ses, mid, addr
        self.p = ses.personaje
        self.stage = self.p.stage
        self.room = presencia.clave_de_mapa(ses, self.stage)
        self.presence = getattr(ses, '_mapa_presencia', None)
        self.life = getattr(ses, 'competicion_vida', 0)
        self.mag = cb.datos_magia(mid)
        self.magic = raw(mid).get('技能限制1') in ('生命技能', '死靈技能', '混亂技能', '大地技能')
        self.triggered = False

    def valid(self):
        import presencia
        return (self.ses.personaje is self.p and alive(self.ses)
                and not getattr(self.ses, 'desconectado', False)
                and not getattr(self.ses, 'mapa_cargando', False)
                and self.p.stage == self.stage
                and presencia.clave_de_mapa(self.ses, self.stage) == self.room
                and getattr(self.ses, '_mapa_presencia', None) == self.presence
                and getattr(self.ses, 'competicion_vida', 0) == self.life)

    def later(self, delay, callback):
        def run():
            if self.valid():
                callback()
        asyncio.get_event_loop().call_later(max(0, delay), cb.con_atacante(self.ses, run))

    def target_valid(self, target, life=None):
        import presencia
        if not self.valid() or not alive(target) or (life is not None and generation(target) != life):
            return False
        if hasattr(target, 'personaje'):
            return (target.personaje.stage == self.stage
                    and presencia.clave_de_mapa(target, self.stage) == self.room
                    and not getattr(target, 'desconectado', False)
                    and not getattr(target, 'mapa_cargando', False))
        return (getattr(target, 'stage', self.stage) in (None, self.stage)
                and (self.ses.monstruos or {}).get(target.entity_id) is target)

    def enemy(self, target):
        import holy_battlefield, pvp_liga, totem_war
        if not self.target_valid(target):
            return False
        if hasattr(target, 'personaje'):
            return not self.mag.get('no_jugadores') and pvp_liga.permitido(self.ses, target)
        return (not getattr(target, 'encantado', False)
                and holy_battlefield.puede_atacar(self.ses, target)
                and (not getattr(target, 'es_totem_tw', False) or totem_war.puede_pegar(self.ses, target))
                and (not getattr(target, 'es_fuerte_tw', False) or totem_war.puede_pegar_fuerte(self.ses, target)))

    def eid(self, target):
        import presencia
        if target is self.ses:
            return self.p.entity_id
        return presencia.entidad_de(target) if hasattr(target, 'personaje') else target.entity_id

    def emit(self, *packets):
        """Enviar una vez al lanzador y publicar con su entidad visible."""
        import app, presencia
        send = getattr(self.ses, 'enviar_sin_espejo', None) or self.ses.enviar_inmediato
        send(*packets)
        if hasattr(self.ses, 'volcar'):
            self.ses.volcar()
        public = presencia.entidad_de(self.ses)
        visible = []
        for packet in packets:
            copy = bytearray(packet)
            for offset in app._ENTIDADES_DEL_PAQUETE.get(struct.unpack_from('<H', packet)[0], ()):
                if len(copy) >= offset + 6 and struct.unpack_from('<I', copy, offset + 2)[0] == self.p.entity_id:
                    struct.pack_into('<I', copy, offset + 2, public)
            visible.append(bytes(copy))
        presencia.notificar_companero_accion(self.ses, *visible)

    def effect(self, mid):
        row = raw(mid)
        effect = num(row, '特效編號')
        if not effect and num(row, '公式') == 65:
            effect = num(raw(num(row, '狀態參數')), '特效編號')
        return effect

    def visual(self, mid, target=None, center=None, cast=0, close=False, source=None):
        effect = self.effect(mid)
        if not effect:
            return
        tid = self.eid(target) if target is not None else 0
        source = self.p.entity_id if source is None else source
        x, y = center or (0, 0)
        packet = (cb.cierre_de_dano(source, tid, ataque=mid, efecto=effect,
                                   es_magia=self.magic, tile_x=x, tile_y=y) if close else
                  cb.numero_de_dano(source, tid, ataque=mid, efecto=effect,
                                    cast_time=cast, es_magia=self.magic, tile_x=x, tile_y=y))
        self.emit(packet)
        if target is not None and hasattr(target, 'personaje') and target is not self.ses:
            import presencia
            local = bytearray(packet)
            struct.pack_into('<II', local, 4, presencia.entidad_de(self.ses), target.personaje.entity_id)
            target.enviar_inmediato(bytes(local))

    def around(self, center, radius):
        import pvp_liga
        monsters = [m for m in (self.ses.monstruos or {}).values()
                    if distance(pos(m), center) <= radius and self.enemy(m)]
        return monsters + pvp_liga.rivales_en_area(self.ses, *center, radius)

    def save(self, target=None):
        import cuentas
        s = target or self.ses
        p = s.personaje
        if p and getattr(s, 'usuario', None):
            cuentas.guardar_progreso(s.usuario, p.char_id, p.nivel, p.exp, p.hp, p.mp,
                                     p.habilidades, hp_max=p.hp_max, mp_max=p.mp_max,
                                     sp=getattr(s, 'sp', None), buffs=p.buffs)

    def heal(self, target, amount, mp=0):
        import app
        if not self.target_valid(target):
            return
        p = target.personaje
        before = p.hp, p.mp
        p.hp = min(app._vida_max(p, target.inventario), p.hp + max(0, amount))
        p.mp = min(app._mana_max(p, target.inventario), p.mp + max(0, mp))
        packets = []
        if amount > 0:
            # Como Cure Spell: mostrar la potencia de cura aun con HP lleno.
            # El HP autoritativo sigue limitado por el maximo efectivo.
            packets += [cb.numero_flotante(p.entity_id, amount, cb.TIPO_CURA_HP),
                        cb.atributo(p.entity_id, p.hp, cb.KIND_HP)]
        if mp > 0:
            packets += [cb.numero_flotante(p.entity_id, mp, cb.TIPO_CURA_MP),
                        cb.atributo(p.entity_id, p.mp, cb.KIND_MP)]
        if target is self.ses:
            self.emit(*packets)
        else:
            target.enviar_inmediato(*packets)
            self.emit(cb.numero_flotante(self.eid(target), amount, cb.TIPO_CURA_HP))
        log.debug('TW cura %d a %s: HP %d -> %d (+%d), MP %d -> %d (+%d)',
                  self.mid, p.nombre, before[0], p.hp, p.hp - before[0],
                  before[1], p.mp, p.mp - before[1])
        self.save(target)

    def buff(self, target, mid):
        import app
        mag = cb.datos_magia(mid)
        dur = mag['dur_ms']
        if dur <= 0 or not self.target_valid(target):
            return
        group = mag.get('priority_group', 0)
        for old, entry in list((target.personaje.buffs or {}).items()):
            if group and old != mid and isinstance(entry, dict) and entry.get('priority_group') == group:
                target.personaje.buffs.pop(old, None)
                target.enviar_inmediato(struct.pack('<HIBBII', 0x1d, target.personaje.entity_id, 1, 4, int(old), 0))
        entry = app._entrada_de_buff(mag, dur / 1000)
        app._buff_a_otro(target, mid, entry, dur, mag)
        self.save(target)
        return target.personaje.buffs[mid]

    def debuff(self, target, mid):
        if not self.enemy(target):
            return
        row, mag = raw(mid), cb.datos_magia(mid)
        dur = num(row, '持續時間')
        if not dur:
            return
        root = row.get('魔法狀態') == '定身'
        if hasattr(target, 'personaje'):
            import app
            entry = app._entrada_de_buff(mag, dur)
            entry['tw_root'] = root
            app._buff_a_otro(target, mid, entry, dur * 1000, mag)
            entry = target.personaje.buffs[mid]
            self.save(target)
        else:
            state = 'inmovilizado' if root else ''
            result = target.aplicar_efecto(dict(magia=mid, estado=state, dur_ms=dur * 1000,
                vel_mov=num(row, '移動速度'), tipo_cuerpo=row.get('體質型') == '是',
                tipo_mente=row.get('心靈型') == '是'))
            if result is None:
                return
            entry = dict(mag, fin=time.time() + dur)
            target.debuffs[mid] = entry
        self.emit(struct.pack('<HIBBII', 0x1d, self.eid(target), 1, 4, mid, dur * 1000),
                  cb.efecto_aura_objetivo(self.p.entity_id, self.eid(target), *pos(target), mid))
        # Cada marca tiene sus propios tics y generacion; dos venenos no
        # comparten el unico sangra_hp del motor antiguo.
        interval = num(row, '作用間隔')
        if interval and (num(row, 'HP') < 0 or num(row, 'MP') < 0):
            life = generation(target)
            def tick():
                if not self.target_valid(target, life) or self.effects(target).get(mid) is not entry:
                    return
                if time.time() >= entry['fin']:
                    return
                if num(row, 'HP') < 0:
                    self.fixed_damage(target, -num(row, 'HP'))
                self.drain(target, -min(0, num(row, 'MP')), 0)
                self.later(interval, tick)
            self.later(interval, tick)
        return entry

    def effects(self, target):
        return target.personaje.buffs if hasattr(target, 'personaje') else target.debuffs

    def drain(self, target, mp, sp):
        if hasattr(target, 'personaje'):
            p = target.personaje
            p.mp = max(0, p.mp - max(0, mp))
            target.sp = max(0, getattr(target, 'sp', 0) - max(0, sp))
            p.sp = target.sp
            target.enviar_inmediato(cb.atributo(p.entity_id, p.mp, cb.KIND_MP),
                                    cb.atributo(p.entity_id, target.sp, cb.KIND_SP))
            self.save(target)
        elif hasattr(target, 'mp'):
            target.mp = max(0, target.mp - max(0, mp))

    def fixed_damage(self, target, amount, mid=None):
        if not self.enemy(target):
            return 0
        if hasattr(target, 'personaje'):
            import pvp_liga
            pvp_liga._aplicar(self.ses, target, amount, False, False,
                              mid or self.mid, 0, self.magic)
        else:
            real = min(target.hp, amount)
            target.registrar_dano(real)
            target.hp = max(0, target.hp - amount)
            self.monster_hit(target, real)
        return amount

    def monster_hit(self, target, amount, critical=False):
        import app
        self.emit(cb.numero_flotante(target.entity_id, amount, cb.TIPO_DANO_CRITICO if critical else cb.TIPO_DANO),
                  cb.atributo(target.entity_id, target.porcentaje))
        if target.vivo:
            target.en_combate_con = self.p.entity_id
        else:
            target.muerto_en = time.time()
            target.en_combate_con = None
            app._procesar_muerte_monstruo(self.ses, target, self.p.entity_id, self.addr, espera=0)

    def damage(self, target, mid):
        import app, inventario, pvp_liga
        if not self.enemy(target):
            return 0
        row = raw(mid)
        magical = row.get('物理型') != '是' and (num(row, '平均傷害') > 0 or self.magic)
        stats = app._stats_ses(self.ses)
        power = struct.unpack_from('<I', stats, 46 if magical else 26)[0]
        if magical:
            mult = max(1, num(row, '平均傷害')) / cb.DENOM_HECHIZO
        else:
            power += max(0, num(row, 'HP')) * cb.PESO_STANCE
            if num(row, '公式') == 33:
                power += struct.unpack_from('<I', stats, 30)[0] * num(row, '動態參數1') / 100
            mult = 1.2 if row.get('單體多次攻擊') == '是' else 1.35
        mult *= num(row, '傷害係數', 100) / 100
        key = 'mag_dmg_pct' if magical else 'phys_dmg_pct'
        equipment = inventario.modificadores_porcentuales_equipo(self.ses.inventario).get(key, 0)
        mult *= max(0, 1 + (equipment + cb.pct_dano_buffs(self.p.buffs, magical)) / 100)
        if cb.es_jefe(getattr(target, 'npc_type', 0)) and linea(self.mid) in ('slashes', 'charge', 'barrage', 'deathcall'):
            mult *= .5
        critical = random.random() < pvp_liga._prob_critico(self.ses)
        mult *= 1.5 if critical else 1
        if hasattr(target, 'personaje'):
            defense = struct.unpack_from('<I', app._stats_ses(target), 54 if magical else 38)[0]
            amount = max(1, round(pvp_liga.dano_pvp(power, defense, mult, .03)
                                 * pvp_liga.mitigacion(target, magical)))
            pvp_liga._aplicar(self.ses, target, amount, critical, False, mid, self.effect(mid), magical)
        else:
            amount = target.recibir(round(power), es_magico=magical, mult=mult, var_pct=.03)
            self.monster_hit(target, amount, critical)
            if not self.triggered:
                self.triggered = True
                packets = app._procesar_triggers_buffs(self.ses, self.p.entity_id, target,
                                                        addr=self.addr, en_ataque=True)
                if packets:
                    self.emit(*packets)
        self.drain(target, -min(0, num(row, 'MP')), -min(0, num(row, 'SP')))
        return amount

    def threshold(self, target, mid):
        if not self.target_valid(target):
            return
        import app
        row = raw(mid)
        cutoff = num(row, '動態參數1')
        p = body(target)
        maximum = app._vida_max(p, target.inventario) if hasattr(target, 'personaje') else p.hp_max
        pct = 100 * p.hp / max(1, maximum)
        if ((cutoff > 0 and pct > cutoff) or (cutoff < 0 and pct < -cutoff)):
            if random.randint(1, 100) <= num(row, '動態參數3', 100):
                self.apply(target, num(row, '動態參數2'))

    def apply(self, target, mid, depth=0):
        """Efectos encadenados: golpe, estado o comparacion posterior de HP."""
        if not mid or depth > 12 or not self.target_valid(target):
            return
        row = raw(mid)
        if not row:
            return
        formula = num(row, '公式')
        if formula == 73:
            self.threshold(target, mid)
            return
        if num(row, '持續時間'):
            self.debuff(target, mid)
        elif row.get('攻擊型') == '是' and (num(row, 'HP') > 0 or num(row, '平均傷害') > 0):
            self.damage(target, mid)
        elif hasattr(target, 'personaje') and num(row, 'HP') > 0:
            self.heal(target, num(row, 'HP'))
        child = num(row, '轉嫁法術')
        if child and random.randint(1, 100) <= num(row, '轉嫁機率', 100):
            self.apply(target, child, depth + 1)

    def hit(self, target, mid):
        self.damage(target, mid)
        row = raw(mid)
        child = num(row, '轉嫁法術')
        if child and self.target_valid(target) and random.randint(1, 100) <= num(row, '轉嫁機率', 100):
            self.apply(target, child)

    def repeat(self, target, mid, count, radius=0):
        life = generation(target)
        def hit(index=0):
            if not self.target_valid(target, life):
                return
            # Anti-Chain Tactics: los golpes posteriores del combo pierden
            # precision cuando la victima mantiene esa defensa activa.
            if index and hasattr(target, 'personaje'):
                rates = [num(raw(int(bid)), '動態參數1', 100)
                         for bid, buff in (target.personaje.buffs or {}).items()
                         if str(bid).isdigit() and 596 <= int(bid) <= 600
                         and isinstance(buff, dict) and buff.get('fin', 0) > time.time()]
                if rates and random.randint(1, 100) > min(rates):
                    return
            targets = self.around(pos(target), radius) if radius else [target]
            for enemy in targets:
                self.hit(enemy, mid)
        hit()
        interval = num(raw(self.mid), '連擊間隔', num(raw(mid), '命中時間', 200))
        gap = cb.separacion_aoe(dict(golpes=count, intervalo_ms=interval))
        for i in range(1, count):
            self.later(gap * i, lambda i=i: hit(i))

    def move(self, target, destination):
        import desplazamientos
        if self.target_valid(target) and landing(target, destination):
            desplazamientos.reubicar(target, destination, 'TW skill %d' % self.mid)
            return True
        return False


def landing(ses, tile):
    import transitable, holy_battlefield
    p = ses.personaje
    return (transitable.se_pisa(p.stage, *tile)
            and (p.stage != 112 or not holy_battlefield.bloquear_paso(ses, pos(ses), tile)))


def friendly(cast, eid, rescue=False):
    import presencia, equipos, pvp_liga
    ses = cast.ses
    if eid in (0, cast.p.entity_id, presencia.entidad_de(ses)):
        return ses
    target = presencia.sesion_por_entidad(ses, eid)
    if not target or not cast.target_valid(target):
        return None
    if rescue and not any(s is target for s in equipos.grupo_de(ses)):
        return None
    if not pvp_liga._por_que_no(ses, target):
        return None
    return target


def summons(ses):
    return [(slot, inv) for slot in ('invocacion', 'invocacion2')
            for inv in [getattr(ses, slot, None)]
            if inv and inv.get('hp', 0) > 0 and inv.get('expira', time.time() + 1) > time.time()]


def execute(c, kind, target, center, companions):
    import app
    row = raw(c.mid)
    child = num(row, '轉嫁法術')
    if kind == 'rockskin':
        c.buff(c.ses, c.mid)
    elif kind == 'sword':
        c.buff(c.ses, child)
        strike = num(row, '動態參數2')
        def slash():
            for enemy in c.around(pos(c.ses), num(raw(strike), '範圍')):
                c.hit(enemy, strike)
        c.later(num(row, '持續時間') + num(raw(strike), '命中時間') / 1000, slash)
    elif kind in ('heal', 'rescue'):
        if not c.target_valid(target):
            return
        if kind == 'rescue':
            a, b = pos(c.ses), pos(target)
            if not landing(c.ses, b) or not landing(target, a):
                return
            if target is not c.ses:
                c.move(c.ses, b)
                c.move(target, a)
            c.heal(target, num(raw(child), 'HP'))
            transfer = raw(num(raw(child), '轉嫁法術'))
            c.buff(c.ses, num(transfer, '動態參數2'))
            c.save(target)
        else:
            c.heal(target, num(row, 'HP'))
            c.threshold(target, child)
    elif kind == 'rift':
        if not c.move(c.ses, center):
            return
        shock = num(row, '動態參數1')
        def impact():
            for enemy in c.around(center, num(raw(shock), '範圍')):
                c.hit(enemy, shock)
        c.later(num(raw(shock), '命中時間') / 1000, impact)
    elif kind == 'command':
        entry = c.buff(c.ses, c.mid)
        spell = num(row, '動態參數1')
        interval = num(row, '動態參數2') / 1000
        uses = num(row, '動態參數3')
        def pulse(n=0):
            if c.p.buffs.get(c.mid) is not entry or time.time() >= entry['fin']:
                return
            for _, inv in summons(c.ses):
                center_inv = inv['tile_x'], inv['tile_y']
                c.visual(spell, center=center_inv, source=inv['entity_id'])
                c.visual(spell, center=center_inv, close=True, source=inv['entity_id'])
                for enemy in c.around(center_inv, num(raw(spell), '範圍')):
                    c.debuff(enemy, spell)
            if n + 1 < uses:
                c.later(interval, lambda: pulse(n + 1))
            else:
                c.p.buffs.pop(c.mid, None)
                c.emit(struct.pack('<HIBBII', 0x1d, c.p.entity_id, 1, 4, c.mid, 0))
        pulse()
    elif kind == 'burst':
        strike = num(row, '動態參數1')
        for slot, inv in companions:
            if getattr(c.ses, slot, None) is not inv or inv.get('hp', 0) <= 0:
                continue
            center_inv = inv['tile_x'], inv['tile_y']
            setattr(c.ses, slot, None)
            c.emit(cb.atributo(inv['entity_id'], 0, cb.KIND_HP), cb.despawn_monstruo(inv['entity_id']))
            c.visual(strike, center=center_inv)
            c.visual(strike, center=center_inv, close=True)
            for enemy in c.around(center_inv, num(row, '動態參數2')):
                life = generation(enemy)
                def impact(enemy=enemy, life=life):
                    if c.target_valid(enemy, life):
                        c.hit(enemy, strike)
                c.later(num(raw(strike), '命中時間') / 1000, impact)
        c.ses.enviar(struct.pack('<HIBBI', 0x13, c.p.entity_id, 1, 0x3d, 0))
    elif target is not None and c.enemy(target):
        if kind in ('knife', 'brand'):
            brand(c, target)
        elif kind == 'charge':
            candidates = [(target.tile_x + dx, target.tile_y + dy) if not hasattr(target, 'personaje')
                          else (body(target).tile_x + dx, body(target).tile_y + dy)
                          for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]
            destination = next((tile for tile in sorted(candidates, key=lambda tile: distance(pos(c.ses), tile))
                                if landing(c.ses, tile)), None)
            if destination is None or not c.move(c.ses, destination):
                return
            combo = raw(num(raw(child), '轉嫁法術'))
            c.repeat(target, num(combo, '轉嫁法術'), num(combo, '動態參數2'))
        elif kind in ('barrage', 'deathcall'):
            c.repeat(target, child, num(row, '動態參數2'), num(raw(child), '範圍'))
        else:
            c.hit(target, c.mid)
            if kind == 'armor':
                wave = num(raw(child), '動態參數2')
                impact = pos(target)
                def shatter():
                    c.visual(wave, center=impact)
                    c.visual(wave, center=impact, close=True)
                    for enemy in c.around(impact, num(raw(wave), '範圍')):
                        c.debuff(enemy, wave)
                c.later(num(raw(child), '持續時間'), shatter)
            elif kind == 'retreat':
                transfer = raw(num(raw(child), '動態參數2'))
                steps = num(transfer, '動態參數1')
                x, y = pos(c.ses)
                tile = next(((x + n, y) for n in range(steps, 0, -1)
                             if landing(c.ses, (x + n, y))), None)
                if tile:
                    c.move(c.ses, tile)
            elif kind == 'beak':
                if not alive(target):
                    c.heal(c.ses, app._vida_max(c.p, c.ses.inventario) * num(row, '動態參數1') // 100,
                           app._mana_max(c.p, c.ses.inventario) * num(row, '動態參數2') // 100)
                else:
                    transfer = raw(child)
                    life = generation(target)
                    def bite():
                        if c.target_valid(target, life) and random.randint(1, 100) <= num(transfer, '動態參數1'):
                            c.debuff(target, num(transfer, '動態參數2'))
                    c.later(num(transfer, '持續時間'), bite)
    elif kind in ('slashes', 'earthsplit', 'skull'):
        if kind == 'slashes':
            for enemy in c.around(pos(c.ses), num(row, '範圍')):
                c.repeat(enemy, child, num(row, '動態參數2'))
        else:
            targets = c.around(center, num(row, '範圍'))
            if kind == 'earthsplit':
                start = pos(c.ses)
                dx, dy = center[0] - start[0], center[1] - start[1]
                length = max(1, math.hypot(dx, dy))
                targets = [enemy for enemy in targets
                           if ((pos(enemy)[0] - start[0]) * dx + (pos(enemy)[1] - start[1]) * dy) >= 0
                           and abs((pos(enemy)[0] - start[0]) * dy - (pos(enemy)[1] - start[1]) * dx) / length <= 1.5]
            for enemy in targets:
                c.repeat(enemy, c.mid, num(row, '連擊次數', 1))


def brand(c, target):
    row = raw(c.mid)
    mark, burst = num(row, '動態參數1'), num(row, '動態參數2')
    marks = c.effects(target)
    current = marks.get(mark)
    if current and current.get('fin', 0) > time.time():
        current['tw_bomb_active'] = False
        marks.pop(mark, None)
        c.emit(struct.pack('<HIBBII', 0x1d, c.eid(target), 1, 4, mark, 0))
        for enemy in c.around(pos(target), num(raw(burst), '範圍')):
            c.damage(enemy, burst)
        return
    hit = num(row, '狀態參數')
    targets = c.around(pos(target), num(raw(hit), '範圍')) if num(raw(hit), '範圍') else [target]
    for enemy in targets:
        c.damage(enemy, hit)
        if c.target_valid(enemy):
            entry = c.debuff(enemy, mark)
            # La bomba de mana explota al terminar aun sin un segundo uso.
            if num(raw(mark), '公式') == 22 and entry:
                entry['tw_bomb_active'] = True
                life = generation(enemy)
                def detonate(enemy=enemy, entry=entry, life=life):
                    active = c.effects(enemy).get(mark)
                    expired = active is None and time.time() >= entry['fin']
                    if (c.target_valid(enemy, life) and entry.get('tw_bomb_active')
                            and (active is entry or expired)):
                        entry['tw_bomb_active'] = False
                        c.effects(enemy).pop(mark, None)
                        c.visual(burst, enemy)
                        c.visual(burst, enemy, close=True)
                        for victim in c.around(pos(enemy), num(raw(burst), '範圍')):
                            c.damage(victim, burst)
                c.later(num(raw(mark), '持續時間'), detonate)


def lanzar(ses, mid, objetivo=0, tx=0, ty=0, addr='TW'):
    import app, presencia, transitable
    kind = linea(mid)
    p = getattr(ses, 'personaje', None)
    if (not kind or not p or not alive(ses) or getattr(ses, 'mapa_cargando', False)
            or getattr(ses, 'desconectado', False) or getattr(ses, 'puesto', None)
            or getattr(ses, '_tw_cast', None)):
        return False
    c = Lanzamiento(ses, mid, addr)
    if inmovilizado(ses) and kind in ('rift', 'charge', 'rescue', 'retreat'):
        return False
    row = raw(mid)
    target, center = None, pos(ses)
    companions = summons(ses)
    offensive = kind not in ('heal', 'rescue', 'rockskin', 'command')
    if offensive and __import__('daily_events').basic_only(p.stage):
        return False
    if kind in ('heal', 'rescue'):
        target = friendly(c, objetivo, rescue=kind == 'rescue')
        if not target:
            return False
        center = pos(target)
    elif kind in ('command', 'burst'):
        if not companions:
            return False
    elif kind in ('rift', 'earthsplit'):
        center = int(tx), int(ty)
        if not landing(ses, center) or center == (0, 0):
            return False
    elif kind not in ('sword', 'slashes', 'rockskin'):
        target = (getattr(ses, 'monstruos', None) or {}).get(objetivo)
        if target is None:
            target = presencia.sesion_por_entidad(ses, objetivo)
        if target is None and not objetivo:
            candidates = c.around(pos(ses), num(row, '射程', 1))
            target = min(candidates, key=lambda enemy: distance(pos(ses), pos(enemy))) if candidates else None
        if target is None or not c.enemy(target):
            return False
        center = pos(target)
    if target is not None or kind in ('rift', 'earthsplit'):
        if distance(pos(ses), center) > num(row, '射程', 1):
            return False
        if not transitable.linea_libre(p.stage, pos(ses), center):
            return False
    now = time.time()
    group = tuple(cb.grupo_de(mid))
    uses = getattr(ses, 'ultimo_uso', None) or {}
    if any(now - uses.get(member, 0) < c.mag['cd_ms'] / 1000 for member in group):
        return False
    mp, sp = c.mag['mp'], c.mag.get('cost_sp', 0)
    if p.mp < mp or getattr(ses, 'sp', 0) < sp:
        return False
    if app._sigilo_activo(ses, now) and offensive:
        app._romper_sigilo(ses, addr, 'por atacar con ' + c.mag['nombre'])
    p.mp -= mp
    ses.sp = getattr(ses, 'sp', 0) - sp
    p.sp = ses.sp
    ses.ultimo_uso = uses
    for member in group:
        uses[member] = now
    if getattr(ses, 'sentado', False):
        ses.sentado = False
        c.emit(struct.pack('<HIII', 0xa, p.entity_id, 0, 0))
    app._dar_sp(ses, p.entity_id, c.mag, addr)
    base_cast = num(row, '前置時間')
    cast = cb.calcular_cast_time(base_cast, p.buffs, p.habilidades, c.magic) if base_cast else 0
    visual_target = target if target is not None else (ses if kind in ('sword', 'slashes', 'command', 'rockskin') else None)
    visual_center = center if visual_target is None else None
    visual_mid = mid
    if kind in ('knife', 'brand'):
        existing = c.effects(target).get(num(row, '動態參數1'))
        visual_mid = num(row, '動態參數2') if existing and existing.get('fin', 0) > now else num(row, '狀態參數')
    ses.enviar(cb.confirmar_cast(c.eid(visual_target) if visual_target is not None else 0, *center),
               cb.atributo(p.entity_id, p.mp, cb.KIND_MP), cb.atributo(p.entity_id, ses.sp, cb.KIND_SP),
               *(struct.pack('<HIBBII', 0x1d, p.entity_id, 1, 3, member, c.mag['cd_ms']) for member in group),
               cb.gcd_paquete())
    c.visual(visual_mid, visual_target, visual_center, cast)
    if not c.magic and raw(visual_mid).get('施展動作') == '攻擊動作':
        attack_type, animation = cb.golpe_de_arma((ses.inventario or {}).get(3, 0),
                                                duales=app.lleva_duales_ses(ses))
        c.emit(cb.ataque(p.entity_id, c.eid(target) if target is not None else 0,
                         animation, attack_type))
    token = object()
    ses._tw_cast = token
    target_life = generation(target) if target is not None else None
    def finish():
        if getattr(ses, '_tw_cast', None) is not token:
            return
        ses._tw_cast = None
        if not c.valid() or (target is not None and not c.target_valid(target, target_life)):
            return
        c.visual(visual_mid, visual_target, visual_center, close=True)
        def impact():
            if target is not None and not c.target_valid(target, target_life):
                return
            execute(c, kind, target, center, companions)
            ses.enviar_inmediato(*app._otorgar_skill_exp(ses, p, p.entity_id, magic_id=mid))
            c.save()
            log.info('[%s] TW %s (%d) ejecutada', addr, c.mag['nombre'], mid)
        hit_delay = num(raw(visual_mid), '命中時間') / 1000
        if hit_delay:
            c.later(hit_delay, impact)
        else:
            impact()
    if cast:
        asyncio.get_event_loop().call_later(cast / 1000, cb.con_atacante(ses, finish))
    else:
        finish()
    def ready():
        if ses.personaje is p and not getattr(ses, 'desconectado', False) and uses.get(mid) == now:
            ses.enviar_inmediato(*(struct.pack('<HIBBII', 0x1d, p.entity_id, 1, 3, member, 0) for member in group))
    asyncio.get_event_loop().call_later(c.mag['cd_ms'] / 1000, ready)
    c.save()
    return True
