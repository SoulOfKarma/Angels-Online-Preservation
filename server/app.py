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
    if not f.exists():
        return ''
    for e in json.loads(f.read_text(encoding='utf-8'))['spawns']:
        if e['entity_id'] == entity_id:
            return e['nombre']
    return ''


def _monstruos_de(stage: int):
    """Los monstruos vivos del mapa, por entity_id."""
    import json
    import combate
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

    async def cliente(self, reader, writer, rol='mundo'):
        addr = writer.get_extra_info('peername')
        self.sesiones += 1
        ses = Session(addr)
        ses.rol = rol
        ses.puerto = self.port if rol == 'login' else self.wport
        grab = Grabador(addr, self.port if rol == 'login' else self.wport, ses.key)
        log.info(f"[{addr}] conectado ({rol})  clave={ses.key.hex(' ')}")
        log.info(f"[{addr}] grabando sesion -> logs/sesiones/{grab.base}_*.bin")
        ses.enviar_hello()
        primero = ses.drenar()
        grab.salida(primero)
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
                ses.enviar(_cl.arbol([h[0] for h in p.habilidades]))
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
            bichos = getattr(ses, 'monstruos', None) or {}
            m = bichos.get(objetivo)
            if m is None:
                log.debug(f"[{addr}] ataque a la entidad {objetivo}: no es un "
                          f"monstruo conocido")
                return
            if not m.vivo:
                return
            yo = ses.entity_id or 1001
            # El dano sale del ataque del jugador menos la defensa del bicho.
            import inventario as _iv
            st = _iv.stats(ses.inventario)
            ataque = struct.unpack_from('<I', st, 2 + 20 + 4)[0]
            dano = m.recibir(ataque)
            # El orden es el de la captura, y importa: primero la vida del
            # objetivo, despues un 0x000A CON CEROS que abre el ataque, y solo
            # entonces los dos 0x0011, que son los que dibujan el numero.
            # Mandar el dano dentro del 0x000A no hace nada: el cliente lo
            # ignora, y por eso se veia el gesto sin numero.
            ses.esfuerzo = max(0, getattr(ses, 'esfuerzo', 900) - _cb.COSTE_GOLPE)
            ses.enviar(_cb.atributo(objetivo, m.porcentaje),
                       _cb.empieza_ataque(yo),
                       *_cb.numero_de_dano(yo, objetivo, dano, tipo),
                       _cb.atributo(yo, ses.esfuerzo, _cb.KIND_ESFUERZO))
            if m.vivo:
                # Contraataca.
                suyo = m.pegar()
                ses.enviar(_cb.empieza_ataque(objetivo),
                           *_cb.numero_de_dano(objetivo, yo, suyo))
                log.debug(f"[{addr}] pego {dano} al {m.nombre} "
                          f"({m.porcentaje}%), me devolvio {suyo}")
                return
            # Muerto: el botin entra DIRECTO al inventario, no cae al suelo.
            import clases as _cl
            oro = _cb.botin()
            ses.oro = getattr(ses, 'oro', 0) + oro
            if ses.personaje:
                ses.personaje.oro = ses.oro
            cid = ses.personaje.char_id if ses.personaje else 4980
            ses.enviar(_iv.completo(cid, _con_oro(ses)),
                       _cl.aviso(f'{oro} Gold', tipo=0, msg_id=_cl.MSG_ITEM))
            if getattr(ses, 'usuario', None):
                cuentas.guardar_oro(ses.usuario, cid, ses.oro)
            log.info(f"[{addr}] mato un {m.nombre} (entidad {objetivo}); "
                     f"+{oro} de oro, total {ses.oro}")
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
            ses.enviar(*salida)
            if ses.personaje:
                ses.personaje.habilidades = [(sid, 1, 0) for sid in ids]
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_habilidades(
                        ses.usuario, ses.personaje.char_id,
                        ses.personaje.habilidades)
            log.info(f"[{addr}] CLASE ELEGIDA: "
                     + ', '.join(f'{clases.nombre(i)}({i})' for i in ids))
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
            if dst in bolsa:
                log.warning(f"[{addr}] mover {org} -> {dst}: la ranura {dst} ya "
                            f"esta ocupada (apilar todavia no se implementa)")
                return
            it = bolsa.pop(org)
            bolsa[dst] = it
            cid = ses.personaje.char_id if ses.personaje else 4980
            salida = [inv.movimiento(org, dst, cid, it, inv.instancia_de(cid, it))]
            # Los stats solo se recalculan si cambia lo que lleva puesto: en la
            # captura hay 26 movimientos y solo 2 traen 0x0042, justo los dos
            # que tocan la ranura del cuerpo.
            # Recalcular si cambio CUALQUIER ranura de equipo, no solo el
            # cuerpo: hay mochilas equipables y podria haber mas piezas.
            if inv.es_equipo(org) or inv.es_equipo(dst):
                salida.append(inv.stats(bolsa))
            ses.enviar(*salida)
            if ses.personaje and getattr(ses, 'usuario', None):
                cuentas.guardar_inventario(ses.usuario, ses.personaje.char_id, bolsa)
            log.info(f"[{addr}] item {it}: ranura {org} -> {dst}"
                     + ("  (cambia el equipo)"
                        if inv.es_equipo(org) or inv.es_equipo(dst) else ""))
            return
            ses.equipo = estado
            ses.enviar(*equipo.mensajes(estado, ses.entity_id or 1001))
            log.info(f"[{addr}] item movido {org} -> {dst}: ropa {estado}")
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
            if ses.personaje and ent in dialogos.NOMBRE_POR_ENTIDAD:
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
                g2 = dialogos.propio(_nombre_entidad(ses, ent))
                if g2:
                    nom2 = ses.personaje.nombre if ses.personaje else 'Jugador'
                    ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g2, 1
                    ses.enviar(dialogos.linea_de(g2, 0, nom2))
                    log.info(f"[{addr}] dialogo de {_nombre_entidad(ses, ent)}")
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
                ses.enviar(dialogos.respuesta_a(_el) if _el
                           else struct.pack('<H', 0x0012) + dialogos.FIN)
                ses.dlg_ent = None
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
                # Este atributo (kind 12, valor 0) es lo que hace que el
                # cliente ofrezca elegir clase. Repasando las capturas por
                # NPC, solo sale tras el dialogo de Angel Raphael (entidad
                # 19), nunca tras el Interface Tutor ni el Angel Aide. Y
                # tampoco vuelve a salir una vez elegida la clase: en la
                # misma sesion se habla tres veces mas con Raphael y ya no
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
                        ses.enviar(_cls.cambiar_mapa(_cls.STAGE_LYCEUM))
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
