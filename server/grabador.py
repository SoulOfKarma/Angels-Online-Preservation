"""
Grabador de sesiones en vivo.

Vuelca el trafico crudo a .bin con el MISMO formato de nombre que
logs/raw_streams/, para poder correr sobre una sesion fallida exactamente las
mismas herramientas que se usaron con las capturas reales:

    tools/validate_framing.py   tools/build_corpus2.py
    tools/replay.py             tools/opcode_map.py

Cuando el cliente real falle -- y va a fallar en algun punto -- esto convierte
"no anduvo" en "en el mensaje N el cliente esperaba otra cosa".
"""
import json
import pathlib
import struct
import time
import datetime

RAIZ = pathlib.Path(__file__).parent.parent / 'logs' / 'sesiones'


class Grabador:
    def __init__(self, addr, puerto, clave):
        RAIZ.mkdir(parents=True, exist_ok=True)
        marca = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        ip = str(addr[0]).replace('.', '_')
        base = f"{ip}_{puerto}_{marca}"
        self.c2s = open(RAIZ / f"{base}_c2s.bin", 'wb')
        self.s2c = open(RAIZ / f"{base}_s2c.bin", 'wb')
        # la clave es imprescindible para descifrar despues
        (RAIZ / f"{base}_clave.txt").write_text(clave.hex(), encoding='utf-8')
        # Y un .jsonl con TIEMPOS, igual que el del proxy, para poder medir
        # cadencias y comparar contra el servidor real. Los .bin solos no
        # sirven para eso: guardan el orden pero no cuando paso cada cosa.
        self.orden = open(RAIZ / f"{base}_orden.jsonl", 'w', encoding='utf-8')
        self.t0 = time.time()
        self.base = base
        self.n_c2s = self.n_s2c = 0

    def _anotar(self, sentido, datos):
        """Parte el bloque en sub-mensajes y anota cada uno con su instante."""
        try:
            off = 0
            while off + 6 <= len(datos):
                ln = struct.unpack_from('<H', datos, off)[0] ^ 0x1357
                if ln <= 0 or off + 6 + ln > len(datos):
                    break
                cuerpo = datos[off + 6:off + 6 + ln]
                i = 0
                while i + 4 <= len(cuerpo):
                    sl = struct.unpack_from('<H', cuerpo, i)[0]
                    if sl < 2 or i + 2 + sl > len(cuerpo):
                        break
                    sub = cuerpo[i + 2:i + 2 + sl]
                    self.orden.write(json.dumps({
                        't': round(time.time() - self.t0, 4),
                        'dir': sentido,
                        'opcode': struct.unpack_from('<H', sub, 0)[0],
                        'len': len(sub) - 2,
                        'hex': sub[2:].hex(),
                    }) + chr(10))
                    i += 2 + sl
                off += 6 + ln
            self.orden.flush()
        except Exception:
            pass

    def submensaje(self, sentido, opcode, cuerpo):
        """Anota un sub-mensaje YA DESCIFRADO.

        El sentido cliente->servidor llega cifrado con XorEvolving, asi que
        anotarlo desde los bytes crudos solo captura el hello. Se llama esto
        desde el dispatcher, donde el mensaje ya esta descifrado.
        """
        try:
            self.orden.write(json.dumps({
                't': round(time.time() - self.t0, 4),
                'dir': sentido,
                'opcode': int(opcode),
                'len': len(cuerpo),
                'hex': bytes(cuerpo).hex(),
            }) + chr(10))
            self.orden.flush()
        except Exception:
            pass

    def entrada(self, datos):
        # Solo el .bin: estos bytes vienen cifrados. El .jsonl del sentido
        # c2s lo llena el dispatcher con submensaje(), ya descifrado.
        self.c2s.write(datos); self.c2s.flush(); self.n_c2s += len(datos)

    def salida(self, datos):
        self.s2c.write(datos); self.s2c.flush(); self.n_s2c += len(datos)
        self._anotar('s2c', datos)

    def cerrar(self):
        for f in (self.c2s, self.s2c, self.orden):
            try: f.close()
            except Exception: pass
        return self.base, self.n_c2s, self.n_s2c
