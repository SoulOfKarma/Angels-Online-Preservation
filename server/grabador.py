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
import pathlib
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
        self.base = base
        self.n_c2s = self.n_s2c = 0

    def entrada(self, datos):
        self.c2s.write(datos); self.c2s.flush(); self.n_c2s += len(datos)

    def salida(self, datos):
        self.s2c.write(datos); self.s2c.flush(); self.n_s2c += len(datos)

    def cerrar(self):
        for f in (self.c2s, self.s2c):
            try: f.close()
            except Exception: pass
        return self.base, self.n_c2s, self.n_s2c
