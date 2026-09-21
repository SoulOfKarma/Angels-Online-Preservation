"""
Servidor Angels Online -- capa de transporte.

Estado: el TRANSPORTE funciona y esta validado contra capturas reales.
La LOGICA DE JUEGO no existe todavia (ver docs/05_SERVIDOR.md).

Uso:
    python server/app.py [--host 127.0.0.1] [--port 16768]
"""
import asyncio
import argparse
import logging
import random
import sys
import pathlib
import collections
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'proto'))

from session import Session
from login import Personaje, secuencia
from grabador import Grabador
import cuentas
import login_server
from codec import Msg
import messages  # noqa
import struct

log = logging.getLogger('app')

# Angel Raphael. Es el unico NPC tras cuyo dialogo el servidor real manda el
# atributo que habilita la eleccion de clase.
ENTIDAD_MAESTRO_CLASE = 19
MAPA_DEL_TUTORIAL = 51      # los entity_id del tutorial solo valen aqui


def _nombre_entidad(ses, entity_id: int) -> str:
    """El nombre del NPC del mapa, para buscarle su dialogo."""
    totems_lyceum = {
        41: 'Aurora Totem', 150: 'Aurora Totem',
        43: 'Iron Totem', 121: 'Iron Totem',
        44: 'Dark City Totem', 122: 'Dark City Totem',
        45: 'Breeze Totem', 120: 'Breeze Totem',
    }
    if entity_id in totems_lyceum:
        return totems_lyceum[entity_id]
    import json
    f = pathlib.Path(__file__).parent / 'plantillas' / 'lyceum.json'
    if f.exists():
        for e in json.loads(f.read_text(encoding='utf-8'))['spawns']:
            if e['entity_id'] == entity_id:
                return e['nombre']
    # Si es un NPC de quest de los xmls (entity_id >= 900)
    f_mapas = pathlib.Path(__file__).parent / 'plantillas' / 'npc_por_mapa.json'
    if f_mapas.exists() and entity_id >= 900 and getattr(ses, 'personaje', None):
        d_mapas = json.loads(f_mapas.read_text(encoding='utf-8')).get('mapas', {})
        st_npcs = d_mapas.get(str(ses.personaje.stage), [])
        idx = entity_id - 900
        if 0 <= idx < len(st_npcs):
            return st_npcs[idx].get('nombre', '')
    return ''


def _monstruos_de(stage: int):
    """Los monstruos vivos del mapa, por entity_id."""
    import json
    import combate
    import login as _lg
    if stage in _lg.PLAYGROUND_MONSTERS:
        return {eid: combate.Monstruo(eid, ntype, nom, tile)
                for eid, ntype, nom, tile in _lg.PLAYGROUND_MONSTERS[stage]}
    f = pathlib.Path(__file__).parent / 'plantillas' / 'lyceum.json'
    if stage != 41 or not f.exists():
        return {}
    d = json.loads(f.read_text(encoding='utf-8'))
    return {e['entity_id']: combate.Monstruo(e['entity_id'], e['npc_type'],
                                             e['nombre'], e['tile'])
            for e in d['spawns'] if e.get('monstruo')}


def _precio_item(item_id: int) -> int:
    """Precio de compra, de la columna price de item.xml."""
    import sqlite3
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    try:
        r = sqlite3.connect(db).execute(
            'select price from item where id=?', (str(item_id),)).fetchone()
        return int(float(r[0])) if r and r[0] else 0
    except Exception:
        return 0


def _ranura_libre(bolsa, desde=20):
    """Primera casilla vacia de la mochila."""
    r = desde
    while r in bolsa:
        r += 1
    return r


def _final_tutorial(ses, addr):
    """Ultimo paso: entrega el set y las cajas, y manda al Angel Lyceum."""
    import clases
    import inventario as inv
    bolsa = getattr(ses, 'inventario', None)
    if bolsa is None or not ses.personaje.habilidades:
        return
    cid = ses.personaje.char_id
    ids = [h[0] for h in ses.personaje.habilidades]
    for ranura, item_id in clases.premio_final(ids):
        if ranura in bolsa:
            ranura = _ranura_libre(bolsa)
        bolsa[ranura] = item_id
        ses.enviar(clases.aviso(_nombre_item(item_id), tipo=0,
                                msg_id=clases.MSG_ITEM))
        ses.enviar(*inv.entregar(cid, item_id, ranura))
    ses.enviar(inv.stats(bolsa))
    # Y al Lyceum.
    ses.personaje.stage = clases.STAGE_LYCEUM
    ses.personaje.tile_x, ses.personaje.tile_y = clases.TILE_LYCEUM
    ses.monstruos = _monstruos_de(clases.STAGE_LYCEUM)
    ses.enviar(clases.cambiar_mapa(clases.STAGE_LYCEUM))
    if getattr(ses, 'usuario', None):
        cuentas.guardar_inventario(ses.usuario, cid, bolsa)
        cuentas.guardar_mapa(ses.usuario, cid, clases.STAGE_LYCEUM,
                             *clases.TILE_LYCEUM)
    log.info(f"[{addr}] tutorial terminado: set completo, "
             f"{len(clases.cajas_de(ids)) + 1} cajas y al Angel Lyceum")


def _premio(srv, ses, addr, etapa):
    """Entrega lo que da ese tramo del tutorial: items y oro."""
    import clases
    import inventario as inv
    r = clases.RECOMPENSAS.get(etapa)
    if not r or getattr(ses, 'inventario', None) is None:
        return
    cid = ses.personaje.char_id
    nuevos = False
    for ranura, item_id in r['items']:
        if ranura not in ses.inventario:
            ses.inventario[ranura] = item_id
            ses.enviar(clases.aviso(_nombre_item(item_id), tipo=0,
                                    msg_id=clases.MSG_ITEM))
            ses.enviar(*inv.entregar(cid, item_id, ranura))
            nuevos = True
    if r['oro']:
        ses.oro = getattr(ses, 'oro', 0) + r['oro']
        if ses.personaje:
            ses.personaje.oro = ses.oro
        nuevos = True
        log.info(f"[{addr}] tutorial: +{r['oro']} de oro (total {ses.oro})")
    if nuevos:
        # El oro si necesita el inventario entero: su cantidad vive en la
        # entrada de la ranura 0 y no hay un mensaje de "cambio de oro"
        # identificado.
        if r['oro']:
            ses.enviar(inv.completo(cid, _con_oro(ses)))
        if getattr(ses, 'usuario', None):
            cuentas.guardar_inventario(ses.usuario, cid, ses.inventario)
        log.info(f"[{addr}] tutorial: entregado el premio de la etapa {etapa}")


def _con_oro(ses):
    """El inventario con la cantidad de oro en su ranura."""
    import inventario as inv
    out = []
    for ranura, item_id in ses.inventario.items():
        r = int(ranura)
        if r == inv.RANURA_ORO:
            out.append((r, int(item_id), getattr(ses, 'oro', 0)))
        else:
            out.append((r, int(item_id), 1))
    return out


def _nombre_item(item_id: int) -> str:
    """Nombre del item para el cartel de 'obtuviste X'."""
    if item_id == 10:
        return "FreshmanSabre"
    import sqlite3
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    try:
        con = sqlite3.connect(db)
        r = con.execute('select "基本名稱" from item where id=?',
                        (str(item_id),)).fetchone()
        return r[0] if r and r[0] else f'Item{item_id}'
    except Exception:
        return f'Item{item_id}'


def _max_sp_info(p):
    """Devuelve (barras_sp, max_puntos_sp). Por defecto 2 barras (2000 puntos).
    La habilidad pasiva Reserve (15) otorga +1 barra cada 25 niveles."""
    res_rank = 1
    if p and getattr(p, 'habilidades', None):
        for h in p.habilidades:
            sid = h[0] if isinstance(h, (list, tuple)) else h
            if sid == 15:
                res_rank = h[1] if isinstance(h, (list, tuple)) and len(h) > 1 else 1
                break
    bars = 2 + (res_rank // 25)
    return bars, bars * 1000


def _stats_ses(ses):
    """Genera el paquete 0x0042 con stats completos del personaje."""
    import inventario as inv
    p = getattr(ses, 'personaje', None)
    habs = p.habilidades if p else None
    hp = p.hp if p else None
    hp_max = p.hp_max if p else None
    mp = p.mp if p else None
    mp_max = p.mp_max if p else None
    oro = getattr(ses, 'oro', 0)
    buffs = getattr(p, 'buffs', None)
    bars, max_pts = _max_sp_info(p)
    sp = getattr(ses, 'sp', None)
    bolsa = getattr(ses, 'inventario', None)
    return inv.stats(bolsa, habs, hp=hp, hp_max=hp_max, mp=mp, mp_max=mp_max, oro=oro, buffs=buffs, sp=sp, sp_max=bars)


def _otorgar_skill_exp(ses, p, yo, arma_puesta=0, magic_id=0):
    """Otorga Skill EXP en cada impacto de ataque o uso de habilidad activa (buff/cura/spell)."""
    if not p or not getattr(p, 'habilidades', None):
        return []
    import configuracion, cuentas, clases as _cl, combate as _cb, inventario as _iv
    pkgs = []
    mult = configuracion.multiplicador_skill_exp()
    exp_ganada = max(1, int(round(2 * mult)))

    SKILLS_PRODUCTOR = {20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31}

    skill_arma = None
    if arma_puesta:
        for sid, itid in _cl.ARMA_POR_SKILL.items():
            if itid == arma_puesta:
                skill_arma = sid
                break

    nuevas_habs = []
    subio_alguna = False
    exp_otorgada = False
    for h in p.habilidades:
        sid, slv, sexp = h[0], h[1], h[2]
        aplica = False
        if magic_id:
            # Si se uso una habilidad magica/hechizo, avanza su rama correspondiente
            rama = _cl.RAMA_POR_SKILL.get(sid)
            if rama or sid in {1, 2, 3, 4, 9, 10, 11, 17, 32}:
                aplica = True
        else:
            # Ataque fisico: avanza la habilidad del arma en mano o la habilidad principal de ataque
            if skill_arma and sid == skill_arma:
                aplica = True
            elif not skill_arma and sid in (1, 9, 10, 11, 17, 32):
                aplica = True

        if aplica and not exp_otorgada:
            sexp += exp_ganada
            exp_otorgada = True
            sid_ganador = sid
            max_lv = (p.nivel + 11) if sid in SKILLS_PRODUCTOR else p.nivel
            req = max(1, slv * 100)
            while sexp >= req and slv < max_lv:
                sexp -= req
                slv += 1
                req = max(1, slv * 100)
                subio_alguna = True
                pkgs.append(_cl.aviso(f"The level of the spell {_cl.nombre(sid)} has been upgraded.", tipo=0, msg_id=_cl.MSG_ITEM))
            if slv >= max_lv:
                sexp = min(sexp, req)
            pct_exp = min(100, int(round(100.0 * sexp / req)))

        nuevas_habs.append((sid, slv, sexp))

    p.habilidades = nuevas_habs
    if exp_otorgada:
        # 0x000B kind=4 con val=sid: muestra en chat y pantalla '[Skill] has obtained 1 Exp.'
        pkgs.append(struct.pack('<HIBIH', 0x000B, yo, 4, sid_ganador, 0))
        # 0x001D kind=53 (0x35): actualiza la barra porcentual de la habilidad en la UI
        pkgs.append(struct.pack('<HIBBII', 0x001D, yo, 1, 53, sid_ganador, pct_exp))
    if subio_alguna:
        pkgs.append(_cl.arbol(p.habilidades))
        pkgs.append(_stats_ses(ses))

    if getattr(ses, 'usuario', None):
        cuentas.guardar_progreso(ses.usuario, p.char_id, p.nivel, p.exp,
                                 p.hp, p.mp, p.habilidades,
                                 hp_max=p.hp_max, mp_max=p.mp_max)
    return pkgs


class Servidor:
    def __init__(self, host, port, fport=21238, wport=None):
        self.host, self.port, self.fport = host, port, fport
        # puerto del servidor de MUNDO, al que se redirige tras el login
        self.wport = wport or (port + 1)
        self.desconocidos = collections.Counter()
        self.sesiones = 0
        # Traspaso login -> mundo. Son dos conexiones TCP distintas: cuando
        # el cliente pide entrar (0x0006) anotamos aca que personaje eligio,
        # y la conexion de mundo que llega despues lo levanta. Se indexa por
        # IP porque el puerto de origen cambia entre las dos conexiones.
        self.pendientes = {}

    async def _patrulla_lyceum(self, ses):
        """Mueve a los House Pickets periodicamente para que patrullen el Angel Lyceum,
        y gestiona el respawn de monstruos y movimiento de la mascota."""
        rutas = [
            (5, [(94, 55), (94, 61)]),
            (6, [(123, 53), (128, 53)]),
            (7, [(145, 81), (150, 81)]),
            (12, [(145, 71), (145, 77)]),
            (16, [(217, 75), (211, 75)]),
        ]
        estado = {eid: 0 for eid, _ in rutas}
        MOVE = Msg.registry[(0x0005, 's2c', '*')]
        try:
            while True:
                await asyncio.sleep(5)
                if not getattr(ses, 'personaje', None):
                    continue

                # 1. Patrulla de House Pickets en Angel Lyceum
                if ses.personaje.stage == 41:
                    for eid, pts in rutas:
                        idx = estado[eid]
                        nxt = 1 - idx
                        cur_t = pts[idx]
                        dst_t = pts[nxt]
                        estado[eid] = nxt
                        msg = MOVE.build(
                            entity_id=eid,
                            cur_x=cur_t[0] * 32,
                            cur_y=cur_t[1] * 32,
                            dst_x=dst_t[0] * 32,
                            dst_y=dst_t[1] * 32,
                            speed=50
                        )
                        ses.enviar(msg)

                # 2. Respawn de monstruos caidos
                monstruos = getattr(ses, 'monstruos', {})
                import login as _lg
                for mid, m in list(monstruos.items()):
                    if m.toca_reaparecer():
                        m.revivir()
                        ses.enviar(_lg._npc_spawn(m.entity_id, m.npc_type, m.nombre, m.spawn_tile, klass=1))
                        log.info(f"monstruo {m.nombre} (eid={m.entity_id}) reaparecio en {m.spawn_tile}")

                # 3. Seguimiento de mascota al jugador
                pet_id = getattr(ses, 'pet_entity_id', None)
                if pet_id and ses.personaje:
                    px, py = ses.personaje.tile_x, ses.personaje.tile_y
                    msg_pet = MOVE.build(
                        entity_id=pet_id,
                        cur_x=(px + 1) * 32,
                        cur_y=py * 32,
                        dst_x=px * 32,
                        dst_y=py * 32,
                        speed=100
                    )
                    ses.enviar(msg_pet)

                out = ses.drenar()
                if out and getattr(ses, 'writer', None):
                    try:
                        if getattr(ses, 'grab', None):
                            ses.grab.salida(out)
                        ses.writer.write(out)
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.debug(f"patrulla lyceum detenida: {e}")

    async def _bucle_regeneracion(self, ses):
        """Regeneracion pasiva de HP y MP:
        - Sentado (tecla Insert): cada 1 segundo recupera +6 MP y +12 HP.
        - Quieto de pie (al menos 2s quieto y sin combate): cada 2 segundos recupera +6 MP y +6 HP.
        """
        import combate as _cb
        try:
            while getattr(ses, 'conectado', True):
                await asyncio.sleep(1.0)
                p = getattr(ses, 'personaje', None)
                if not p:
                    continue

                yo = p.entity_id
                sentado = getattr(ses, 'sentado', False)
                ahora = time.time()
                ultimo_mov = getattr(ses, 'ultimo_movimiento', 0)
                ultimo_comb = getattr(ses, 'ultimo_combate', 0)
                en_combate = (ahora - ultimo_comb) < 4.0

                toca_regen = False
                if sentado:
                    toca_regen = True
                    rec_mp = 6
                    rec_hp = 12
                else:
                    if (ahora - ultimo_mov) >= 2.0 and not en_combate:
                        ultimo_tick = getattr(ses, 'ultimo_regen_tick', 0)
                        if (ahora - ultimo_tick) >= 2.0:
                            toca_regen = True
                            ses.ultimo_regen_tick = ahora
                            rec_mp = 6
                            rec_hp = 6

                if toca_regen:
                    pkgs = []
                    if p.mp < p.mp_max:
                        p.mp = min(p.mp_max, p.mp + rec_mp)
                        pkgs.append(_cb.atributo(yo, p.mp, _cb.KIND_MP))
                    if p.hp < p.hp_max:
                        p.hp = min(p.hp_max, p.hp + rec_hp)
                        pkgs.append(_cb.atributo(yo, p.hp, _cb.KIND_HP))

                    if pkgs:
                        ses.enviar_inmediato(*pkgs)
                        if getattr(ses, 'usuario', None):
                            cuentas.guardar_progreso(ses.usuario, p.char_id, p.nivel, p.exp,
                                                     p.hp, p.mp, p.habilidades,
                                                     hp_max=p.hp_max, mp_max=p.mp_max)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.debug(f"bucle de regeneracion detenido: {e}")

    async def cliente(self, reader, writer, rol='mundo'):
        addr = writer.get_extra_info('peername')
        self.sesiones += 1
        ses = Session(addr)
        ses.rol = rol
        ses.puerto = self.port if rol == 'login' else self.wport
        ses.writer = writer
        grab = Grabador(addr, self.port if rol == 'login' else self.wport, ses.key)
        ses.grab = grab
        ses.patrulla_task = asyncio.create_task(self._patrulla_lyceum(ses)) if rol == 'mundo' else None
        ses.regen_task = asyncio.create_task(self._bucle_regeneracion(ses)) if rol == 'mundo' else None
        log.info(f"[{addr}] conectado ({rol})  clave={ses.key.hex(' ')}")
        log.info(f"[{addr}] grabando sesion -> logs/sesiones/{ses.grab.base}_*.bin")
        ses.enviar_hello()
        primero = ses.drenar()
        ses.grab.salida(primero)
        writer.write(primero)
        await writer.drain()
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                grab.entrada(data)
                for opcode, cuerpo in ses.alimentar(data):
                    ses.vistos[opcode] += 1
                    m, d = ses.parsear(opcode, cuerpo)
                    if m is None:
                        self.desconocidos[opcode] += 1
                        log.debug(f"[{addr}] 0x{opcode:04X} sin esquema "
                                  f"({len(cuerpo)}B): {cuerpo[:24].hex(' ')}")
                    else:
                        log.debug(f"[{addr}] {m.name} {d if d else '(no parsea)'}")
                    # el dispatcher corre igual: un opcode sin esquema puede
                    # necesitar respuesta (la autenticacion es el caso tipico)
                    self.manejar(ses, opcode, m, d, addr, cuerpo)
                salida = ses.drenar()
                if salida:
                    grab.salida(salida)
                    writer.write(salida)
                    await writer.drain()

        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            if getattr(ses, 'patrulla_task', None):
                ses.patrulla_task.cancel()
            if getattr(ses, 'regen_task', None):
                ses.regen_task.cancel()
            # Guardar donde quedo el personaje, para que al volver a entrar
            # aparezca ahi y no en el punto de aparicion.
            if getattr(ses, 'personaje', None) and getattr(ses, 'usuario', None):
                try:
                    cuentas.guardar_posicion(ses.usuario, ses.personaje.char_id,
                                             ses.personaje.tile_x,
                                             ses.personaje.tile_y)
                    log.info(f"[{addr}] posicion guardada: "
                             f"({ses.personaje.tile_x},{ses.personaje.tile_y})")
                except Exception as e:
                    log.warning(f"[{addr}] no se pudo guardar la posicion: {e}")
            base, nc, ns = grab.cerrar()
            log.info(f"[{addr}] desconectado. opcodes vistos: "
                     f"{dict(ses.vistos.most_common(8))}")
            log.info(f"[{addr}] sesion grabada: {nc} B del cliente, "
                     f"{ns} B del servidor -> logs/sesiones/{base}_*.bin")
            if self.desconocidos:
                log.warning(f"[{addr}] opcodes SIN ESQUEMA que mando el cliente: "
                            f"{ {f'0x{k:04X}': v for k, v in self.desconocidos.items()} }")
            writer.close()

    def manejar(self, ses, opcode, m, d, addr, cuerpo=b''):
        """Login: responde MOTD + personajes + redirect. Mundo: entra al juego."""
        if opcode == 0x0002 and ses.rol == 'login':
            usuario = login_server.usuario_de_auth(cuerpo)
            ses.usuario = usuario
            cuentas.guardar_muestra_auth(cuerpo, f"usuario='{usuario}' desde {addr}")
            cuenta, motivo = cuentas.validar(usuario, cuerpo)
            if cuenta is None:
                log.warning(f"[{addr}] LOGIN RECHAZADO usuario='{usuario}': {motivo}")
                ses.enviar_crudo(login_server.respuesta_error())
                return
            log.info(f"[{addr}] LOGIN usuario='{usuario}' aceptado ({motivo})")
            # Solo lo que este guardado de verdad. Nada inventado.
            lista = list(cuenta.get('personajes', []))[:3]
            import os as _o
            # Ajustables para bisecar: los tres unicos campos que todavia
            # difieren del bloque real (ranuras=1, subcanal=3, clase=5).
            _ran = int(_o.environ.get('AO_RANURAS', 3))
            _sub = int(_o.environ.get('AO_SUBCANAL', 2))
            _cls = _o.environ.get('AO_CLASE')
            # El cliente se CONGELA sin intentar ninguna conexion, asi que el
            # bloqueo es local -- muy probablemente la carga del mapa. Con
            # AO_MAPA se puede probar otro stage_id sin recrear el personaje.
            _mapa = _o.environ.get('AO_MAPA')
            if _mapa is not None:
                for _p in lista:
                    _p['stage_id'] = int(_mapa)
            if _cls is not None:
                for _p in lista:
                    _p['class_id'] = int(_cls)
            if _o.environ.get('AO_BLOQUE_REAL'):
                # Manda el bloque de cuenta CAPTURADO tal cual, sin generar
                # nada. Si con los bytes literales de un servidor que
                # funcionaba el cliente tampoco entra, el bloque queda
                # descartado de forma concluyente.
                import struct as _s
                _b = (pathlib.Path(__file__).parent / 'plantillas'
                      / 'login_bloque_real.bin').read_bytes()
                ses.enviar_crudo(_s.pack('<HH', len(_b) + 2, 0x0000) + _b)
                log.warning(f"[{addr}] usando el BLOQUE REAL capturado "
                            f"({len(_b)} B), no el generado")
            else:
                ses.enviar_crudo(login_server.respuesta_login(
                    lista, cuenta=usuario, ranuras=_ran, subcanal=_sub))
            log.info(f"[{addr}] ranuras={_ran} subcanal={_sub} "
                     f"clase={_cls or 'la del pj'} mapa={_mapa or 'el del pj'}")
            log.info(f"[{addr}] ranuras: {len(lista)} con personaje, "
                     f"{3 - len(lista)} libres")
            import os as _os
            # Diagnostico: con AO_REDIRECT_AL_LOGIN=1 el redirect apunta al
            # MISMO puerto del login. Si aparece una SEGUNDA conexion, el
            # cliente si actua sobre el redirect y el problema esta en la
            # sesion de mundo. Si no aparece, lo esta ignorando.
            # El redirect NO va aca. Se manda como respuesta a 0x0006, que es
            # el pedido de ENTRAR AL MUNDO. Mandarlo apenas llega el AUTH hace
            # que el cliente lo reciba antes de pedir entrar, lo descarte, y
            # despues quede esperando una respuesta que nunca llega -- que es
            # exactamente el congelamiento que veniamos persiguiendo.
            log.info(f"[{addr}] lista enviada; esperando 0x0006 para entrar")
            # NO cerrar la conexion de login aca. Se probo y el cliente
            # muestra "The connection with the server has been interrupted":
            # trata el cierre como caida. La nota del proyecto anterior sobre
            # "cerrar el socket de login" describia un cierre PREMATURO como
            # causa de aborto, no un cierre necesario. Mal interpretada.
            return

        if opcode == 0x0003 and ses.rol == 'login':
            import personajes, pathlib as _pl
            d = personajes.parsear_creacion(cuerpo)
            if not d['nombre']:
                log.warning(f"[{addr}] CREAR: nombre vacio, se ignora")
                return
            cta = cuentas.cargar()['cuentas'].get(ses.usuario) or {'personajes': []}
            usados = {x.get('char_id', 0) for x in cta.get('personajes', [])}
            nuevo = personajes.personaje_nuevo(
                d['nombre'], d['ranura'], max(usados or [1000]) + 1)
            personajes.guardar(ses.usuario, nuevo, cuentas.ARCHIVO)
            ses.enviar(personajes.respuesta_creacion(d['ranura'], nuevo))
            log.info(f"[{addr}] PERSONAJE CREADO '{nuevo['nombre']}' "
                     f"ranura={d['ranura']} id={nuevo['char_id']} "
                     f"nivel={nuevo['nivel']} mapa={nuevo['stage_id']} -> guardado")
            return

        if opcode == 0x0006 and ses.rol == 'login':
            # ENTRAR AL MUNDO. El cuerpo trae la ruta del sprite del personaje
            # elegido, por ejemplo "\chr\i263g\20263_Wait.spr".
            import os as _o2
            _pt = self.port if _o2.environ.get('AO_REDIRECT_AL_LOGIN') else self.wport
            ranura = cuerpo[0] if cuerpo else 0
            txt = bytes(c if 32 <= c < 127 else 46 for c in cuerpo[:40]).decode()
            cta = cuentas.cargar()['cuentas'].get(ses.usuario) or {}
            elegidos = list(cta.get('personajes', []))
            nombre = elegidos[ranura]['nombre'] if ranura < len(elegidos) else '?'
            self.pendientes[addr[0]] = (ses.usuario, ranura)
            log.info(f"[{addr}] ENTRAR AL MUNDO ranura={ranura} -> '{nombre}'")
            log.info(f"[{addr}] 0x0006 sprite: {txt}")
            ses.enviar(login_server.redirect(self.host, _pt))
            log.info(f"[{addr}] redirigido a {self.host}:{_pt}")
            return

        if opcode == 0x0002 and not ses.entity_id:
            # El cliente se autentico. Entra al mundo.
            # No se validan credenciales: el bloque de 16 B no esta descifrado.
            # Se guarda el AUTH crudo para poder deducir su formato despues.
            if d and d.get('credenciales'):
                cuentas.guardar_muestra_auth(d['credenciales'], f"desde {addr}")
            usuario, ranura = self.pendientes.get(addr[0], (None, 0))
            if usuario is None:
                log.warning(f"[{addr}] conexion de mundo sin 0x0006 previo; "
                            f"no se sabe que personaje cargar")
                return
            cuenta = cuentas.cargar()['cuentas'].get(usuario) or {}
            p = cuentas.personaje_de(cuenta, ranura)
            # La sesion de MUNDO es otra conexion TCP: no paso por el handler
            # de login, asi que no tiene ses.usuario. Sin esto, guardar el
            # inventario fallaba en silencio y todo volvia a su sitio al
            # reconectar.
            ses.usuario = usuario
            if p is None:
                log.warning(f"[{addr}] la ranura {ranura} de '{usuario}' "
                            f"esta vacia")
                return
            ses.entity_id = p.entity_id
            ses.personaje = p
            for sub in secuencia(p):
                ses.enviar(sub)
            # El inventario va dentro de la secuencia de entrada: el 0x001A
            # se arma con el del personaje, asi que cada item ya sale en su
            # ranura y no hay que corregir nada despues.
            import inventario as inv
            # La MISMA referencia, no una copia: con dict(p.inventario) se
            # trabajaba sobre una copia y al recargar el mapa la secuencia
            # volvia a leer p.inventario, que seguia sin los items entregados.
            # De ahi que los regalos solo aparecieran al reconectar.
            ses.inventario = p.inventario
            ses.oro = p.oro
            ses.monstruos = _monstruos_de(p.stage)
            bars, max_pts = _max_sp_info(p)
            ses.sp = getattr(ses, 'sp', None) or max_pts
            ses.enviar(inv.stats(ses.inventario, p.habilidades,
                                 hp=p.hp, hp_max=p.hp_max,
                                 mp=p.mp, mp_max=p.mp_max,
                                 oro=p.oro, sp=ses.sp, sp_max=bars))
            import combate as _cb
            ses.enviar(_cb.atributo(p.entity_id, ses.sp, _cb.KIND_SP))
            # El arbol de habilidades tambien al entrar, no solo al elegir
            # clase: si no, al reconectar el panel vuelve a salir lleno de
            # interrogantes.
            if p.habilidades:
                import clases as _cl
                ses.enviar(_cl.arbol(p.habilidades))
                _ids = [h[0] for h in p.habilidades]
                # Y los hechizos de F1..F3: el cliente no los recuerda entre sesiones,
                # por lo que se otorgan las ranuras (0x001D) sin spamear el chat con avisos.
                _hech = _cl.hechizos_iniciales(_ids)
                if _hech:
                    ses.enviar(_cl.otorgar_hechizos(
                        p.entity_id, [n for n, _ in _hech]))
            # Iniciar tarea asincrona de IA para que los monstruos paseen por el mapa y ataquen
            async def _ia_monstruos():
                import random, time
                import combate as _cb
                MOVE = Msg.registry[(0x0005, 's2c', '*')]
                try:
                    while getattr(ses, 'personaje', None):
                        await asyncio.sleep(1.2)
                        p = getattr(ses, 'personaje', None)
                        if not p or not getattr(ses, 'monstruos', None):
                            continue
                        ahora = time.time()
                        yo = p.entity_id

                        for m in list(ses.monstruos.values()):
                            if not getattr(m, 'vivo', True):
                                continue

                            dist_x = abs(m.tile_x - p.tile_x)
                            dist_y = abs(m.tile_y - p.tile_y)
                            dist = max(dist_x, dist_y)

                            # 1. Monstruo en combate con el jugador
                            if getattr(m, 'en_combate_con', None) == yo:
                                if dist > 18:
                                    m.en_combate_con = None
                                    continue

                                r_atk = max(1, getattr(m, 'atk_range', 1))
                                if dist <= r_atk:
                                    # Atacar al jugador si paso el cooldown (2.0s)
                                    if ahora - getattr(m, 'ultimo_ataque', 0) >= 2.0:
                                        m.ultimo_ataque = ahora
                                        suyo = m.pegar()
                                        p.hp = max(0, p.hp - suyo)
                                        pct_hp = max(0, min(100, round(100 * p.hp / p.hp_max)))
                                        ef_atk = m.proj_ef if m.proj_ef > 0 else 148
                                        ses.enviar(_cb.ataque(m.entity_id, yo, ef_atk),
                                                   _cb.numero_de_dano(m.entity_id, yo, suyo, ataque=656, efecto=ef_atk),
                                                   _cb.numero_flotante(yo, suyo),
                                                   _cb.atributo(yo, pct_hp, _cb.VIDA))
                                        if p.hp <= 0:
                                            import clases as _cl
                                            ses.enviar(_cl.aviso("You were defeated! Returning to safe haven...", tipo=0, msg_id=_cl.MSG_ITEM))
                                            p.hp = p.hp_max
                                            p.mp = p.mp_max
                                            rev_x = getattr(p, 'spawn_x', 138)
                                            rev_y = getattr(p, 'spawn_y', 60)
                                            p.tile_x, p.tile_y = rev_x, rev_y
                                            ses.enviar(struct.pack('<HIII', 0x0003, p.entity_id, rev_x, rev_y),
                                                       _cb.atributo(yo, p.hp, _cb.KIND_HP))
                                            m.en_combate_con = None
                                else:
                                    # Fuera de rango: avanzar hacia el jugador solo si NO es estatico (como Lily)
                                    if not getattr(m, 'es_estatico', False):
                                        step_x = 1 if p.tile_x > m.tile_x else (-1 if p.tile_x < m.tile_x else 0)
                                        step_y = 1 if p.tile_y > m.tile_y else (-1 if p.tile_y < m.tile_y else 0)
                                        cur_x, cur_y = m.tile_x * 32, m.tile_y * 32
                                        m.tile_x += step_x
                                        m.tile_y += step_y
                                        m.tile[0], m.tile[1] = m.tile_x, m.tile_y
                                        dst_x, dst_y = m.tile_x * 32, m.tile_y * 32
                                        ses.enviar(MOVE.build(entity_id=m.entity_id,
                                                              cur_x=cur_x, cur_y=cur_y,
                                                              dst_x=dst_x, dst_y=dst_y, speed=m.move_speed or 50))
                            else:
                                # 2. Monstruo libre: pasear aleatoriamente si no es estatico
                                if not getattr(m, 'es_estatico', False) and random.random() < 0.12:
                                    dx = random.choice([-1, 0, 1])
                                    dy = random.choice([-1, 0, 1])
                                    if dx == 0 and dy == 0:
                                        continue
                                    new_x = m.tile_x + dx
                                    new_y = m.tile_y + dy
                                    if abs(new_x - m.spawn_x) <= m.move_range and abs(new_y - m.spawn_y) <= m.move_range:
                                        cur_x, cur_y = m.tile_x * 32, m.tile_y * 32
                                        m.tile_x = new_x
                                        m.tile_y = new_y
                                        m.tile[0], m.tile[1] = new_x, new_y
                                        dst_x, dst_y = new_x * 32, new_y * 32
                                        ses.enviar(MOVE.build(entity_id=m.entity_id,
                                                              cur_x=cur_x, cur_y=cur_y,
                                                              dst_x=dst_x, dst_y=dst_y, speed=m.move_speed or 50))
                except Exception:
                    pass

            asyncio.create_task(_ia_monstruos())
            log.info(f"[{addr}] entro al mundo: '{p.nombre}' entidad={p.entity_id} "
                     f"char_id={p.char_id} tile=({p.tile_x},{p.tile_y})")
            log.info(f"[{addr}] (credenciales NO validadas: formato aun sin descifrar)")
            return

        # --- combate -----------------------------------------------------
        if opcode == 0x0006 and ses.rol == 'mundo' and cuerpo:
            import combate as _cb
            d3 = _cb.parsear_ataque(cuerpo)
            if not d3:
                return
            tipo, objetivo = d3
            yo = ses.entity_id or 1001

            bichos = getattr(ses, 'monstruos', None) or {}
            m = bichos.get(objetivo)
            arma_puesta = ses.inventario.get(3, 0) if ses.inventario else 0

            # Si se uso una habilidad de ataque sin objetivo fijado, auto-fijar el monstruo mas cercano
            if m is None and tipo != _cb.ATAQUE_NORMAL and ses.personaje:
                mag_check = _cb.datos_magia(tipo)
                if mag_check.get('es_ataque'):
                    r_max = max(2, mag_check.get('rango', 1))
                    cands = [b for b in bichos.values() if b.vivo and max(abs(b.tile_x - ses.personaje.tile_x), abs(b.tile_y - ses.personaje.tile_y)) <= r_max]
                    if cands:
                        m = min(cands, key=lambda b: max(abs(b.tile_x - ses.personaje.tile_x), abs(b.tile_y - ses.personaje.tile_y)))
                        objetivo = m.entity_id

            if m is None:
                # Habilidad activa sobre uno mismo (F1, F2, F3, buffs o curaciones)
                if tipo != _cb.ATAQUE_NORMAL or objetivo == yo:
                    mag = _cb.datos_magia(tipo)
                    # Si es una habilidad pasiva, ignorar (no se castea activamente en la barra)
                    if mag.get('es_pasiva'):
                        return
                    # Si es una habilidad de ataque, no se puede autocastear
                    if mag.get('es_ataque'):
                        return

                    # Si estaba sentado, levantarse antes de ejecutar habilidad
                    if getattr(ses, 'sentado', False):
                        ses.sentado = False
                        ses.enviar(struct.pack('<HIII', 0x000A, yo, 0, 0))

                    cost_sp = mag.get('cost_sp', 0)
                    if cost_sp > 0:
                        if getattr(ses, 'sp', 0) < cost_sp:
                            log.info(f"[{addr}] SP insuficiente ({getattr(ses, 'sp', 0)}/{cost_sp}) para habilidad {tipo}")
                            return
                        ses.sp -= cost_sp
                        ses.enviar(_cb.atributo(yo, ses.sp, _cb.KIND_SP))

                    mp_coste = mag.get('mp', 0)
                    if ses.personaje and mp_coste > 0:
                        if ses.personaje.mp < mp_coste:
                            log.info(f"[{addr}] MP insuficiente ({ses.personaje.mp}/{mp_coste}) para habilidad {tipo}")
                            return
                        ses.personaje.mp = max(0, ses.personaje.mp - mp_coste)

                    ef = _cb.efecto_de_ataque(tipo)
                    cd_ms = mag.get('cd_ms', 2000)
                    dur_ms = mag.get('dur_ms', 0)
                    cast_time = mag.get('cast_time', 100)
                    import clases as _cl
                    import inventario as _iv

                    # 1. Habilidad de curacion real (Cure Spell de mago, etc.)
                    if mag.get('es_cura') and ses.personaje:
                        cura = max(10, abs(mag.get('hp', 0)))
                        ses.personaje.hp = min(ses.personaje.hp_max, ses.personaje.hp + cura)
                        ses.enviar(_cb.efecto_curacion_inicio(yo, yo, cura, efecto=ef), _cb.gcd_paquete())
                        def _fin_cura():
                            if ses.personaje:
                                pkgs_fin = [
                                    _cb.efecto_curacion_fin(yo, yo, efecto=ef),
                                    _cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP),
                                    _cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP),
                                ]
                                if cd_ms > 0:
                                    pkgs_fin.append(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, cd_ms))
                                    asyncio.get_event_loop().call_later(cd_ms / 1000.0, lambda: ses.enviar_inmediato(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, 0)))
                                pkgs_fin.extend(_otorgar_skill_exp(ses, ses.personaje, yo, magic_id=tipo))
                                ses.enviar_inmediato(*pkgs_fin)
                                if getattr(ses, 'usuario', None):
                                    cuentas.guardar_progreso(ses.usuario, ses.personaje.char_id,
                                                             ses.personaje.nivel, ses.personaje.exp,
                                                             ses.personaje.hp, ses.personaje.mp,
                                                             ses.personaje.habilidades,
                                                             hp_max=ses.personaje.hp_max, mp_max=ses.personaje.mp_max)
                        asyncio.get_event_loop().call_later(max(0.1, cast_time / 1000.0), _fin_cura)
                        log.info(f"[{addr}] habilidad curativa {tipo} curó {cura} HP ({ses.personaje.hp}/{ses.personaje.hp_max})")
                    else:
                        # 2. Buff activo / habilidad sobre si mismo (Ferocious Song, Fighting Shield, Swiftness Song, Injury Cure)
                        ses.enviar(_cb.efecto_magia_self_inicio(yo, ef, tipo, cast_time=cast_time), _cb.gcd_paquete())

                        # Registrar buff en el personaje (duracion, bono de critico, % mitigacion de dano)
                        if ses.personaje:
                            if not hasattr(ses.personaje, 'buffs') or ses.personaje.buffs is None:
                                ses.personaje.buffs = {}
                            buff_dur_s = (dur_ms / 1000.0) if dur_ms > 0 else 300.0
                            buff_entry = {
                                'fin': time.time() + buff_dur_s,
                                'mag': mag
                            }
                            if mag.get('crit_rate'):
                                buff_entry['crit'] = mag.get('crit_rate')
                            if mag.get('phys_mit'):
                                buff_entry['mit'] = mag.get('phys_mit')
                            if mag.get('mag_mit'):
                                buff_entry['mag_mit'] = mag.get('mag_mit')
                            ses.personaje.buffs[tipo] = buff_entry

                        def _fin_buff():
                            if ses.personaje:
                                pkgs_fin = [
                                    _cb.efecto_magia_self_fin(yo, ef, tipo),
                                    _cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP),
                                ]
                                if dur_ms > 0:
                                    pkgs_fin.append(struct.pack('<HIBBII', 0x001D, yo, 1, 4, tipo, dur_ms))
                                    def _expirar_buff(sk_id=tipo):
                                        if ses.personaje and getattr(ses.personaje, 'buffs', None):
                                            ses.personaje.buffs.pop(sk_id, None)
                                            ses.enviar_inmediato(
                                                struct.pack('<HIBBII', 0x001D, yo, 1, 4, sk_id, 0),
                                                _stats_ses(ses)
                                            )
                                    asyncio.get_event_loop().call_later(dur_ms / 1000.0, _expirar_buff)

                                if cd_ms > 0:
                                    pkgs_fin.append(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, cd_ms))
                                    asyncio.get_event_loop().call_later(cd_ms / 1000.0, lambda: ses.enviar_inmediato(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, 0)))

                                pkgs_fin.append(_stats_ses(ses))
                                pkgs_fin.extend(_otorgar_skill_exp(ses, ses.personaje, yo, magic_id=tipo))
                                ses.enviar_inmediato(*pkgs_fin)
                                if getattr(ses, 'usuario', None):
                                    cuentas.guardar_progreso(ses.usuario, ses.personaje.char_id,
                                                             ses.personaje.nivel, ses.personaje.exp,
                                                             ses.personaje.hp, ses.personaje.mp,
                                                             ses.personaje.habilidades,
                                                             hp_max=ses.personaje.hp_max, mp_max=ses.personaje.mp_max)

                        asyncio.get_event_loop().call_later(max(0.1, cast_time / 1000.0), _fin_buff)
                        log.info(f"[{addr}] habilidad buff {tipo} ejecutada ({mag.get('nombre')}) [cd={cd_ms}ms, dur={dur_ms}ms]")
                    return
                log.debug(f"[{addr}] ataque a la entidad {objetivo}: no es un monstruo conocido")
                return

            if not m.vivo:
                return

            # El dano sale del ataque del jugador mas bonos pasivos menos defensa del bicho
            import inventario as _iv
            habs = ses.personaje.habilidades if ses.personaje else None
            buffs_activos = getattr(ses.personaje, 'buffs', None)
            st = _iv.stats(ses.inventario, habs, buffs=buffs_activos)
            ataque = struct.unpack_from('<I', st, 2 + 20 + 4)[0]

            # Si se usa una habilidad activa (ej. Slicing Hit, Basic Beating, etc.)
            dano_extra = 0
            if tipo != _cb.ATAQUE_NORMAL:
                mag = _cb.datos_magia(tipo)
                cost_sp = mag.get('cost_sp', 0)
                if cost_sp > 0:
                    if getattr(ses, 'sp', 0) < cost_sp:
                        log.info(f"[{addr}] SP insuficiente ({getattr(ses, 'sp', 0)}/{cost_sp}) para habilidad {tipo}")
                        return
                    ses.sp -= cost_sp
                    ses.enviar(_cb.atributo(yo, ses.sp, _cb.KIND_SP))

                mp_coste = mag.get('mp', 0)
                if ses.personaje and mp_coste > 0:
                    if ses.personaje.mp < mp_coste:
                        log.info(f"[{addr}] MP insuficiente ({ses.personaje.mp}/{mp_coste}) para habilidad {tipo}")
                        return
                    ses.personaje.mp = max(0, ses.personaje.mp - mp_coste)
                    ses.enviar(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))
                dano_extra = abs(mag.get('hp', 0))
                atk_magic = tipo
                atk_efecto = _cb.efecto_de_ataque(tipo)
                # Enviar cooldown de TODAS las habilidades (kind=3) igual que el servidor real
                # El servidor real manda kind=3 con cd_ms para cada skill al usar una habilidad
                cd_ms = mag.get('cd_ms', 1000)
                if cd_ms > 0 and ses.personaje and getattr(ses.personaje, 'habilidades', None):
                    # Inundar cooldowns de todas las skills del jugador (copia exacta del comportamiento real)
                    cd_pkgs = []
                    for h_item in ses.personaje.habilidades:
                        sk_id = h_item[0] if isinstance(h_item, (list, tuple)) else h_item
                        cd_pkgs.append(struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, cd_ms))
                    ses.enviar(*cd_pkgs, _cb.gcd_paquete())
                    _sk_ids_copia = [h_item[0] if isinstance(h_item, (list, tuple)) else h_item
                                     for h_item in ses.personaje.habilidades]
                    try:
                        asyncio.get_event_loop().call_later(cd_ms / 1000.0,
                            lambda ids=_sk_ids_copia: ses.enviar(*[
                                struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, 0)
                                for sk_id in ids
                            ]))
                    except Exception:
                        pass
                elif cd_ms > 0:
                    ses.enviar(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, cd_ms), _cb.gcd_paquete())
                    try:
                        asyncio.get_event_loop().call_later(cd_ms / 1000.0, lambda: ses.enviar(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, 0)))
                    except Exception:
                        pass

            else:
                atk_magic, atk_efecto = _cb.ataque_estandar_arma(arma_puesta)

            # Probabilidad de golpe critico (base 5% + bonus de Ferocious Song / buffs)
            extra_crit = 0
            if buffs_activos:
                now = time.time()
                for b_id, b_data in list(buffs_activos.items()):
                    if isinstance(b_data, dict) and b_data.get('fin', 0) > now and 'crit' in b_data:
                        extra_crit += b_data['crit']
            crit_prob = min(0.90, (5 + extra_crit) / 100.0)
            es_crit = (random.random() < crit_prob)
            total_atk = ataque + dano_extra
            if es_crit:
                total_atk = int(round(total_atk * 1.5))

            dano = m.recibir(total_atk)
            # Marcar al monstruo en combate con el jugador
            m.en_combate_con = yo
            m.ultimo_ataque = time.time()
            ses.ultimo_combate = time.time()

            # Acumulacion de SP (303 puntos base + bono de Reserve)
            bars, max_pts = _max_sp_info(ses.personaje)
            res_rank = 1
            if ses.personaje and getattr(ses.personaje, 'habilidades', None):
                for h in ses.personaje.habilidades:
                    if (h[0] if isinstance(h, (list, tuple)) else h) == 15:
                        res_rank = h[1] if isinstance(h, (list, tuple)) and len(h) > 1 else 1
                        break
            sp_gain = 303 + res_rank * 5
            ant_bars = getattr(ses, 'sp', 0) // 1000
            ses.sp = min(max_pts, getattr(ses, 'sp', 0) + sp_gain)
            curr_bars = ses.sp // 1000
            pkgs_sp = [_cb.atributo(yo, ses.sp, _cb.KIND_SP)]
            if curr_bars != ant_bars:
                pkgs_sp.append(_iv.stats(ses.inventario, ses.personaje.habilidades,
                                         hp=ses.personaje.hp, hp_max=ses.personaje.hp_max,
                                         mp=ses.personaje.mp, mp_max=ses.personaje.mp_max,
                                         oro=ses.personaje.oro, buffs=buffs_activos,
                                         sp=ses.sp, sp_max=bars))

            ses.esfuerzo = max(0, getattr(ses, 'esfuerzo', 900) - _cb.COSTE_GOLPE)
            pkgs_sk = _otorgar_skill_exp(ses, ses.personaje, yo, arma_puesta=arma_puesta,
                                         magic_id=tipo if tipo != _cb.ATAQUE_NORMAL else 0)

            # S2C 0x0006 confirmacion de ataque: el servidor confirma que el golpe llego al objetivo.
            # Sin este paquete el cliente no reproduce el sprite de efecto del ataque.
            # Formato: [U8 01][U8 00][LE32 target_entity][U8 seq][U8 00][U8 00][U8 00][LE32 0xCB000000_pad]
            atk_seq = getattr(ses, '_atk_seq', 0x80)
            ses._atk_seq = (atk_seq + 3) & 0xFF
            atk_confirm = struct.pack('<BBIBBBBB', 0x01, 0x00, objetivo, atk_seq, 0x00, 0x00, 0x00, 0xCB) + b'\x00\x00\x00\x00'
            # Enviar animacion de ataque 0x000A + confirmacion 0x0006 + dano visual 0x0011 + vida monstruo 0x0013 + SP
            ses.enviar(_cb.ataque(yo, objetivo, atk_efecto),
                       struct.pack('<H', 0x0006) + atk_confirm,
                       _cb.atributo(objetivo, m.porcentaje),
                       _cb.numero_de_dano(yo, objetivo, dano, atk_magic, efecto=atk_efecto),
                       _cb.numero_flotante(objetivo, dano),
                       *pkgs_sk,
                       *pkgs_sp)
            try:
                asyncio.get_event_loop().call_later(0.12, lambda: ses.enviar_inmediato(_cb.cierre_de_dano(yo, objetivo, atk_magic, efecto=atk_efecto)))
            except Exception:
                pass
            if m.vivo:
                # Contraataca inmediatamente si esta en rango
                dist_m = max(abs(m.tile_x - ses.personaje.tile_x), abs(m.tile_y - ses.personaje.tile_y)) if ses.personaje else 1
                if dist_m <= getattr(m, 'atk_range', 1):
                    suyo = m.pegar()
                    # Aplicar mitigacion de daño porcentual de Fighting Shield (% mitigacion calculo final)
                    mit_pct = 0
                    if buffs_activos:
                        now = time.time()
                        for b_id, b_data in list(buffs_activos.items()):
                            if isinstance(b_data, dict) and b_data.get('fin', 0) > now and 'mit' in b_data:
                                mit_pct += b_data['mit']
                    if mit_pct > 0:
                        suyo = max(1, int(round(suyo * (1.0 - min(80, mit_pct) / 100.0))))

                    if ses.personaje:
                        ses.personaje.hp = max(0, ses.personaje.hp - suyo)
                        if ses.personaje.hp <= 0:
                            import clases as _cl
                            ses.enviar(_cl.aviso("You were defeated! Returning to safe haven...", tipo=0, msg_id=_cl.MSG_ITEM))
                            ses.personaje.hp = ses.personaje.hp_max
                            ses.personaje.mp = ses.personaje.mp_max
                            rev_x = getattr(ses.personaje, 'spawn_x', 138)
                            rev_y = getattr(ses.personaje, 'spawn_y', 60)
                            ses.personaje.tile_x, ses.personaje.tile_y = rev_x, rev_y
                            ses.enviar(struct.pack('<HIII', 0x0003, ses.personaje.entity_id, rev_x, rev_y),
                                       _cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP))
                            m.en_combate_con = None
                            if getattr(ses, 'usuario', None):
                                cuentas.guardar_posicion(ses.usuario, ses.personaje.char_id, rev_x, rev_y)
                                cuentas.guardar_progreso(ses.usuario, ses.personaje.char_id,
                                                         ses.personaje.nivel, ses.personaje.exp,
                                                         ses.personaje.hp, ses.personaje.mp)
                            log.info(f"[{addr}] jugador derrotado por {m.nombre}; revivido en checkpoint ({rev_x}, {rev_y})")
                            return

                        ef_mon = m.proj_ef if m.proj_ef > 0 else 148
                        ses.enviar(_cb.ataque(objetivo, yo, ef_mon),
                                   _cb.numero_de_dano(objetivo, yo, suyo, ataque=656, efecto=ef_mon),
                                   _cb.numero_flotante(yo, suyo),
                                   _cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP))
                    else:
                        ef_mon = m.proj_ef if m.proj_ef > 0 else 148
                        ses.enviar(_cb.ataque(objetivo, yo, ef_mon),
                                   _cb.numero_de_dano(objetivo, yo, suyo, ataque=656, efecto=ef_mon),
                                   _cb.numero_flotante(yo, suyo))
                log.debug(f"[{addr}] pego {dano} al {m.nombre} "
                          f"({m.porcentaje}%), contraataque procesado")
                return


            # --- Monstruo Muerto: Avisar muerte, Despawn con animacion, Respawn, EXP y Botin ---
            import clases as _cl
            if ses.personaje and ses.personaje.stage == 57 and m.npc_type == 224:
                ses.slarm_kills = getattr(ses, 'slarm_kills', 0) + 1
                log.info(f"[{addr}] Little Slarm derrotado en Fighting Palace ({ses.slarm_kills}/2)")

            # 1. Avisar muerte del monstruo (vida 0) y evento de muerte (tipo 7)
            # El monstruo reproduce su animacion de muerte en el cliente
            ses.enviar(_cb.atributo(objetivo, 0, _cb.VIDA),
                       _cb.muerte_monstruo(objetivo, yo))

            # Despawnear a los 2.5 segundos para que se vea la animacion de morir completa
            try:
                asyncio.get_event_loop().call_later(2.5, lambda: ses.enviar_inmediato(_cb.despawn_monstruo(objetivo)))
            except Exception:
                pass


            # Programar respawn del monstruo en 20 segundos
            def _respawn():
                if not getattr(m, 'vivo', False):
                    m.revivir()
                    import login as _lg
                    # Mandar aparicion del monstruo vivo de nuevo en su spawn_tile
                    ses.enviar_inmediato(_lg._npc_spawn(objetivo, m.npc_type, m.nombre, (m.tile_x, m.tile_y), klass=1))
                    log.info(f"[{addr}] monstruo {m.nombre} (entidad {objetivo}) reaparecio")

            try:
                asyncio.get_event_loop().call_later(_cb.SEGUNDOS_REAPARICION, _respawn)
            except Exception:
                pass

            # 2. Calcular EXP y Skill EXP con los multiplicadores configurables
            buffs = ses.personaje.buffs if ses.personaje else {}
            exp_ganada = _cb.calcular_exp(m.npc_type, buffs)
            sk_exp_ganada = _cb.calcular_skill_exp(buffs)

            # 3. Oro
            oro = _cb.botin()
            ses.oro = getattr(ses, 'oro', 0) + oro
            if ses.personaje:
                ses.personaje.oro = ses.oro

            salida_combate = []
            cid = ses.personaje.char_id if ses.personaje else 4980

            # 4. Progreso de personaje y Habilidades
            if ses.personaje:
                p = ses.personaje
                p.exp += exp_ganada
                subio_nivel = False
                while True:
                    exp_siguiente = _cb.exp_para_nivel(p.nivel + 1)
                    if exp_siguiente > 0 and p.exp >= exp_siguiente:
                        p.nivel += 1
                        p.hp_max += 25
                        p.mp_max += 15
                        subio_nivel = True
                    else:
                        break
                if subio_nivel:
                    p.hp = p.hp_max
                    p.mp = p.mp_max
                    salida_combate.append(_cl.aviso(f"Level Up! Reached Level {p.nivel}!", tipo=0, msg_id=_cl.MSG_ITEM))
                    salida_combate.append(_cb.atributo(yo, p.hp, _cb.KIND_HP))
                    salida_combate.append(_cb.atributo(yo, p.mp, _cb.KIND_MP))
                    # 0x001D compound level-up: opcode + entity + count=4 + 4x(kind + v1 + v2)
                    # Kind 29=level, 30=current_exp, 31=exp_to_next, 32=exp_bar
                    exp_sig = _cb.exp_para_nivel(p.nivel + 1)
                    salida_combate.append(
                        struct.pack('<HIB', 0x001D, yo, 4) +
                        struct.pack('<BII', 29, p.nivel, 0) +
                        struct.pack('<BII', 30, p.exp, 0) +
                        struct.pack('<BII', 31, exp_sig, 0) +
                        struct.pack('<BII', 32, p.exp, 0)
                    )
                    salida_combate.append(_stats_ses(ses))
                    log.info(f"[{addr}] {p.nombre} SUBIO A NIVEL {p.nivel} (enviado 0x001D compound)!")

                # Paquetes oficiales para EXP y actualizacion de barra
                # 0x000B kind=1 genera 'Obtain X Exp.' en pantalla y chat
                salida_combate.append(_cb.exp_paquete(objetivo, exp_ganada, 1))
                # 0x001D kind=32 (0x20) ACTUALIZA LA BARRA DE EXPERIENCIA EN LA UI
                salida_combate.append(struct.pack('<HIBBII', 0x001D, yo, 1, 32, p.exp, 0))

                if getattr(ses, 'usuario', None):
                    cuentas.guardar_progreso(ses.usuario, p.char_id, p.nivel, p.exp,
                                             p.hp, p.mp, p.habilidades,
                                             hp_max=p.hp_max, mp_max=p.mp_max)
                    cuentas.guardar_oro(ses.usuario, p.char_id, ses.oro)

            salida_combate.append(_cl.aviso(f'{oro} Gold', tipo=0, msg_id=_cl.MSG_ITEM))


            # 5. Drops de items al inventario (con apilamiento de consumibles y tope de bolsa)
            drops = _cb.botin_items(m.npc_type)
            bolsa = getattr(ses, 'inventario', {})
            tiene_mochila = (bolsa.get(7) is not None or bolsa.get(8) is not None)
            max_ranura = 44 if tiene_mochila else 39

            for item_drop, cant in drops:
                r_slot = None
                if _iv.es_apilable(item_drop):
                    for s, it_id in bolsa.items():
                        if 20 <= s <= max_ranura and it_id == item_drop:
                            r_slot = s
                            break
                if r_slot is None:
                    for r in range(20, max_ranura + 1):
                        if r not in bolsa:
                            r_slot = r
                            break
                if r_slot is None:
                    log.info(f"[{addr}] inventario lleno (limite={max_ranura}), drop {item_drop} ignorado silenciosamente")
                    continue

                bolsa[r_slot] = item_drop
                salida_combate.append(_cl.aviso(_nombre_item(item_drop), tipo=0, msg_id=_cl.MSG_ITEM))
                salida_combate.extend(_iv.entregar(cid, item_drop, r_slot))

            salida_combate.append(_iv.completo(cid, _con_oro(ses)))
            ses.enviar(*salida_combate)
            if ses.personaje and getattr(ses, 'usuario', None):
                cuentas.guardar_inventario(ses.usuario, cid, bolsa)

            log.info(f"[{addr}] mato un {m.nombre} (entidad {objetivo}); "
                     f"+{exp_ganada} exp, +{oro} oro, {len(drops)} items")
            return

        # --- el cliente pide el mapa nuevo -------------------------------
        # Tras un 0x000C el cliente contesta con un 0x0009 vacio y espera la
        # secuencia de entrada otra vez, ya con la ficha en el mapa nuevo.
        if opcode == 0x0009 and ses.rol == 'mundo' and ses.personaje:
            import inventario as _iv2
            import clases as _cl2
            import combate as _cb2
            import login as _lg2
            p = ses.personaje
            ses.monstruos = _monstruos_de(p.stage)
            # Cargar la secuencia completa oficial del nuevo mapa (aparicion, capas, barra, stats, spawns y atributos)
            for sub in _lg2.secuencia(p):
                ses.enviar(sub)
            ses.enviar(_stats_ses(ses))
            if p.habilidades:
                _ids = [h[0] for h in p.habilidades]
                ses.enviar(_cl2.arbol(_ids))
                _hech = _cl2.hechizos_iniciales(_ids)
                if _hech:
                    ses.enviar(_cl2.otorgar_hechizos(p.entity_id, [n for n, _ in _hech]))
            log.info(f"[{addr}] mapa cargado exitosamente: stage {p.stage} "
                     f"tile ({p.tile_x},{p.tile_y})")
            return

        # --- comprar en una tienda ---------------------------------------
        # La ventana la abre el cliente solo; aqui solo se atiende la compra.
        if opcode == 0x0027 and ses.rol == 'mundo' and cuerpo:
            import clases as _c
            import inventario as _iv
            import sqlite3 as _sq
            d2 = _c.parsear_compra(cuerpo)
            if not d2 or getattr(ses, 'inventario', None) is None:
                return
            item_id, cant = d2
            precio = _precio_item(item_id) * cant
            if getattr(ses, 'oro', 0) < precio:
                log.warning(f"[{addr}] compra rechazada: el item {item_id} vale "
                            f"{precio} y hay {getattr(ses, 'oro', 0)}")
                return
            ses.oro -= precio
            if ses.personaje:
                ses.personaje.oro = ses.oro
            ranura = _ranura_libre(ses.inventario)
            ses.inventario[ranura] = item_id
            cid = ses.personaje.char_id if ses.personaje else 4980
            ses.enviar(_c.aviso(f'{precio} Gold', tipo=0, msg_id=_c.MSG_PAGO),
                       _c.aviso(_nombre_item(item_id), tipo=0, msg_id=_c.MSG_ITEM),
                       *_iv.entregar(cid, item_id, ranura),
                       _iv.completo(cid, _con_oro(ses)),
                       struct.pack('<HII', 0x0035, item_id, cant))
            if getattr(ses, 'usuario', None):
                cuentas.guardar_inventario(ses.usuario, cid, ses.inventario)
                cuentas.guardar_oro(ses.usuario, cid, ses.oro)
            log.info(f"[{addr}] compra: {_nombre_item(item_id)} x{cant} por "
                     f"{precio}; quedan {ses.oro} de oro")
            return

        # --- venta a tienda NPC (WND_NPCSALE) ---------------------------
        # Cliente manda [LE32 n_items] y luego [LE32 slot][LE32 inst_hi][LE32 cant] por item
        if opcode == 0x0028 and ses.rol == 'mundo' and cuerpo and ses.personaje:
            import clases as _c
            import inventario as _iv
            bolsa = getattr(ses, 'inventario', {})
            cid = ses.personaje.char_id
            oro_ganado = 0
            if len(cuerpo) >= 4:
                n_items = struct.unpack_from('<I', cuerpo, 0)[0]
                offset = 4
                for _ in range(n_items):
                    if offset + 12 > len(cuerpo):
                        break
                    slot, inst_hi, cant = struct.unpack_from('<III', cuerpo, offset)
                    offset += 12
                    cant = max(1, cant)
                    if slot in bolsa:
                        it_id = bolsa[slot]
                        del bolsa[slot]
                        precio_base = _precio_item(it_id)
                        ganancia_item = max(1, (precio_base // 2)) * cant
                        oro_ganado += ganancia_item
                        log.info(f"[{addr}] vendio item {it_id} ranura {slot} x{cant} por {ganancia_item} oro")

                ses.oro = getattr(ses, 'oro', 0) + oro_ganado
                if ses.personaje:
                    ses.personaje.oro = ses.oro
                salida = [
                    _iv.completo(cid, _con_oro(ses)),
                    _c.aviso(f"{oro_ganado} Gold", tipo=0, msg_id=_c.MSG_PAGO),
                ]
                ses.enviar(*salida)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa)
                    cuentas.guardar_oro(ses.usuario, cid, ses.oro)
            return

        # --- Descartar / Destruir item del inventario (papelera) ---------
        if opcode == 0x004C and ses.rol == 'mundo' and ses.personaje and cuerpo:
            import inventario as _iv
            import clases as _c
            slot = cuerpo[0]
            bolsa = getattr(ses, 'inventario', {})
            cid = ses.personaje.char_id
            if slot in bolsa:
                item_del = bolsa[slot]
                del bolsa[slot]
                nom_it = _nombre_item(item_del)
                ses.enviar(_iv.completo(cid, _con_oro(ses)),
                           _c.aviso(f"Destroyed {nom_it}", tipo=0, msg_id=_c.MSG_ITEM))
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa)
                log.info(f"[{addr}] item destruido en ranura {slot}: {item_del} ({nom_it})")
            return

        # --- Mover / Intercambiar item entre ranuras (drag & drop) -------
        if opcode == 0x0130 and ses.rol == 'mundo' and ses.personaje and cuerpo:
            import inventario as _iv
            if len(cuerpo) >= 2:
                s1, s2 = cuerpo[0], cuerpo[1]
                bolsa = getattr(ses, 'inventario', {})
                cid = ses.personaje.char_id
                it1 = bolsa.pop(s1, None)
                it2 = bolsa.pop(s2, None)
                if it1 is not None:
                    bolsa[s2] = it1
                if it2 is not None:
                    bolsa[s1] = it2
                ses.enviar(_iv.completo(cid, _con_oro(ses)))
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa)
                log.info(f"[{addr}] intercambio ranuras inventario: {s1} <-> {s2}")
            return

        # --- eleccion de clase -----------------------------------------
        # La ventana la abre el cliente solo; lo unico que llega es esto.
        if opcode == 0x003A and ses.rol == 'mundo' and cuerpo:
            import clases
            ids = clases.parsear_eleccion(cuerpo)
            if not ids:
                return
            # La clase se elige UNA vez. Sin esto se le puede volver a hablar
            # al NPC y cambiarla cuantas veces se quiera.
            if ses.personaje and ses.personaje.habilidades:
                actual = ', '.join(clases.nombre(h[0])
                                   for h in ses.personaje.habilidades)
                log.warning(f"[{addr}] ya tiene clase ({actual}); se ignora el "
                            f"intento de cambiarla")
                return
            salida = []
            for sid in ids:
                salida.append(clases.aviso(clases.nombre(sid)))
            # El arbol completo. Sin el, el panel de habilidades del cliente
            # sale lleno de interrogantes: no conoce las otras treinta.
            salida.append(clases.arbol(ids))
            # Los tres hechizos de nivel 1 del arma, que son los que el
            # cliente pone en F1..F3. En la captura llegan justo despues del
            # arbol, tres 0x000D seguidos con id de mensaje 425.
            hechizos = clases.hechizos_iniciales(ids)
            for _, nom in hechizos:
                salida.append(clases.aviso(nom, tipo=7,
                                           msg_id=clases.MSG_HECHIZO))
            # El 0x000D de arriba solo escribe "Learn X" en el chat. Los
            # iconos no salen hasta que llega este 0x001D.
            if hechizos and ses.personaje:
                salida.append(clases.otorgar_hechizos(
                    ses.personaje.entity_id, [n for n, _ in hechizos]))

            # Entregar lo que da la clase y anotar el class_id. Ambas cosas
            # estan medidas del servidor real AngelWar, no deducidas.
            import inventario as _iv
            regalo = clases.regalo(ids)
            cid = ses.personaje.char_id if ses.personaje else 4980
            if regalo and getattr(ses, 'inventario', None) is not None:
                for ranura, item_id in regalo:
                    ses.inventario[int(ranura)] = int(item_id)
                items_vistos = set()
                for ranura, item_id in regalo:
                    if item_id not in items_vistos:
                        items_vistos.add(item_id)
                        salida.append(clases.aviso(_nombre_item(item_id), tipo=0, msg_id=clases.MSG_ITEM))
                salida.append(_iv.completo(cid, _con_oro(ses)))

            # Actualizar stats para Swordsman: Max HP = 304, MP = 154
            if ses.personaje:
                if 9 in ids:  # Swordsman
                    ses.personaje.hp_max = 304
                    ses.personaje.hp = 304
                bars, max_pts = _max_sp_info(ses.personaje)
                ses.sp = max_pts
                salida.append(_iv.stats(
                    ses.inventario, [(sid, 1, 0) for sid in ids],
                    hp=ses.personaje.hp, hp_max=ses.personaje.hp_max,
                    mp=ses.personaje.mp, mp_max=ses.personaje.mp_max,
                    oro=ses.personaje.oro,
                    sp=ses.sp, sp_max=bars
                ))
                import combate as _cb
                salida.append(_cb.atributo(ses.personaje.entity_id, ses.sp, _cb.KIND_SP))

            ses.enviar(*salida)

            if ses.personaje:
                ses.personaje.habilidades = [(sid, 1, 0) for sid in ids]
                if hechizos:
                    ses.personaje.barra = [n for n, _ in hechizos]
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_habilidades(
                        ses.usuario, ses.personaje.char_id,
                        ses.personaje.habilidades)
                    cuentas.guardar_oro(ses.usuario, cid, ses.personaje.oro)
                    cuentas.guardar_inventario(ses.usuario, cid, ses.inventario)
                    cuentas.guardar_barra(ses.usuario, cid, ses.personaje.barra)
                    cuentas.guardar_progreso(
                        ses.usuario, cid, ses.personaje.nivel, ses.personaje.exp,
                        ses.personaje.hp, ses.personaje.mp, ses.personaje.habilidades,
                        ses.personaje.hp_max, ses.personaje.mp_max)

            log.info(f"[{addr}] CLASE ELEGIDA: "
                     + ', '.join(f'{clases.nombre(i)}({i})' for i in ids)
                     + (f" | hechizos: {', '.join(n for _, n in hechizos)}"
                        if hechizos
                        else " | SIN hechizos de nivel 1 para esa rama"))

            _cid = clases.class_id(ids[0])
            if _cid is not None and ses.personaje and getattr(ses, 'usuario', None):
                cuentas.guardar_clase(ses.usuario, ses.personaje.char_id, _cid)
                log.info(f"[{addr}] class_id {_cid} guardado")
            return

        if opcode == 0x0044 and ses.rol == 'mundo' and len(cuerpo) >= 7:
            # Asignacion de hotkey en la barra (F1..F8, 1..8)
            slot = cuerpo[1]
            mid = struct.unpack_from('<I', cuerpo, 3)[0]
            if ses.personaje:
                while len(ses.personaje.barra) <= slot:
                    ses.personaje.barra.append(0)
                ses.personaje.barra[slot] = mid
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_barra(ses.usuario, ses.personaje.char_id, ses.personaje.barra)
            log.info(f"[{addr}] barra slot {slot} asignada a magic/item {mid}")
            return

        # --- equipar y desequipar --------------------------------------
        # 0x0012 del cliente es MOVER UN ITEM, no hablar con un NPC: eso se
        # confundio al principio porque el cuerpo "02 00 14 00" aparecia
        # despues de hacer clic cerca de un NPC. Con marca de tiempo quedo
        # claro: lo que contesta el servidor es el contenido del contenedor
        # (0x001B) y los stats recalculados (0x0042), no un dialogo.
        if opcode == 0x0012 and ses.rol == 'mundo' and len(cuerpo) >= 4:
            import inventario as inv
            org, dst = struct.unpack_from('<HH', cuerpo, 0)
            bolsa = getattr(ses, 'inventario', None)
            if bolsa is None:
                return
            if org not in bolsa:
                log.warning(f"[{addr}] mover {org} -> {dst}: la ranura {org} esta vacia")
                return
            cid = ses.personaje.char_id if ses.personaje else 4980
            if dst in bolsa:
                # Intercambio (swap) entre ranuras ocupadas
                it_org = bolsa[org]
                it_dst = bolsa[dst]
                bolsa[org] = it_dst
                bolsa[dst] = it_org
                salida = [
                    inv.movimiento(org, dst, cid, it_org, inv.instancia_de(cid, it_org)),
                    inv.movimiento(dst, org, cid, it_dst, inv.instancia_de(cid, it_dst)),
                ]
                if inv.es_equipo(org) or inv.es_equipo(dst):
                    salida.append(_stats_ses(ses))
                ses.enviar(*salida)
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, ses.personaje.char_id, bolsa)
                log.info(f"[{addr}] swap ranuras {org} ({it_org}) <-> {dst} ({it_dst})")
                return

            it = bolsa.pop(org)
            bolsa[dst] = it
            salida = [inv.movimiento(org, dst, cid, it, inv.instancia_de(cid, it))]
            if inv.es_equipo(org) or inv.es_equipo(dst):
                salida.append(_stats_ses(ses))
            # Gestion de mascota en ranura 9
            if dst == 9:
                sp = inv.sprite_de_mascota(it)
                pet_eid = (ses.personaje.entity_id if ses.personaje else 1001) + 5000
                ses.pet_entity_id = pet_eid
                import login as _lg
                salida.append(_lg._npc_spawn(pet_eid, 9999, "Pet", (ses.personaje.tile_x + 1, ses.personaje.tile_y), sprite=sp))
            elif org == 9 and dst != 9:
                pet_eid = getattr(ses, 'pet_entity_id', None)
                if pet_eid:
                    import combate as _cb
                    salida.append(_cb.atributo(pet_eid, 0, _cb.VIDA))
                    ses.pet_entity_id = None
            ses.enviar(*salida)
            if ses.personaje and getattr(ses, 'usuario', None):
                cuentas.guardar_inventario(ses.usuario, ses.personaje.char_id, bolsa)
            log.info(f"[{addr}] item {it}: ranura {org} -> {dst}"
                     + ("  (cambia el equipo)"
                        if inv.es_equipo(org) or inv.es_equipo(dst) else ""))
            return

        # --- usar item (clic derecho) --------------------------------
        # C -> S 0x002E [U8 ranura][LE32 target]
        if opcode == 0x002E and ses.rol == 'mundo' and cuerpo:
            import inventario as inv
            import clases as _c
            ranura = cuerpo[0]
            bolsa = getattr(ses, 'inventario', None)
            if bolsa is None or ranura not in bolsa:
                return
            item_id = bolsa[ranura]
            cid = ses.personaje.char_id if ses.personaje else 4980

            # Caso 1: Item equipable (clic derecho)
            if inv.es_equipo(ranura):
                # Ya esta puesto -> desequipar a la bolsa
                dst = _ranura_libre(bolsa, desde=20)
                it = bolsa.pop(ranura)
                bolsa[dst] = it
                salida = [
                    inv.movimiento(ranura, dst, cid, it, inv.instancia_de(cid, it)),
                    _stats_ses(ses)
                ]
                if ranura == 9 and getattr(ses, 'pet_entity_id', None):
                    import combate as _cb
                    salida.append(_cb.atributo(ses.pet_entity_id, 0, _cb.VIDA))
                    ses.pet_entity_id = None
                ses.enviar(*salida)
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa)
                log.info(f"[{addr}] desequipar: item {it} ({ranura}) -> bolsa ({dst})")
                return

            eq_slot = inv.ranura_equipo_de(item_id)
            if eq_slot is not None:
                # Poner en la ranura de equipo correspondiente
                dst = eq_slot
                # Si se equipa un arma a dos manos (Lanza, Arco, etc.) en mano derecha (3):
                # Desequipar la mano izquierda (4) si habia algo puesto
                if dst == 3 and inv.es_arma_dos_manos(item_id) and 4 in bolsa:
                    it_lhand = bolsa.pop(4)
                    libre = _ranura_libre(bolsa, desde=20)
                    bolsa[libre] = it_lhand
                    log.info(f"[{addr}] arma a dos manos: desequipando mano izquierda {it_lhand} -> bolsa {libre}")
                elif dst == 4 and 3 in bolsa and inv.es_arma_dos_manos(bolsa[3]):
                    # Si intenta equipar mano izquierda y tiene lanza a 2 manos puesta, desequipar la lanza
                    it_rhand = bolsa.pop(3)
                    libre = _ranura_libre(bolsa, desde=20)
                    bolsa[libre] = it_rhand
                    log.info(f"[{addr}] equipando mano izquierda: desequipando arma a dos manos {it_rhand} -> bolsa {libre}")

                if dst in bolsa:
                    # Reemplazar equipo actual (swap con lo puesto)
                    it_eq = bolsa[dst]
                    bolsa[ranura] = it_eq
                    bolsa[dst] = item_id
                    log.info(f"[{addr}] reemplazar equipo: item {item_id} -> {dst}, sacando {it_eq} -> {ranura}")
                else:
                    it = bolsa.pop(ranura)
                    bolsa[dst] = it
                    log.info(f"[{addr}] equipar directo: item {it} -> ranura {dst}")

                salida = [
                    inv.completo(cid, _con_oro(ses)),
                    _stats_ses(ses)
                ]

                if dst == 9:
                    # Spawn de la mascota invocada
                    sp = inv.sprite_de_mascota(item_id)
                    pet_eid = (ses.personaje.entity_id if ses.personaje else 1001) + 5000
                    ses.pet_entity_id = pet_eid
                    import login as _lg
                    salida.append(_lg._npc_spawn(pet_eid, 9999, "Pet", (ses.personaje.tile_x + 1, ses.personaje.tile_y), sprite=sp))

                ses.enviar(*salida)
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa)
                return

            # Caso 2: Comida de mascota (Pet Cookies, Pet Can, Pet Feed) - Solo si hay mascota activa
            if inv.es_comida_mascota(item_id) and (9 in bolsa):
                del bolsa[ranura]
                salida = [
                    _c.aviso("Fed pet! Hunger satiated (up to 500/100 buffer).", tipo=0, msg_id=_c.MSG_ITEM),
                    inv.completo(cid, _con_oro(ses))
                ]
                ses.enviar(*salida)
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa)
                log.info(f"[{addr}] comida de mascota usada: {item_id} (ranura {ranura})")
                return

            # Caso 3: Cajas de regalo / Growth Boxes (drop_table)
            recompensas = inv.recompensas_caja(item_id)
            if recompensas:
                del bolsa[ranura]
                log.info(f"[{addr}] abriendo caja {item_id} de ranura {ranura}: "
                         f"{len(recompensas)} tipos de items")
                salida = []
                primero = True
                for rew_id, cant in recompensas:
                    r_slot = ranura if primero else _ranura_libre(bolsa, desde=20)
                    primero = False
                    bolsa[r_slot] = rew_id
                    salida.append(_c.aviso(_nombre_item(rew_id), tipo=0, msg_id=_c.MSG_ITEM))
                    salida.extend(inv.entregar(cid, rew_id, r_slot))
                salida.append(inv.completo(cid, _con_oro(ses)))
                ses.enviar(*salida)
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa)
                return

            # Caso 4: Consumibles (Pociones HP/MP, Hierba Magica 1228, Biscuits 2, etc.)
            ef_con = inv.efecto_consumible(item_id)
            if ef_con and ses.personaje:
                del bolsa[ranura]
                salida = []
                yo = ses.personaje.entity_id
                import combate as _cb
                if 'hp' in ef_con:
                    curado = ef_con['hp']
                    ses.personaje.hp = min(ses.personaje.hp_max, ses.personaje.hp + curado)
                    salida.append(_cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP))
                    salida.extend(_cb.efecto_curacion(yo, yo, curado, efecto=165))
                if 'mp' in ef_con:
                    rec_mp = ef_con['mp']
                    ses.personaje.mp = min(ses.personaje.mp_max, ses.personaje.mp + rec_mp)
                    salida.append(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))
                    pct_mp = max(0, min(100, round(100 * ses.personaje.mp / ses.personaje.mp_max)))
                    salida.append(_cb.atributo(yo, pct_mp, 1))
                    salida.extend(_cb.efecto_recuperacion_mp(yo, yo, rec_mp, efecto=69))
                salida.append(inv.completo(cid, _con_oro(ses)))
                ses.enviar(*salida)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_progreso(ses.usuario, cid, ses.personaje.nivel, ses.personaje.exp,
                                             ses.personaje.hp, ses.personaje.mp,
                                             hp_max=ses.personaje.hp_max, mp_max=ses.personaje.mp_max)
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa)
                log.info(f"[{addr}] consumible usado: {item_id} (ranura {ranura}) -> {ef_con}")
                return

            # Caso 5: Tarjetas de Monstruo / Coleccionables
            if inv.es_tarjeta_coleccion(item_id):
                del bolsa[ranura]
                nom_it = _nombre_item(item_id)
                salida = [
                    _c.aviso(f"Registered {nom_it} to Card Collection!", tipo=0, msg_id=_c.MSG_ITEM),
                    inv.completo(cid, _con_oro(ses))
                ]
                ses.enviar(*salida)
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa)
                log.info(f"[{addr}] tarjeta usada: {nom_it} (ranura {ranura})")
                return

            log.info(f"[{addr}] usar item {item_id} (ranura {ranura}): sin accion")
            return

        # --- escena / mapa de radar (Scene Map) -------------------------
        # 0x012D C2S: el cliente abre la ventana de mini-mapa/escena.
        # El servidor responde con una cabecera 0x0062 (entidad de zona) y
        # luego entradas 0x0061 para cada NPC/entidad de interes, terminando
        # con un 0x0061 de un solo byte 0x00.
        if opcode == 0x012D and ses.rol == 'mundo':
            # Usar un entity_id de zona generico basado en el stage del jugador
            stage_z = getattr(ses.personaje, 'stage', 41) if ses.personaje else 41
            zona_eid = 0x000F3000 + stage_z  # entidad de zona ficticia por mapa
            ses.enviar(struct.pack('<HI', 0x0062, zona_eid),
                       struct.pack('<HB', 0x0061, 0x00))
            log.debug(f"[{addr}] escena (0x012D) respondida para stage {stage_z}")
            return

        # 0x012B C2S: radar de NPCs cercanos (5 bytes: 02 00 00 00 00).
        # El servidor responde con 0x0062 + lista de entidades 0x0061 + 0x00.
        # Cada entrada 0x0061 tiene: [U8 kind=1][LE32 eid][LE32 v1][LE32 v2][24 bytes cero]
        if opcode == 0x012B and ses.rol == 'mundo':
            stage_z = getattr(ses.personaje, 'stage', 41) if ses.personaje else 41
            zona_eid = 0x000F3000 + stage_z
            pkgs_radar = [struct.pack('<HI', 0x0062, zona_eid)]
            # Agregar al jugador como entidad del radar
            if ses.personaje:
                yo = ses.personaje.entity_id
                radar_entry = (
                    struct.pack('<H', 0x0061) +
                    struct.pack('<B', 0x01) +  # kind=1 (jugador)
                    struct.pack('<I', yo) +
                    struct.pack('<I', ses.personaje.nivel) +
                    struct.pack('<I', 100) +  # HP%
                    b'\x00' * 24
                )
                pkgs_radar.append(radar_entry)
            # Terminador
            pkgs_radar.append(struct.pack('<HB', 0x0061, 0x00))
            ses.enviar(*pkgs_radar)
            log.debug(f"[{addr}] radar (0x012B) respondido para stage {stage_z}")
            return

        # --- dialogo con los NPC -------------------------------------
        # Secuencia establecida con una captura con marca de tiempo:
        #   0x0005 [LE32 entity] clic   ->  0x0012 primera linea
        #   0x000B [01] siguiente       ->  0x0012 linea siguiente
        #   ... y al terminar, un 0x0012 de nueve ceros que cierra el cuadro.
        if opcode == 0x0005 and ses.rol == 'mundo' and len(cuerpo) >= 4:
            import dialogos
            ent = struct.unpack_from('<I', cuerpo, 0)[0]
            # Si ya se cumplio lo que pedia el tramo actual, se avanza ANTES
            # de hablar: en el juego, en cuanto llevas el examen encima
            # Raphael te suelta el "Good for you!" y no repite lo anterior.
            if ses.personaje and ses.personaje.stage == MAPA_DEL_TUTORIAL and ent in dialogos.NOMBRE_POR_ENTIDAD:
                import clases as _c
                _sig = ses.personaje.tutorial + 1
                _req = _c.REQUISITO_ETAPA.get(_sig)
                if (_req and _sig < dialogos.etapas(ent)
                        and _req in (getattr(ses, 'inventario', {}) or {}).values()):
                    ses.personaje.tutorial = _sig
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_tutorial(ses.usuario,
                                                 ses.personaje.char_id, _sig)
                    log.info(f"[{addr}] tutorial: cumplido el requisito, "
                             f"pasa a la etapa {_sig}")
            # Clic en un MONSTRUO: hay que contestar con su vida. Eso es lo
            # que hace el servidor real y lo que le dice al cliente que ese
            # objetivo se puede atacar; sin la respuesta el cliente ni siquiera
            # llega a mandar el 0x0006 y parecia que "no deja atacar".
            import combate as _cb0
            _m = (getattr(ses, 'monstruos', None) or {}).get(ent)
            if _m is not None:
                # Lo que contesta el servidor real es un 0x000A fijando el
                # objetivo, no la vida. Con el 0x0013 solo, el cliente no
                # llegaba a mandar el 0x0006 y no se podia atacar.
                ses.enviar(_cb0.fijar_objetivo(ses.entity_id or 1001, ent),
                           _cb0.atributo(ent, _m.porcentaje))
                log.debug(f"[{addr}] objetivo fijado: {_m.nombre} "
                          f"({_m.porcentaje}%)")
                return



            # Los dialogos del tutorial van por entity_id (19 Raphael, 20
            # Interface Tutor, 21 Angel Aide) y esos numeros SE REPITEN en
            # otros mapas: en el Lyceum la 19 es el Magic Seller, la 20 el Bao
            # Clerk y la 21 Michael, y les salia el dialogo del tutorial. Solo
            # valen en Guide Palace.
            # En Fighting Palace (stage 57):
            if ses.personaje and ses.personaje.stage == 57:
                if ent == 500:
                    kills = getattr(ses, 'slarm_kills', 0)
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    g_fp = dialogos.guion_fighting_palace(kills, nom)
                    ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g_fp, 0
                    ses.dlg_val = 5
                    ses.enviar(dialogos.linea_de(g_fp, 0, nom))
                    ses.dlg_paso = 1
                    log.info(f"[{addr}] Angel Raphael (Fighting Palace, kills={kills}): linea 1 de {len(g_fp)}")
                    return
                # Totems de facciones en Fighting Palace:
                totems_fp = {501: 5138, 502: 5137, 503: 5136, 504: 5139}
                if ent in totems_fp:
                    sub_totem = dialogos.armar_linea(totems_fp[ent], 4, [])
                    ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, [sub_totem[2:]], 1
                    ses.dlg_val = 4
                    ses.enviar(sub_totem)
                    log.info(f"[{addr}] Totem {ent} en Fighting Palace (dialogo {totems_fp[ent]})")
                    return
                log.debug(f"[{addr}] clic en la entidad {ent} en stage 57: sin dialogo")
                return

            if ses.personaje and ses.personaje.stage != MAPA_DEL_TUTORIAL:
                # Fuera del tutorial, cada NPC tiene su propia linea, sacada
                # de msg.xml por su nombre.
                faccion = ses.personaje.faction if ses.personaje else "Heaven"
                g2 = dialogos.propio(_nombre_entidad(ses, ent), faccion=faccion)
                if g2:
                    nom2 = ses.personaje.nombre if ses.personaje else 'Jugador'
                    ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g2, 1
                    ses.dlg_val = struct.unpack_from('<H', g2[0], 4)[0] if len(g2[0]) >= 6 else 4
                    ses.enviar(dialogos.linea_de(g2, 0, nom2))
                    log.info(f"[{addr}] dialogo de {_nombre_entidad(ses, ent)} (val={ses.dlg_val})")
                    return
                log.debug(f"[{addr}] clic en la entidad {ent}: sin dialogo")
                return
            # En Guide Palace (stage 51):
            inv_items = list((getattr(ses, 'inventario', {}) or {}).values())
            has_exam = (1386 in inv_items)
            bolsa = getattr(ses, 'inventario', {}) or {}
            # Guantes (5) o Zapatos (6) que Raphael ensena a equiparse en la etapa 1:
            has_gloves_or_shoes = bool(bolsa.get(5) or bolsa.get(6))

            if ent == 19:  # Raphael
                if has_exam:
                    etapa = 3
                elif ses.personaje and ses.personaje.tutorial >= 2:
                    etapa = 2
                elif ses.personaje and ses.personaje.tutorial >= 1 and has_gloves_or_shoes:
                    etapa = 2
                elif (ses.personaje and ses.personaje.habilidades):
                    etapa = 1
                else:
                    etapa = 0
            elif ent == 21:  # Angel Aide
                if has_exam:
                    etapa = 2  # 5047 (Good for you!)
                elif (ses.personaje and (ses.personaje.tutorial >= 2 or getattr(ses, 'oro', 0) >= 10)):
                    etapa = 1  # 5022 con menu: 5045 Buy / 5046 Quit
                else:
                    etapa = 0  # 5022 sin menu (0 opciones)
            else:  # 20 Interface Tutor
                etapa = 0

            g = dialogos.guion_etapa(ent, etapa)
            if not g:
                log.debug(f"[{addr}] clic en la entidad {ent}: sin dialogo conocido")
                return
            nom = ses.personaje.nombre if ses.personaje else 'Jugador'
            ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g, 0
            ses.dlg_val = 3 if ent == 19 else (2 if ent == 20 else 52)
            ses.enviar(dialogos.linea_de(g, 0, nom))
            ses.dlg_paso = 1
            log.info(f"[{addr}] dialogo con la entidad {ent} (etapa {etapa}): "
                     f"linea 1 de {len(g)}")
            return

        if opcode == 0x000B and ses.rol == 'mundo' and getattr(ses, 'dlg_ent', None):
            import dialogos
            ent, paso = ses.dlg_ent, getattr(ses, 'dlg_paso', 0)
            g = getattr(ses, 'dlg_guion', None) or []
            # Elegir una opcion del cuadro, no pasar de linea.
            _v = d.get('valor', 1) if d else 1
            if dialogos.es_opcion(_v):
                _ops = dialogos.opciones_de(g[paso - 1]) if 0 < paso <= len(g) else []
                _i = dialogos.indice_opcion(_v)
                _el = _ops[_i] if _i < len(_ops) else None
                val = getattr(ses, 'dlg_val', 4)

                # Casos especiales de opciones en Guide Palace:
                # 1. Interface Tutor: 5241 ("OK") -> Inicia explicacion paso a paso
                if _el == 5241:
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    ses.dlg_ent = ent
                    ses.dlg_guion = g
                    ses.dlg_paso = 2
                    ses.enviar(dialogos.linea_de(g, 1, nom))
                    log.info(f"[{addr}] Interface Tutor: explicacion iniciada (linea 5243)")
                    return

                # 2. Raphael: 5008 ("I'm ready") -> Inicia fase de equipamiento
                if _el == 5008:
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    ses.dlg_ent = ent
                    ses.dlg_guion = g
                    ses.dlg_paso = 3
                    ses.enviar(dialogos.linea_de(g, 2, nom))
                    log.info(f"[{addr}] Raphael: jugador listo, inicia fase de equipo (linea 5014)")
                    return

                # 3. Raphael: 5011 ("Yes." confirmar abandono del tutorial)
                if _el == 5011:
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    submsg_5013 = dialogos.armar_linea(5013, 3, [], strings=[nom])
                    submsg_fin = struct.pack('<H', 0x0012) + dialogos.FIN
                    ses.enviar(submsg_5013, submsg_fin)
                    ses.dlg_ent = None
                    import clases as _cl3
                    ses.personaje.stage = 41
                    ses.personaje.tile_x, ses.personaje.tile_y = (152, 74)
                    ses.monstruos = _monstruos_de(41)
                    ses.enviar(_cl3.cambiar_mapa(41))
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id, 41, 152, 74)
                    log.info(f"[{addr}] Raphael: abandono tutorial -> enviado a Angel Lyceum (41)")
                    return

                submsgs = dialogos.respuesta_a(_el, entidad=ent, val=val) if _el else (struct.pack('<H', 0x0012) + dialogos.FIN,)
                ses.enviar(*submsgs)


                # Elecciones especiales
                if _el == 10125 and ses.personaje:
                    # Quit training con Angels' Tutor -> graduado / habilitado para elegir faccion
                    ses.personaje.faction = "Graduated"
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_faccion(ses.usuario, ses.personaje.char_id, "Graduated")
                    log.info(f"[{addr}] {ses.personaje.nombre} completo o abandono el entrenamiento; listo para faccion")
                elif _el == 10235 and ses.personaje:
                    # Confirmar en totem (Aurora, Dark City, Iron Castle, Breeze Woods)
                    totem_faccion = {
                        41: "Aurora", 150: "Aurora",
                        44: "Dark City", 122: "Dark City",
                        43: "Iron Castle", 121: "Iron Castle",
                        45: "Breeze Woods", 120: "Breeze Woods",
                    }
                    nueva_fac = totem_faccion.get(ent, "Aurora")
                    ses.personaje.faction = nueva_fac
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_faccion(ses.usuario, ses.personaje.char_id, nueva_fac)
                    log.info(f"[{addr}] {ses.personaje.nombre} eligio faccion: {nueva_fac}")
                elif _el == 5747 and ses.personaje:
                    # Cupid: Savepoint en Angel Lyceum (tile 138, 60)
                    ses.personaje.spawn_stage = 41
                    ses.personaje.spawn_x = 138
                    ses.personaje.spawn_y = 60
                    log.info(f"[{addr}] {ses.personaje.nombre} registro checkpoint con Cupid (138, 60)")
                elif _el == 20001 and ses.personaje:
                    # Teleporter Jack: East Field A1 (stage 42)
                    import clases as _cl3
                    ses.personaje.stage = 42
                    ses.personaje.tile_x, ses.personaje.tile_y = (11, 113)
                    ses.monstruos = _monstruos_de(42)
                    ses.enviar(_cl3.cambiar_mapa(42))
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id, 42, 11, 113)
                    log.info(f"[{addr}] Teleporter Jack: al East Playground (stage 42)")
                elif _el == 20003 and ses.personaje:
                    # Teleporter Shiva: West Field A1 (stage 43)
                    import clases as _cl3
                    ses.personaje.stage = 43
                    ses.personaje.tile_x, ses.personaje.tile_y = (189, 24)
                    ses.monstruos = _monstruos_de(43)
                    ses.enviar(_cl3.cambiar_mapa(43))
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id, 43, 189, 24)
                    log.info(f"[{addr}] Teleporter Shiva: al West Playground (stage 43)")
                elif 5802 <= _el <= 5806 and ses.personaje:
                    # East Playground A1..A5
                    import clases as _cl3
                    ses.personaje.stage = 42
                    ses.personaje.tile_x, ses.personaje.tile_y = (11, 113)
                    ses.monstruos = _monstruos_de(42)
                    ses.enviar(_cl3.cambiar_mapa(42))
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id, 42, 11, 113)
                    log.info(f"[{addr}] East Portal: al East Playground (stage 42)")
                elif 5807 <= _el <= 5811 and ses.personaje:
                    # West Playground A1..A5
                    import clases as _cl3
                    ses.personaje.stage = 43
                    ses.personaje.tile_x, ses.personaje.tile_y = (189, 24)
                    ses.monstruos = _monstruos_de(43)
                    ses.enviar(_cl3.cambiar_mapa(43))
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id, 43, 189, 24)
                    log.info(f"[{addr}] West Portal: al West Playground (stage 43)")
                elif _el == 5080 and ses.personaje:
                    # Director Wolay: retorno a la ciudad de faccion elegida
                    ciudades_faccion = {
                        "Aurora": (3, (150, 150)),
                        "Dark City": (26, (150, 150)),
                        "Iron Castle": (38, (41, 9)),
                        "Breeze Woods": (29, (150, 150)),
                    }
                    st_dest, tile_dest = ciudades_faccion.get(ses.personaje.faction, (3, (150, 150)))
                    import clases as _cl3
                    ses.personaje.stage = st_dest
                    ses.personaje.tile_x, ses.personaje.tile_y = tile_dest
                    ses.monstruos = _monstruos_de(st_dest)
                    ses.enviar(_cl3.cambiar_mapa(st_dest))
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id, st_dest, *tile_dest)
                    log.info(f"[{addr}] Director Wolay: retorno a {ses.personaje.faction} (stage {st_dest})")
                elif _el == 5058 and ses.personaje:
                    # Raphael (Fighting Palace): Repetir explicacion
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    g_rep = dialogos.guion_fighting_palace(0, nom)
                    ses.dlg_ent = ent
                    ses.dlg_guion = g_rep
                    ses.dlg_paso = 1
                    ses.dlg_val = 5
                    ses.enviar(dialogos.linea_de(g_rep, 0, nom))
                    log.info(f"[{addr}] Raphael (Fighting Palace): repitiendo explicacion de combate")
                    return
                elif _el == 5063 and ses.personaje:
                    # Raphael (Fighting Palace): "I'm ready to go to the Angel Lyceum."
                    # Manda la linea 5065 y luego teletransporta a Angel Lyceum (stage 41)
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    submsg_5065 = dialogos.armar_linea(5065, 5, [])
                    submsg_fin = struct.pack('<H', 0x0012) + dialogos.FIN
                    ses.enviar(submsg_5065, submsg_fin)
                    ses.dlg_ent = None
                    import clases as _cl3
                    ses.personaje.stage = 41
                    ses.personaje.tile_x, ses.personaje.tile_y = (152, 74)
                    ses.monstruos = _monstruos_de(41)
                    ses.enviar(_cl3.cambiar_mapa(41))
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id, 41, 152, 74)
                    log.info(f"[{addr}] Raphael (Fighting Palace): combate completado -> teletransportado a Angel Lyceum (41)")
                    return

                termina = any(
                    m.endswith(dialogos.FIN) or struct.unpack_from('<H', m, 0)[0] in (0x0034, 0x002B, 0x001D)
                    for m in submsgs if len(m) >= 2
                )
                if termina:
                    ses.dlg_ent = None
                else:
                    ses.dlg_ent = ent
                    ses.dlg_guion = [submsgs[0][2:]]
                    ses.dlg_paso = 1
                    if len(submsgs[0]) >= 8:
                        ses.dlg_val = struct.unpack_from('<H', submsgs[0], 6)[0]
                log.info(f"[{addr}] eligio la opcion {_i + 1}"
                         + (f" (dialogo {_el})" if _el else ""))
                return
            nom = ses.personaje.nombre if ses.personaje else 'Jugador'
            # Entrega de guantes y zapatos en Raphael antes de mostrar la linea 5015 (paso == 3 en tramo 1):
            if ent == 19 and paso == 3 and len(g) >= 7 and struct.unpack_from('<I', g[3], 0)[0] == 5015:
                cid = ses.personaje.char_id if ses.personaje else 4980
                ses.inventario = getattr(ses, 'inventario', {}) or {}
                import inventario as _iv
                import clases as _cls
                s_glov = _ranura_libre(ses.inventario, desde=20)
                ses.inventario[s_glov] = 28
                s_shoe = _ranura_libre(ses.inventario, desde=s_glov + 1)
                ses.inventario[s_shoe] = 30
                ses.enviar(*_iv.entregar(cid, 28, s_glov),
                           *_iv.entregar(cid, 30, s_shoe),
                           _iv.completo(cid, _con_oro(ses)),
                           _cls.aviso("Students' Gloves\x00Students' shoes", tipo=0, msg_id=493))
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, ses.inventario)
                log.info(f"[{addr}] Raphael: entregados guantes (slot {s_glov}) y zapatos (slot {s_shoe})")

            ses.enviar(dialogos.linea_de(g, paso, nom))
            if paso < len(g):
                ses.dlg_paso = paso + 1
                log.debug(f"[{addr}] dialogo {ent}: linea {paso + 1}")
            else:
                ses.dlg_ent = None
                # Fin de dialogo en Guide Palace (stage 51):
                if ses.personaje and ses.personaje.stage == MAPA_DEL_TUTORIAL:
                    if ent == 19:
                        ultimo_id = struct.unpack_from('<I', g[-1], 0)[0] if g else 0
                        if ultimo_id == 5005:
                            # Fin de tramo 0 -> abrir ventana de seleccion de clase (0x001D kind=12)
                            pkg_prof = struct.pack('<HIBBII', 0x001D, ent, 1, 12, 0, 0)
                            ses.enviar(pkg_prof)
                            log.info(f"[{addr}] Raphael: fin tramo 0 -> abierta ventana de seleccion de clase")
                        elif ultimo_id == 5018:
                            # Fin de fase de equipo
                            ses.personaje.tutorial = 1
                            if getattr(ses, 'usuario', None):
                                cuentas.guardar_tutorial(ses.usuario, ses.personaje.char_id, 1)
                            log.info(f"[{addr}] Raphael: fin fase de equipo (etapa 1)")
                        elif ultimo_id == 5043:
                            # Fin de fase de compra de bienes -> dar 10 de oro
                            ses.personaje.tutorial = 2
                            if getattr(ses, 'usuario', None):
                                cuentas.guardar_tutorial(ses.usuario, ses.personaje.char_id, 2)
                            if getattr(ses, 'oro', 0) < 10:
                                ses.oro = 10
                                ses.personaje.oro = 10
                                import clases as _cls
                                import inventario as _iv
                                bars, max_pts = _max_sp_info(ses.personaje)
                                ses.enviar(struct.pack('<HIBBI', 0x0013, ses.personaje.entity_id, 1, 6, 10),
                                           _cls.aviso("10 Gold", tipo=0, msg_id=_cls.MSG_PAGO),
                                           _iv.completo(ses.personaje.char_id, _con_oro(ses)),
                                           _iv.stats(ses.inventario, ses.personaje.habilidades,
                                                     hp=ses.personaje.hp, hp_max=ses.personaje.hp_max,
                                                     mp=ses.personaje.mp, mp_max=ses.personaje.mp_max,
                                                     oro=10, sp=getattr(ses, 'sp', None), sp_max=bars))
                                if getattr(ses, 'usuario', None):
                                    cuentas.guardar_oro(ses.usuario, ses.personaje.char_id, 10)
                            log.info(f"[{addr}] Raphael: fin etapa 2 -> 10 de oro otorgados")
                        elif ultimo_id in (5047, 5054):
                            # Fin de tramo 3 (examen completado) -> consumir examen y teletransportar a Fighting Palace (57)
                            slot_1386 = next((s for s, it in ses.inventario.items() if it == 1386), None)
                            if slot_1386 is not None:
                                del ses.inventario[slot_1386]
                            import inventario as _iv
                            import clases as _cls
                            ses.enviar(_iv.completo(ses.personaje.char_id, _con_oro(ses)))
                            ses.personaje.tutorial = 3
                            if getattr(ses, 'usuario', None):
                                cuentas.guardar_inventario(ses.usuario, ses.personaje.char_id, ses.inventario)
                                cuentas.guardar_tutorial(ses.usuario, ses.personaje.char_id, 3)
                            ses.personaje.stage = 57
                            ses.personaje.tile_x, ses.personaje.tile_y = (216, 37)
                            ses.monstruos = _monstruos_de(57)
                            ses.enviar(_cls.cambiar_mapa(57))
                            if getattr(ses, 'usuario', None):
                                cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id, 57, 216, 37)
                            log.info(f"[{addr}] Raphael: examen completado -> teletransportado a Fighting Palace (57)")
                        else:
                            log.info(f"[{addr}] Raphael: dialogo terminado (ultimo_id={ultimo_id})")
                    else:
                        log.info(f"[{addr}] dialogo con la entidad {ent} terminado")
                else:
                    log.info(f"[{addr}] dialogo con la entidad {ent} terminado")
            return

        if opcode == 0x0007 and ses.rol == 'mundo' and cuerpo:
            log.debug(f"[{addr}] se gira hacia la direccion {cuerpo[0]}")
            return

        # --- Acciones de personaje: Sentarse / Levantarse con tecla Insert (0x0016) ---
        if opcode == 0x0016 and ses.rol == 'mundo' and len(cuerpo) >= 4:
            accion = struct.unpack_from('<I', cuerpo, 0)[0]
            if accion == 4 and ses.personaje:
                yo = ses.personaje.entity_id
                ses.sentado = not getattr(ses, 'sentado', False)
                act_code = 8 if ses.sentado else 0
                ses.enviar(struct.pack('<HIII', 0x000A, yo, 0, act_code))
                log.info(f"[{addr}] personaje {'se sento' if ses.sentado else 'se levanto'} (accion={act_code})")
                return

        if opcode == 0x0004 and d:
            ses.ultimo_movimiento = time.time()
            if getattr(ses, 'sentado', False):
                ses.sentado = False
                if ses.personaje:
                    ses.enviar(struct.pack('<HIII', 0x000A, ses.personaje.entity_id, 0, 0))
            # Ruta con waypoints. Se confirma el ultimo tramo.
            if not d.get('path'):
                return
            dst = d['path'][-1]
            MOVE = Msg.registry[(0x0005, 's2c', '*')]
            ACK = Msg.registry[(0x006D, 's2c', '*')]
            ses.enviar(ACK.build(),
                       MOVE.build(entity_id=ses.entity_id or 1001,
                                  cur_x=d['cur_x'], cur_y=d['cur_y'],
                                  dst_x=dst['x'], dst_y=dst['y'], speed=110))
            # Anotar donde queda. Las coordenadas del cliente van en pixeles y
            # el tile mide 32: 2640 -> 82 y 2672 -> 83, que es justo el punto
            # de aparicion de Guide Palace. Se guarda al desconectar, no en
            # cada paso, para no escribir en disco varias veces por segundo.
            if ses.personaje:
                ses.personaje.tile_x = dst['x'] // 32
                ses.personaje.tile_y = dst['y'] // 32
                import clases as _cl3
                nuevo_stage, nuevo_tile = None, None
                tx, ty = ses.personaje.tile_x, ses.personaje.tile_y
                if ses.personaje.stage == 41:
                    # Portal Este en Lyceum -> abrir dialogo oficial si no esta abierto
                    if tx >= 256 and ty <= 17:
                        if getattr(ses, 'dlg_ent', None) != 896:
                            import dialogos
                            ses.dlg_ent, ses.dlg_paso = 896, 1
                            ses.dlg_guion = [dialogos.armar_linea(5801, 4, [5802, 5803, 5804, 5805, 5806, 5812])[2:]]
                            ses.dlg_val = 4
                            ses.enviar(dialogos.linea_de(ses.dlg_guion, 0, ses.personaje.nombre))
                            log.info(f"[{addr}] menu de East Portal abierto por posicion ({tx},{ty})")
                    # Portal Oeste en Lyceum -> abrir dialogo oficial si no esta abierto
                    elif tx <= 32 and ty >= 126:
                        if getattr(ses, 'dlg_ent', None) != 897:
                            import dialogos
                            ses.dlg_ent, ses.dlg_paso = 897, 1
                            ses.dlg_guion = [dialogos.armar_linea(5801, 4, [5807, 5808, 5809, 5810, 5811, 5812])[2:]]
                            ses.dlg_val = 4
                            ses.enviar(dialogos.linea_de(ses.dlg_guion, 0, ses.personaje.nombre))
                            log.info(f"[{addr}] menu de West Portal abierto por posicion ({tx},{ty})")
                elif ses.personaje.stage == 42:
                    # Retorno desde East Playground (42) a Lyceum (41) al pisar el portal (11, 113)
                    if tx <= 15 and 106 <= ty <= 120:
                        nuevo_stage, nuevo_tile = 41, (257, 15)
                elif ses.personaje.stage == 43:
                    # Retorno desde West Playground (43) a Lyceum (41) al pisar el portal (189, 24)
                    if tx >= 185 and 18 <= ty <= 30:
                        nuevo_stage, nuevo_tile = 41, (28, 131)

                if nuevo_stage:
                    ses.personaje.stage = nuevo_stage
                    ses.personaje.tile_x, ses.personaje.tile_y = nuevo_tile
                    ses.monstruos = _monstruos_de(nuevo_stage)
                    ses.enviar(_cl3.cambiar_mapa(nuevo_stage))
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id,
                                             nuevo_stage, *nuevo_tile)
                    log.info(f"[{addr}] transicion de mapa: stage {nuevo_stage} tile {nuevo_tile}")
                    return
            log.debug(f"[{addr}] movimiento ({d['cur_x']},{d['cur_y']}) -> "
                      f"({dst['x']},{dst['y']}) via {d['n']} waypoints")

    async def archivos(self, reader, writer):
        """File server (fport en server.xml). Todavia no responde: graba lo que
        el cliente pide, que es justo lo que hace falta para implementarlo."""
        addr = writer.get_extra_info('peername')
        log.info(f"[archivos {addr}] conectado")
        grab = Grabador(addr, self.fport, bytes(16))
        import archivos
        from framing import HDR, decode_header, submessages, build_frame, pack_submessages, SEQ_HELLO
        # El servidor de archivos tambien manda HELLO al conectar. Se comprobo
        # contra una captura real: frame 0 con seq=0xFFFF y 134 bytes, igual
        # que login y mundo. El mio no mandaba nada hasta que le pedian algo,
        # asi que el cliente esperaba un handshake que nunca llegaba.
        _ph = pathlib.Path(__file__).parent / 'plantillas' / 'hello_archivos.bin'
        if _ph.exists():
            _hf = build_frame(_ph.read_bytes(), SEQ_HELLO)
            grab.salida(_hf)
            writer.write(_hf)
            await writer.drain()
            log.info("[archivos %s] HELLO enviado (%s B)", addr, len(_hf))
        buf, seq = bytearray(), 1
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                grab.entrada(data)
                buf.extend(data)
                while len(buf) >= HDR:
                    h = decode_header(buf, 0)
                    if h['length'] == 0 or h['length'] > 0x10000:
                        del buf[0]; continue
                    if len(buf) < h['wire']:
                        break
                    cuerpo = bytes(buf[HDR:h['wire']]); del buf[:h['wire']]
                    for op, b in submessages(cuerpo[:h['length']])[0]:
                        nom = archivos.nombre_pedido(b)
                        if not nom:
                            # El binario dice que la direccion del MUNDO sale
                            # de +96/+112 de la entrada de servidor, que es el
                            # par fip/fport del server.xml -- o sea ESTE puerto.
                            # Si llega algo que no es un pedido de archivo,
                            # probablemente sea la sesion de mundo.
                            log.warning(f"[archivos {addr}] 0x{op:04X} {len(b)}B "
                                        f"NO es pedido de archivo: {b[:32].hex(' ')}")
                            log.warning(f"[archivos {addr}] ¿es la sesion de MUNDO "
                                        f"llegando por fport?")
                            continue
                        log.info(f"[archivos {addr}] 0x{op:04X} pide '{nom}'")
                        resp = build_frame(
                            pack_submessages([archivos.respuesta_avatar(b)]), seq)
                        seq = 1 if seq >= 0x7FFE else seq + 1
                        grab.salida(resp)
                        writer.write(resp)
                        await writer.drain()
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            base, nc, ns = grab.cerrar()
            log.info(f"[archivos {addr}] desconectado -> logs/sesiones/{base}_*.bin")
            writer.close()

    async def correr(self):
        import functools
        srv = await asyncio.start_server(
            functools.partial(self.cliente, rol='login'), self.host, self.port)
        log.info(f"servidor de LOGIN en {self.host}:{self.port}")
        wsrv = await asyncio.start_server(
            functools.partial(self.cliente, rol='mundo'), self.host, self.wport)
        log.info(f"servidor de MUNDO en {self.host}:{self.wport}")
        tareas = [srv.serve_forever(), wsrv.serve_forever()]
        try:
            fsrv = await asyncio.start_server(self.archivos, self.host, self.fport)
            log.info(f"servidor de archivos en {self.host}:{self.fport}")
            tareas.append(fsrv.serve_forever())
        except OSError as e:
            log.warning(f"no se pudo abrir el puerto de archivos {self.fport}: {e}")
        log.info("server.xml del cliente ya apunta aca (ip=127.0.0.1 port=16768)")

        # SEÑUELOS: el binario muestra que la ip y el puerto del mundo NO
        # salen del redirect sino de la lista de servidores (sub_51A370 los
        # lee de +64 y +80 de una entrada de 372 bytes). Para saber a donde
        # intenta ir el cliente de verdad, se abren los puertos vecinos y se
        # registra cualquier conexion.
        async def senuelo(r, w, p):
            a = w.get_extra_info('peername')
            log.warning("*** EL CLIENTE CONECTO AL PUERTO %s (desde %s) ***", p, a)
            try:
                d = await asyncio.wait_for(r.read(4096), 3)
                log.warning("    mando %s bytes: %s", len(d), d[:48].hex(' ') if d else '(nada)')
            except asyncio.TimeoutError:
                log.warning("    se quedo esperando respuesta")
            w.close()

        usados = {self.port, self.wport, self.fport}
        # Se agregan los valores POR DEFECTO que trae el binario
        #   dword_91AA6C = 6768   y   dword_91AA80 = 1234
        # mas los puertos de mundo vistos en capturas reales.
        for pu in (list(range(16760, 16790)) + [1234, 6768, 21237, 21239]
                   + list(range(24125, 24160)) + list(range(29995, 30012))):
            if pu in usados:
                continue
            try:
                # Escuchar en TODAS las interfaces, no solo loopback: si el
                # cliente intenta conectar a la IP de red en vez de a
                # 127.0.0.1, un senuelo atado solo a loopback no lo ve y el
                # cliente se queda colgado esperando (que es lo que pasa).
                sx = await asyncio.start_server(
                    functools.partial(senuelo, p=pu), '0.0.0.0', pu)
                tareas.append(sx.serve_forever())
            except OSError:
                pass
        log.info("senuelos abiertos en los puertos vecinos")
        log.info("las sesiones se graban en logs/sesiones/ para poder analizarlas")
        await asyncio.gather(*tareas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=16768)
    ap.add_argument('--wport', type=int, default=16769,
                    help='puerto del servidor de mundo (destino del redirect)')
    ap.add_argument('--fport', type=int, default=21238,
                    help='puerto del servidor de archivos (fport en server.xml)')
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    try:
        asyncio.run(Servidor(a.host, a.port, a.fport, a.wport).correr())
    except KeyboardInterrupt:
        log.info("detenido")


if __name__ == '__main__':
    main()
