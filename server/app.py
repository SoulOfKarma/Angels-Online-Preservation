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
import sys
import pathlib
import pathlib
import collections

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
    import login as _lg
    ses.enviar(*_lg.poblar(clases.STAGE_LYCEUM))
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
        if ranura == inv.RANURA_ORO:
            out.append((ranura, item_id, getattr(ses, 'oro', 0)))
        else:
            out.append((ranura, item_id, 1))
    return out


def _nombre_item(item_id: int) -> str:
    """Nombre del item para el cartel de 'obtuviste X'."""
    import sqlite3
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    try:
        con = sqlite3.connect(db)
        r = con.execute('select "基本名稱" from item where id=?',
                        (str(item_id),)).fetchone()
        return r[0] if r and r[0] else f'Item{item_id}'
    except Exception:
        return f'Item{item_id}'


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

                salida = ses.drenar()
                if salida and getattr(ses, 'writer', None):
                    if getattr(ses, 'grab', None):
                        ses.grab.salida(salida)
                    ses.writer.write(salida)
                    await ses.writer.drain()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.debug(f"patrulla lyceum detenida: {e}")

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
            ses.enviar(inv.stats(ses.inventario))
            # El arbol de habilidades tambien al entrar, no solo al elegir
            # clase: si no, al reconectar el panel vuelve a salir lleno de
            # interrogantes.
            if p.habilidades:
                import clases as _cl
                _ids = [h[0] for h in p.habilidades]
                ses.enviar(_cl.arbol(_ids))
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
                                        ses.enviar(_cb.empieza_ataque(m.entity_id),
                                                   *_cb.numero_de_dano(m.entity_id, yo, suyo, ataque=656, efecto=ef_atk),
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
            import time
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
                    # Si es una habilidad de ataque, no se puede autocastear
                    if mag.get('es_ataque'):
                        return

                    mp_coste = mag.get('mp', 0)
                    sp_coste = mag.get('sp', _cb.COSTE_GOLPE)
                    if ses.personaje and mp_coste > 0:
                        if ses.personaje.mp < mp_coste:
                            log.info(f"[{addr}] MP insuficiente ({ses.personaje.mp}/{mp_coste}) para habilidad {tipo}")
                            return
                        ses.personaje.mp = max(0, ses.personaje.mp - mp_coste)
                        pct_mp = max(0, min(100, round(100 * ses.personaje.mp / ses.personaje.mp_max)))
                        ses.enviar(_cb.atributo(yo, pct_mp, 1))

                    ses.esfuerzo = max(0, getattr(ses, 'esfuerzo', 900) - sp_coste)
                    ef = _cb.efecto_de_ataque(tipo)
                    import clases as _cl
                    pkgs = [
                        _cb.empieza_ataque(yo),
                        _cb.atributo(yo, ses.esfuerzo, _cb.KIND_SP),
                    ]
                    # Si es una habilidad de curacion (Cure Spell, etc.)
                    if mag.get('es_cura') and ses.personaje:
                        cura = max(10, abs(mag.get('hp', 0)))
                        ses.personaje.hp = min(ses.personaje.hp_max, ses.personaje.hp + cura)
                        pkgs.append(_cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP))
                        pkgs.extend(_cb.efecto_curacion(yo, yo, cura, efecto=ef))
                        if getattr(ses, 'usuario', None):
                            cuentas.guardar_progreso(ses.usuario, ses.personaje.char_id,
                                                     ses.personaje.nivel, ses.personaje.exp,
                                                     ses.personaje.hp, ses.personaje.mp,
                                                     ses.personaje.habilidades,
                                                     hp_max=ses.personaje.hp_max, mp_max=ses.personaje.mp_max)
                        log.info(f"[{addr}] habilidad curativa {tipo} curó {cura} HP ({ses.personaje.hp}/{ses.personaje.hp_max})")
                    else:
                        # Buff activo sobre si mismo: solo efecto visual
                        pkgs.extend(_cb.efecto_curacion(yo, yo, 0, efecto=ef))

                    cd_ms = mag.get('cd_ms', 1000)
                    dur_ms = mag.get('dur_ms', 0)
                    if cd_ms > 0:
                        pkgs.append(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, cd_ms))
                        import asyncio
                        try:
                            asyncio.get_event_loop().call_later(cd_ms / 1000.0, lambda: ses.enviar(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, 0)))
                        except Exception:
                            pass
                    if dur_ms > 0:
                        pkgs.append(struct.pack('<HIBBII', 0x001D, yo, 1, 4, tipo, dur_ms))
                        import asyncio
                        try:
                            asyncio.get_event_loop().call_later(dur_ms / 1000.0, lambda: ses.enviar(struct.pack('<HIBBII', 0x001D, yo, 1, 4, tipo, 0)))
                        except Exception:
                            pass
                    ses.enviar(*pkgs)
                    # Resetear animacion tras 0.6 segundos para volver a postura de reposo
                    import asyncio
                    try:
                        asyncio.get_event_loop().call_later(0.6, lambda: ses.enviar(
                            struct.pack('<HIII', 0x000A, yo, 0, 0)
                        ))
                    except Exception:
                        pass
                    log.info(f"[{addr}] habilidad {tipo} ejecutada sobre si mismo ({mag.get('nombre')}) [cd={cd_ms}ms, dur={dur_ms}ms]")
                    return
                log.debug(f"[{addr}] ataque a la entidad {objetivo}: no es un monstruo conocido")
                return

            if not m.vivo:
                return

            # El dano sale del ataque del jugador mas bonos pasivos menos defensa del bicho
            import inventario as _iv
            habs = ses.personaje.habilidades if ses.personaje else None
            st = _iv.stats(ses.inventario, habs)
            ataque = struct.unpack_from('<I', st, 2 + 20 + 4)[0]

            # Si se usa una habilidad activa (ej. Slicing Hit, Spear Hacking, etc.)
            dano_extra = 0
            if tipo != _cb.ATAQUE_NORMAL:
                mag = _cb.datos_magia(tipo)
                mp_coste = mag.get('mp', 0)
                if ses.personaje and mp_coste > 0:
                    if ses.personaje.mp < mp_coste:
                        log.info(f"[{addr}] MP insuficiente ({ses.personaje.mp}/{mp_coste}) para habilidad {tipo}")
                        return
                    ses.personaje.mp = max(0, ses.personaje.mp - mp_coste)
                    pct_mp = max(0, min(100, round(100 * ses.personaje.mp / ses.personaje.mp_max)))
                    ses.enviar(_cb.atributo(yo, pct_mp, 1))
                dano_extra = abs(mag.get('hp', 0))
                atk_magic = tipo
                atk_efecto = _cb.efecto_de_ataque(tipo)
                # Enviar cooldown de la habilidad activa
                cd_ms = mag.get('cd_ms', 1000)
                if cd_ms > 0:
                    ses.enviar(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, cd_ms))
                    import asyncio
                    try:
                        asyncio.get_event_loop().call_later(cd_ms / 1000.0, lambda: ses.enviar(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, 0)))
                    except Exception:
                        pass
            else:
                atk_magic, atk_efecto = _cb.ataque_estandar_arma(arma_puesta)

            dano = m.recibir(ataque + dano_extra)
            # Marcar al monstruo en combate con el jugador
            m.en_combate_con = yo
            m.ultimo_ataque = time.time()

            ses.esfuerzo = max(0, getattr(ses, 'esfuerzo', 900) - _cb.COSTE_GOLPE)
            ses.enviar(_cb.atributo(objetivo, m.porcentaje),
                       _cb.empieza_ataque(yo),
                       *_cb.numero_de_dano(yo, objetivo, dano, atk_magic, efecto=atk_efecto),
                       _cb.atributo(yo, ses.esfuerzo, _cb.KIND_ESFUERZO))
            if m.vivo:
                # Contraataca inmediatamente si esta en rango
                dist_m = max(abs(m.tile_x - ses.personaje.tile_x), abs(m.tile_y - ses.personaje.tile_y)) if ses.personaje else 1
                if dist_m <= getattr(m, 'atk_range', 1):
                    suyo = m.pegar()
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

                        pct = max(1, round(100 * ses.personaje.hp / ses.personaje.hp_max))
                        ef_mon = m.proj_ef if m.proj_ef > 0 else 148
                        ses.enviar(_cb.empieza_ataque(objetivo),
                                   *_cb.numero_de_dano(objetivo, yo, suyo, ataque=656, efecto=ef_mon),
                                   _cb.atributo(yo, pct, _cb.VIDA))
                    else:
                        ef_mon = m.proj_ef if m.proj_ef > 0 else 148
                        ses.enviar(_cb.empieza_ataque(objetivo),
                                   *_cb.numero_de_dano(objetivo, yo, suyo, ataque=656, efecto=ef_mon))
                log.debug(f"[{addr}] pego {dano} al {m.nombre} "
                          f"({m.porcentaje}%), contraataque procesado")
                return


            # --- Monstruo Muerto: Avisar muerte, Despawn con animacion, Respawn, EXP y Botin ---
            import clases as _cl
            # 1. Avisar muerte del monstruo (vida 0) y evento de muerte (tipo 7)
            # El monstruo reproduce su animacion de muerte en el cliente
            ses.enviar(_cb.atributo(objetivo, 0, _cb.VIDA),
                       _cb.muerte_monstruo(objetivo, yo))

            # Despawnear a los 2.5 segundos para que se vea la animacion de morir completa
            import asyncio
            try:
                asyncio.get_event_loop().call_later(2.5, lambda: ses.enviar(_cb.despawn_monstruo(objetivo)))
            except Exception:
                pass

            # Programar respawn del monstruo en 20 segundos
            def _respawn():
                if not getattr(m, 'vivo', False):
                    m.revivir()
                    import login as _lg
                    # Mandar aparicion del monstruo vivo de nuevo en su spawn_tile
                    ses.enviar(_lg._npc_spawn(objetivo, m.npc_type, m.nombre, (m.tile_x, m.tile_y), klass=1))
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
                exp_siguiente = _cb.exp_para_nivel(p.nivel + 1)
                subio_nivel = False
                if p.exp >= exp_siguiente:
                    p.nivel += 1
                    p.hp_max += 25
                    p.hp = p.hp_max
                    p.mp_max += 15
                    p.mp = p.mp_max
                    subio_nivel = True
                    salida_combate.append(_cl.aviso(f"Level Up! Reached Level {p.nivel}!", tipo=0, msg_id=_cl.MSG_ITEM))
                    salida_combate.append(_cb.atributo(yo, p.hp, _cb.KIND_HP))
                    salida_combate.append(_cb.atributo(yo, p.mp, _cb.KIND_MP))
                    salida_combate.append(_iv.stats(ses.inventario, p.habilidades))
                    log.info(f"[{addr}] {p.nombre} SUBIO A NIVEL {p.nivel}!")

                # Paquetes oficiales nativos para EXP y actualizacion de barra
                # 0x000B kind=1 genera 'Obtain X Exp.' en pantalla y chat
                salida_combate.append(_cb.exp_paquete(objetivo, exp_ganada, 1))
                # 0x0013 kind=4 ACTUALIZA LA BARRA DE EXPERIENCIA EN LA UI
                salida_combate.append(_cb.atributo(yo, p.exp, _cb.KIND_EXP))

                # Progreso de habilidades en el personaje respetando los topes
                SKILLS_PRODUCTOR = {1, 2, 3, 4, 5, 6, 7, 8}
                if p.habilidades:
                    nuevas_habs = []
                    subio_alguna_hab = False
                    for h in p.habilidades:
                        sid, slv, sexp = h[0], h[1], h[2]
                        max_lv = (p.nivel + 11) if sid in SKILLS_PRODUCTOR else p.nivel
                        # La primera habilidad (arma activa) y defensas reciben progreso
                        if sid == p.habilidades[0][0]:
                            sexp += sk_exp_ganada
                            req = slv * 100
                            while sexp >= req and slv < max_lv:
                                sexp -= req
                                slv += 1
                                req = slv * 100
                                subio_alguna_hab = True
                            if slv >= max_lv:
                                sexp = min(sexp, req)
                            # Paquete nativo de Skill EXP: actualiza barra de habilidad y chat '[Skill] has obtained X Exp.'
                            salida_combate.append(_cb.skill_exp_paquete(yo, sk_exp_ganada))
                        nuevas_habs.append((sid, slv, sexp))
                    p.habilidades = nuevas_habs
                    if subio_alguna_hab:
                        salida_combate.append(_cl.arbol(p.habilidades))

                if getattr(ses, 'usuario', None):
                    cuentas.guardar_progreso(ses.usuario, p.char_id, p.nivel, p.exp,
                                             p.hp, p.mp, p.habilidades,
                                             hp_max=p.hp_max, mp_max=p.mp_max)
                    cuentas.guardar_oro(ses.usuario, p.char_id, ses.oro)

            salida_combate.append(_cl.aviso(f'{oro} Gold', tipo=0, msg_id=_cl.MSG_ITEM))


            # 5. Drops de items al inventario (con apilamiento de consumibles)
            drops = _cb.botin_items(m.npc_type)
            bolsa = getattr(ses, 'inventario', {})
            for item_drop, cant in drops:
                r_slot = None
                if _iv.es_apilable(item_drop):
                    for s, it_id in bolsa.items():
                        if s >= 20 and it_id == item_drop:
                            r_slot = s
                            break
                if r_slot is None:
                    r_slot = _ranura_libre(bolsa, desde=20)
                    bolsa[r_slot] = item_drop
                salida_combate.append(_cl.aviso(_nombre_item(item_drop), tipo=0, msg_id=_cl.MSG_ITEM))
                salida_combate.extend(_iv.entregar(cid, item_drop, r_slot))

            salida_combate.append(_iv.completo(cid, _con_oro(ses)))
            ses.enviar(*salida_combate)
            if ses.personaje and getattr(ses, 'usuario', None):
                cuentas.guardar_inventario(ses.usuario, cid, bolsa)

            log.info(f"[{addr}] mato un {m.nombre} (entidad {objetivo}); "
                     f"+{exp_ganada} exp, +{sk_exp_ganada} skill exp, +{oro} oro, {len(drops)} items")
            return

        # --- el cliente pide el mapa nuevo -------------------------------
        # Tras un 0x000C el cliente contesta con un 0x0009 vacio y espera la
        # secuencia de entrada otra vez, ya con la ficha en el mapa nuevo.
        if opcode == 0x0009 and ses.rol == 'mundo' and ses.personaje:
            import inventario as _iv2
            import clases as _cl2
            p = ses.personaje
            # Los monstruos son los del mapa NUEVO. Sin esto, al llegar al
            # Lyceum se seguia con los de Guide Palace (ninguno) y no se podia
            # atacar nada.
            ses.monstruos = _monstruos_de(p.stage)
            for sub in secuencia(p):
                ses.enviar(sub)
            ses.enviar(_iv2.stats(ses.inventario))
            if p.habilidades:
                ses.enviar(_cl2.arbol([h[0] for h in p.habilidades]))
            ses.enviar(struct.pack('<HIII', 0x0003, p.entity_id,
                                   p.tile_x, p.tile_y))
            log.info(f"[{addr}] mapa recargado: stage {p.stage} "
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
            ses.enviar(*salida)
            if ses.personaje:
                ses.personaje.habilidades = [(sid, 1, 0) for sid in ids]
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_habilidades(
                        ses.usuario, ses.personaje.char_id,
                        ses.personaje.habilidades)
            log.info(f"[{addr}] CLASE ELEGIDA: "
                     + ', '.join(f'{clases.nombre(i)}({i})' for i in ids)
                     + (f" | hechizos: {', '.join(n for _, n in hechizos)}"
                        if hechizos
                        else " | SIN hechizos de nivel 1 para esa rama"))
            # Entregar lo que da la clase y anotar el class_id. Ambas cosas
            # estan medidas del servidor real, no deducidas.
            import inventario as _iv
            regalo = clases.regalo(ids)
            if regalo and getattr(ses, 'inventario', None) is not None:
                cid = ses.personaje.char_id if ses.personaje else 4980
                for ranura, item_id in regalo:
                    if ranura not in ses.inventario:
                        ses.inventario[ranura] = item_id
                        ses.enviar(clases.aviso(_nombre_item(item_id),
                                                tipo=0, msg_id=clases.MSG_ITEM))
                        # Dos 0x001B por item: es lo que refresca el panel en
                        # caliente. Con 0x001A los items salian en el chat
                        # pero el inventario seguia vacio hasta reconectar.
                        ses.enviar(*_iv.entregar(cid, item_id, ranura))
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, ses.inventario)
                log.info(f"[{addr}] entregado: "
                         + ', '.join(f'{i} en la ranura {r}' for r, i in regalo))
            _cid = clases.class_id(ids[0])
            if _cid is not None and ses.personaje and getattr(ses, 'usuario', None):
                cuentas.guardar_clase(ses.usuario, ses.personaje.char_id, _cid)
                log.info(f"[{addr}] class_id {_cid} guardado (se vera en el "
                         f"selector la proxima vez que entres)")

            # Reenviar la ficha para que el cambio se vea EN EL MOMENTO.
            # Sin esto el panel sigue mostrando lo de antes hasta que se
            # cierra y se vuelve a abrir el cliente.
            if ses.personaje:
                from login import _ficha, _cargar_secuencia
                import login as _lg
                if _lg._SEC is None:
                    _lg._SEC = _cargar_secuencia()
                base = next(m['datos'] for m in _lg._SEC if m['opcode'] == 0x0002)
                ses.enviar(_ficha(ses.personaje, base))
            log.info(f"[{addr}] (los stats de la clase todavia no se calculan; "
                     f"skill.xml trae los bonus, ver server/clases.py)")
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
                    salida.append(inv.stats(bolsa))
                ses.enviar(*salida)
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, ses.personaje.char_id, bolsa)
                log.info(f"[{addr}] swap ranuras {org} ({it_org}) <-> {dst} ({it_dst})")
                return

            it = bolsa.pop(org)
            bolsa[dst] = it
            salida = [inv.movimiento(org, dst, cid, it, inv.instancia_de(cid, it))]
            if inv.es_equipo(org) or inv.es_equipo(dst):
                salida.append(inv.stats(bolsa))
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
                    inv.stats(bolsa)
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

                habs = ses.personaje.habilidades if ses.personaje else None
                salida = [
                    inv.completo(cid, _con_oro(ses)),
                    inv.stats(bolsa, habs)
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
                    salida.append(_c.aviso(f"Recovered {curado} HP", tipo=0, msg_id=_c.MSG_ITEM))
                if 'mp' in ef_con:
                    rec_mp = ef_con['mp']
                    ses.personaje.mp = min(ses.personaje.mp_max, ses.personaje.mp + rec_mp)
                    salida.append(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))
                    salida.append(_c.aviso(f"Recovered {rec_mp} MP", tipo=0, msg_id=_c.MSG_ITEM))
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
            etapa = ses.personaje.tutorial if ses.personaje else 0
            g = dialogos.guion_etapa(ent, etapa)
            if not g:
                log.debug(f"[{addr}] clic en la entidad {ent}: sin dialogo conocido")
                return
            nom = ses.personaje.nombre if ses.personaje else 'Jugador'
            ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g, 0
            ses.dlg_val = 4
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
                    # Confirmar en totem (41 Aurora, 44 Dark City, 43 Iron, 45 Breeze)
                    totem_faccion = {41: "Aurora", 44: "Dark City", 43: "Iron Castle", 45: "Breeze Woods"}
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
                    import login as _lg
                    ses.personaje.stage = 42
                    ses.personaje.tile_x, ses.personaje.tile_y = (11, 113)
                    ses.monstruos = _monstruos_de(42)
                    ses.enviar(_cl3.cambiar_mapa(42))
                    ses.enviar(*_lg.poblar(42))
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id, 42, 11, 113)
                    log.info(f"[{addr}] Teleporter Jack: al East Playground (stage 42)")
                elif _el == 20003 and ses.personaje:
                    # Teleporter Shiva: West Field A1 (stage 43)
                    import clases as _cl3
                    import login as _lg
                    ses.personaje.stage = 43
                    ses.personaje.tile_x, ses.personaje.tile_y = (189, 24)
                    ses.monstruos = _monstruos_de(43)
                    ses.enviar(_cl3.cambiar_mapa(43))
                    ses.enviar(*_lg.poblar(43))
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id, 43, 189, 24)
                    log.info(f"[{addr}] Teleporter Shiva: al West Playground (stage 43)")
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
                    import login as _lg
                    ses.personaje.stage = st_dest
                    ses.personaje.tile_x, ses.personaje.tile_y = tile_dest
                    ses.monstruos = _monstruos_de(st_dest)
                    ses.enviar(_cl3.cambiar_mapa(st_dest))
                    ses.enviar(*_lg.poblar(st_dest))
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id, st_dest, *tile_dest)
                    log.info(f"[{addr}] Director Wolay: retorno a {ses.personaje.faction} (stage {st_dest})")

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
            ses.enviar(dialogos.linea_de(g, paso, nom))
            if paso < len(g):
                ses.dlg_paso = paso + 1
                log.debug(f"[{addr}] dialogo {ent}: linea {paso + 1}")
            else:
                ses.dlg_ent = None
                # aparece. Mandarlo tras cualquier dialogo hacia que todos
                # los NPC abrieran la ventana de clases.
                # Angel Aide vende el examen al terminar su dialogo. Todavia
                # no se sabe que mensaje abre la ventana de tienda, asi que la
                # compra se resuelve aqui: si lleva el dinero, se le cobra y
                # se le entrega. No es como lo hace el juego, pero al menos el
                # examen se PAGA en vez de aparecer solo.
                import clases as _cls
                # Ya no se vende al cerrar el dialogo: el jugador compra en la
                # ventana de tienda del cliente, que manda su 0x0027. Hacerlo
                # aqui cobraba el examen sin abrir nada, que es justo lo que
                # el jugador reportaba.
                # Al terminar un tramo, el tutorial avanza al siguiente. Pero
                # solo si se cumple lo que ese tramo pedia: sin el examen en la
                # mochila, Raphael no pasa del tramo 2.
                if ses.personaje and ent in dialogos.NOMBRE_POR_ENTIDAD:
                    tope = dialogos.etapas(ent)
                    _sig = ses.personaje.tutorial + 1
                    _falta = _cls.REQUISITO_ETAPA.get(_sig)
                    if _sig == _cls.ETAPA_PIDE_CLASE and not ses.personaje.habilidades:
                        log.info(f"[{addr}] tutorial: no pasa a la etapa {_sig}, "
                                 f"todavia no eligio clase")
                    elif _falta and _falta not in (getattr(ses, 'inventario', {}) or {}).values():
                        log.info(f"[{addr}] tutorial: no pasa a la etapa {_sig}, "
                                 f"le falta el item {_falta}")
                    elif ses.personaje.tutorial < tope - 1:
                        ses.personaje.tutorial += 1
                        if getattr(ses, 'usuario', None):
                            cuentas.guardar_tutorial(ses.usuario,
                                                     ses.personaje.char_id,
                                                     ses.personaje.tutorial)
                        log.info(f"[{addr}] tutorial: etapa "
                                 f"{ses.personaje.tutorial} de {tope - 1}")
                        _premio(self, ses, addr, ses.personaje.tutorial)
                        if (ent == ENTIDAD_MAESTRO_CLASE
                                and ses.personaje.tutorial >= tope - 1):
                            _final_tutorial(ses, addr)
                    elif (ent == ENTIDAD_MAESTRO_CLASE
                          and ses.personaje.stage != _cls.STAGE_LYCEUM):
                        # Terminado el tutorial, Angel Raphael manda al Lyceum.
                        ses.personaje.stage = _cls.STAGE_LYCEUM
                        ses.personaje.tile_x, ses.personaje.tile_y = _cls.TILE_LYCEUM
                        ses.monstruos = _monstruos_de(_cls.STAGE_LYCEUM)
                        ses.enviar(_cls.cambiar_mapa(_cls.STAGE_LYCEUM))
                        import login as _lg
                        ses.enviar(*_lg.poblar(_cls.STAGE_LYCEUM))
                        if getattr(ses, 'usuario', None):
                            cuentas.guardar_mapa(ses.usuario,
                                                 ses.personaje.char_id,
                                                 _cls.STAGE_LYCEUM,
                                                 *_cls.TILE_LYCEUM)
                        log.info(f"[{addr}] tutorial terminado: al Angel "
                                 f"Lyceum (stage {_cls.STAGE_LYCEUM})")
                sin_clase = not (ses.personaje and ses.personaje.habilidades)
                if ent == ENTIDAD_MAESTRO_CLASE and sin_clase:
                    ses.enviar(struct.pack('<HIBBII', 0x001D,
                                           ses.entity_id or 1001, 1, 12, 0, 0))
                    log.info(f"[{addr}] dialogo con Angel Raphael terminado; "
                             f"ya puede elegir clase")
                else:
                    log.info(f"[{addr}] dialogo con la entidad {ent} terminado")
            return

        if opcode == 0x0007 and ses.rol == 'mundo' and cuerpo:
            log.debug(f"[{addr}] se gira hacia la direccion {cuerpo[0]}")
            return

        if opcode == 0x0004 and d:
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
                    # Portal Este en Lyceum -> al East Playground (stage 42)
                    if tx >= 257 and ty <= 16:
                        nuevo_stage, nuevo_tile = 42, (18, 113)
                    # Portal Oeste en Lyceum -> al West Playground (stage 43)
                    elif tx <= 20 and ty >= 134:
                        nuevo_stage, nuevo_tile = 43, (180, 25)
                elif ses.personaje.stage == 42:
                    # Retorno desde East Playground (42) a Lyceum (41) al pisar el portal (11, 113)
                    if tx <= 15 and 106 <= ty <= 120:
                        nuevo_stage, nuevo_tile = 41, (254, 16)
                elif ses.personaje.stage == 43:
                    # Retorno desde West Playground (43) a Lyceum (41) al pisar el portal (189, 24)
                    if tx >= 185 and 18 <= ty <= 30:
                        nuevo_stage, nuevo_tile = 41, (28, 125)

                if nuevo_stage:
                    ses.personaje.stage = nuevo_stage
                    ses.personaje.tile_x, ses.personaje.tile_y = nuevo_tile
                    ses.monstruos = _monstruos_de(nuevo_stage)
                    ses.enviar(_cl3.cambiar_mapa(nuevo_stage))
                    import login as _lg
                    ses.enviar(*_lg.poblar(nuevo_stage))
                    # Reenviar las habilidades y barra para que no se borren tras tepearse
                    if ses.personaje and ses.personaje.habilidades:
                        import clases as _cl
                        _ids = [h[0] for h in ses.personaje.habilidades]
                        ses.enviar(_cl.arbol(_ids))
                        _hech = _cl.hechizos_iniciales(_ids)
                        if _hech:
                            ses.enviar(_cl.otorgar_hechizos(ses.personaje.entity_id, [n for n, _ in _hech]))
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
