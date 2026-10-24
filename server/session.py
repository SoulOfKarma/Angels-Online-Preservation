"""
Estado y maquinaria de una conexion.

Toda la capa de protocolo esta validada contra capturas reales:
  - framing       : 168.570/168.570 frames re-codificados identicos
  - handshake     : build_hello() reproduce el Hello de IGG byte a byte
  - sub-mensajes  : 24/24 esquemas, 97,6% del corpus

Configuracion elegida (las tres atestiguadas en produccion real):
  - Hello en variante minima con clave de 16 bytes
  - S->C en texto plano (el servidor privado lo hace y el cliente lo acepta)
  - C->S descifrado con XOR evolutivo a partir de esa clave
"""
import os
import sys
import pathlib
import logging
import collections
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'proto'))
from framing import HDR, decode_header, build_frame, submessages, pack_submessages, SEQ_HELLO
from handshake import build_hello, XorEvolving
from codec import Msg
import messages  # noqa: registra los esquemas

log = logging.getLogger('session')

PLANTILLA_HELLO = pathlib.Path(__file__).parent / 'plantillas' / 'hello_embebido.bin'


class Session:
    def __init__(self, addr, key=None):
        self.addr = addr
        self.key = key if key is not None else os.urandom(16)
        self.recv_crypto = XorEvolving(self.key)
        self.seq = 1
        self.buf = bytearray()
        self.salida = []                       # frames listos para enviar
        self.desconocidos = collections.Counter()
        self.vistos = collections.Counter()
        self.entity_id = None
        self.personaje = None
        self.rol = 'mundo'
        self.usuario = None
        self.puerto = None
        self.cerrar_tras_redirect = False
        self.sentado = False
        self.ultimo_movimiento = time.time()
        self.ultimo_combate = 0.0
        self.ultimo_regen_tick = 0.0
        self.mapa_cargando = False
        self._mapa_ui_diferida = []

    # ---------------------------------------------------------------- salida

    def _next_seq(self):
        # El SERVIDOR no incrementa: manda siempre seq=1. Medido en 2.730 de
        # 2.731 frames reales, y confirmado en la captura del proxy (los dos
        # frames del login usan seq=1). Solo el CLIENTE incrementa.
        return 1

    def enviar_hello(self):
        # Se manda la variante CON CIFRADOR EMBEBIDO, no la minima.
        # Comparando frame por frame contra una captura de un servidor vivo,
        # los tres frames del login coincidian salvo este: el real manda 134 B
        # (cifrador embebido, clave en cero) y yo mandaba 22 B (minima, clave
        # aleatoria). La variante minima la usaba IGG; este cliente espera la
        # otra, que le hace instalar el cifrador que el servidor le envia.
        # Con clave en cero, el XOR es identidad y el trafico queda en claro.
        pl = PLANTILLA_HELLO.read_bytes()
        self.key = bytes(16)
        self.recv_crypto = XorEvolving(self.key)
        self.salida.append(build_frame(pl, SEQ_HELLO))

    def enviar(self, *submsgs):
        """submsgs: bytes ya serializados por Msg.build (opcode incluido)."""
        if not submsgs:
            return
        # sub_60ADC0 (0x0065) borra la lista de iconos de buff de WND_PET_INFO;
        # si va un 0x0065 y la mascota esta invocada, reenviar sus 0x001D kind=4 detras.
        if any(isinstance(s, (bytes, bytearray)) and len(s) >= 2 and s[:2] == b'\x65\x00' for s in submsgs):
            try:
                p = getattr(self, 'personaje', None)
                f_pet = getattr(p, 'mascota', None) if p else None
                pet_eid = getattr(self, 'pet_entity_id', None) or (f_pet.get('entidad') if isinstance(f_pet, dict) else None)
                if isinstance(f_pet, dict) and f_pet.get('fuera') and pet_eid:
                    import mascotas as _ms
                    extra_b = _ms.paquetes_buffs(f_pet, int(pet_eid))
                    if extra_b:
                        submsgs = tuple(submsgs) + tuple(extra_b)
            except Exception:
                pass
        submsgs = self._filtrar_carga_mapa(submsgs)
        if not submsgs:
            return
        self._registrar_flags_magicos(submsgs)
        self.salida.append(build_frame(pack_submessages(submsgs), self._next_seq()))
        # SALA DE INSTANCIA COMPARTIDA: lo que le pasa a un bicho de la sala
        # se lo ven todos los del grupo que esten en ella (app._espejar).
        espejo = getattr(self, 'espejo', None)
        if espejo is not None:
            try:
                espejo(self, submsgs)
            except Exception:
                log.debug('no se pudo reenviar al grupo', exc_info=True)

    def enviar_sin_espejo(self, *submsgs):
        """Como enviar, pero sin reenviarlo al grupo: es lo que se usa para
        entregar lo que llega reenviado de otro, para que no rebote."""
        submsgs = self._filtrar_carga_mapa(submsgs)
        if submsgs:
            self._registrar_flags_magicos(submsgs)
            self.salida.append(build_frame(pack_submessages(submsgs), self._next_seq()))

    def _registrar_flags_magicos(self,submsgs):
        """Keep authoritative0185 snapshots so one mechanic preserves other bits."""
        import struct
        own=getattr(getattr(self,'personaje',None),'entity_id',None)
        for packet in submsgs:
            if len(packet)==14 and packet[:2]==b'\x85\x01':
                entity,lo,hi=struct.unpack_from('<III',packet,2)
                if entity==own:self.flags_magicos=(lo,hi)

    def _filtrar_carga_mapa(self, submsgs):
        """Every world CHANGE_MAP starts a barrier, including legacy travel.

        Effects, moves, entities and stat snapshots emitted by timers during
        loading belong to an unready scene. The ready handler rebuilds them
        from current authoritative state. Inventory deltas/chat are independent
        of the scene and are deferred, not lost or replayed before the ficha.
        """
        if self.rol != 'mundo':
            return submsgs
        cambio = next((i for i,s in enumerate(submsgs) if s[:2] == b'\x0c\x00'),None)
        if cambio is not None:
            self.mapa_cargando = True
            self.mapa_cambiado_en = time.time()
            # Keep the measured pre-travel sequence, but never world packets
            # after CHANGE_MAP in the same call/frame.
            prefijo, resto = submsgs[:cambio+1], submsgs[cambio+1:]
        elif not self.mapa_cargando:
            return submsgs
        else:
            prefijo, resto = (), submsgs
        for sub in resto:
            if sub[:2] in (b'\x1b\x00',b'\x0d\x00',b'\x28\x01',b'\x26\x01',b'\x27\x01'):
                self._mapa_ui_diferida.append(sub)
                if len(self._mapa_ui_diferida) > 256:
                    self._mapa_ui_diferida.pop(0)
        return prefijo

    def terminar_carga_mapa(self):
        """Flush only scene-independent UI AFTER the complete ready sequence."""
        self.mapa_cargando = False
        pendientes, self._mapa_ui_diferida = self._mapa_ui_diferida, []
        if pendientes:
            self.enviar_sin_espejo(*pendientes)

    def enviar_crudo(self, payload):
        """Envia un payload ya armado como cadena de sub-mensajes.

        El servidor de login manda su respuesta asi (y el real la comprime con
        LZO1X; nosotros la mandamos sin comprimir, que el cliente acepta igual)."""
        self.salida.append(build_frame(payload, self._next_seq()))

    def drenar(self):
        out = b''.join(self.salida)
        self.salida.clear()
        return out

    def volcar(self):
        """Saca a la red lo que haya en el buffer, sin anadir nada.

        Hace falta porque `enviar` solo ACUMULA: el buffer se vaciaba al
        atender un paquete del cliente, asi que todo lo que generaba el
        servidor por su cuenta -- el paseo de los monstruos, sobre todo --
        se quedaba esperando a que el jugador se moviera. Se veia clavado:
        los bichos solo andaban cuando andabas tu.
        """
        out = self.drenar()
        if out and getattr(self, 'writer', None):
            try:
                if getattr(self, 'grab', None):
                    self.grab.salida(out)
                self.writer.write(out)
            except Exception:
                pass

    def enviar_inmediato(self, *submsgs):
        """Envia submensajes a la red de inmediato sin esperar al drenaje del bucle principal."""
        self.enviar(*submsgs)
        self.volcar()

    # ---------------------------------------------------------------- entrada

    def alimentar(self, data: bytes):
        """Acumula bytes del cliente y devuelve [(opcode, cuerpo)] completos."""
        self.buf.extend(data)
        recibidos = []
        while len(self.buf) >= HDR:
            h = decode_header(self.buf, 0)
            if h['length'] == 0 or h['length'] > 0x10000:
                log.warning(f"[{self.addr}] longitud invalida {h['length']}, se descarta 1 byte")
                del self.buf[0]
                continue
            if len(self.buf) < h['wire']:
                break                          # frame incompleto, esperar mas
            cuerpo = bytes(self.buf[HDR:h['wire']])
            del self.buf[:h['wire']]
            if h['encrypted']:
                cuerpo = self.recv_crypto.decrypt(cuerpo)
            if h['compressed']:
                log.warning(f"[{self.addr}] frame comprimido: sin soporte todavia")
                continue
            msgs, _ = submessages(cuerpo[:h['length']])
            recibidos.extend(msgs)
        return recibidos

    # ---------------------------------------------------------------- dispatch

    def parsear(self, opcode, cuerpo):
        """Devuelve el dict del mensaje, o None si no hay esquema."""
        for rev in ('*', 'privado', 'igg'):
            m = Msg.registry.get((opcode, 'c2s', rev))
            # Alcance POR SERVICIO: un esquema declarado para ciertos puertos
            # no se aplica en otros. El mismo opcode significa cosas distintas
            # en login, mundo y archivos -- 0x0004 es movimiento en el mundo
            # y estado de interfaz en el login.
            if m is not None and m.puertos and self.puerto not in m.puertos:
                continue
            if m:
                try:
                    return m, m.parse(cuerpo)
                except Exception as e:
                    log.debug(f"[{self.addr}] 0x{opcode:04X} no parsea: {e}")
                    return m, None
        return None, None
