"""Pet Amplify (WND_EQUIP_PET_NEW, Ctrl+P).

Sacado con REA del cliente (play_angel_unpacked.exe) el 21/10/2026 y del
0x0179 que mando el servidor real al entrar (plantillas/mundo_real/
init_28_0179.bin, personaje sin casillas abiertas).

El estado lo guarda CEquipPetNewDataHandler (objeto de actividad tipo 3).
s2c 0x0179 (FUN_006e14f0), mismo lector que los bonos: [u32 tam = 8][u32
casillas abiertas][u32 n] n x [u32 seccion][u8 0] + la seccion:
  1  tres listas [u32 n] n x u32: los Re-Amplify Hammer de cada tipo, por
     prioridad (40289 40288 40287 / 40292 40291 40290 / 40295 40294 40293,
     el 優先度 de pet_inlay.xml).
  2  [u32 casilla][u8 atributo][u8 valor]: una casilla.
  3  [u32 n] n x u32: las mascotas metidas (las marca como amplificadas).
  5  [u32 n] n x [u16 atributo][u32 bono]: el bono actual.
  6  igual (la otra columna de la ventana).
  7  [u32 n] n x [u16 atributo][u32 tope]: el "Current Max".
  8  [u8 atributo] x casillas abiertas.
  9  [u8 valor] x casillas abiertas.
Atributos (DEFINE de pet_inlay.xml): 1 HP, 3 MP, 8 ATK, 10 DEF, 11 Spell
ATK, 12 Spell DEF, 13 Hit, 14 Agility; 70/80/90/100 son EXP, Skill EXP,
Repair Discount y Reflect Damage (string.xml 3418-3421).

c2s 0x015D (FUN_00655220, "EquipPetNewUseItemConfirm"): abrir casilla con los
Amplify Hammer elegidos en la lista: [u32 n] n x [u16][u32 a][u32 b][u32 c]
con a/b/c = +0x14/+0x8/+0xC de la fila (objeto, casilla, cantidad: se
reconocen por el valor). Cuesta el 道具數量 de pet_inlay.xml para esa casilla.
c2s 0x015C (FUN_005f8850 -> FUN_005f8d90, 15 bytes): Re-Amplify
[u8 tipo 1 todo | 2 atributo | 3 valor][u32 casilla][u32][u32].
El valor nuevo va del 10 al 50 % (string.xml 3427 y 3430).
"""
import functools
import logging
import pathlib
import random
import re
import struct

log = logging.getLogger('amplify')

S2C = 0x0179
C2S_ABRIR = 0x015D
C2S_CAMBIAR = 0x015C
MAX_CASILLAS = 40
ATRIBUTOS = (1, 3, 8, 10, 11, 12, 13, 14)
EXTRA = (70, 80, 90, 100)
VALOR_MIN, VALOR_MAX = 10, 50
MARTILLO_ABRIR = (40284, 40285, 40286)
MARTILLOS = {1: (40289, 40288, 40287), 2: (40292, 40291, 40290), 3: (40295, 40294, 40293)}
TOPE = {1: 48000, 3: 38400, 8: 19200, 10: 12800, 11: 12800, 12: 12800, 13: 4000, 14: 4000}
# Las casillas de Amplify en el inventario: soltar una mascota en la primera
# manda el 0x0012 [20 -> 559] (log del 21/10/2026). Son 40.
RANURA_INI = 559
RANURA_FIN = RANURA_INI + MAX_CASILLAS - 1
# Atributo de Amplify -> (clave del bono verde de la mascota, clave de buff).
ATR_PET = {1: ('hp', 'hp_bonus'), 3: ('mp', 'mp_bonus'), 8: ('atk', 'atk'), 10: ('dfs', 'def'),
           11: ('matk', 'matk'), 12: ('mdef', 'mdef'), 13: ('rigor', 'hit'), 14: ('agilidad', 'eva')}


def es_ranura(r):
    return RANURA_INI <= int(r) <= RANURA_FIN

_RAIZ = pathlib.Path(__file__).resolve().parent.parent


@functools.lru_cache(maxsize=1)
def coste_casillas():
    """[hammers para abrir la casilla 1, 2, ...] de pet_inlay.xml."""
    for carpeta in sorted((_RAIZ / 'extracted_paks').glob('*'),
                          key=lambda p: int(re.sub(r'\D', '', p.name) or 0), reverse=True):
        f = carpeta / 'setting' / 'pet_inlay.xml'
        if f.is_file():
            filas = re.findall(r'<寵物鑲格 編號="(\d+)" 道具數量="(\d+)"', f.read_text(encoding='utf-8-sig'))
            return [int(n) for _, n in sorted(filas, key=lambda x: int(x[0]))]
    return [5] * 6


def coste(abiertas):
    tabla = coste_casillas()
    return tabla[abiertas] if abiertas < len(tabla) else (tabla[-1] if tabla else 5)


class Estado:
    def __init__(self, d=None):
        d = d or {}
        self.atributos = [int(x) for x in (d.get('atributos') or [])][:MAX_CASILLAS]
        self.valores = [int(x) for x in (d.get('valores') or [])][:MAX_CASILLAS]
        self.mascotas = [int(x) for x in (d.get('mascotas') or [])][:MAX_CASILLAS]
        n = min(len(self.atributos), len(self.valores))
        self.atributos, self.valores = self.atributos[:n], self.valores[:n]

    @property
    def abiertas(self):
        return len(self.atributos)

    def datos(self):
        return {'atributos': self.atributos, 'valores': self.valores, 'mascotas': self.mascotas}

    def abrir(self, rnd=random):
        if self.abiertas >= MAX_CASILLAS:
            return None
        self.atributos.append(rnd.choice(ATRIBUTOS))
        self.valores.append(rnd.randint(VALOR_MIN, VALOR_MAX))
        return self.abiertas - 1

    def cambiar(self, tipo, casilla, rnd=random):
        if not 0 <= casilla < self.abiertas:
            return False
        if tipo in (1, 2):
            self.atributos[casilla] = rnd.choice(ATRIBUTOS)
        if tipo in (1, 3):
            self.valores[casilla] = rnd.randint(VALOR_MIN, VALOR_MAX)
        return True

    def tope(self, atributo):
        """El "Current Max": crece con las casillas abiertas (con 4 de 40 la
        ventana ensena HP 4800 = 48000 x 4 / 40)."""
        return int(TOPE.get(atributo, 0) * self.abiertas / MAX_CASILLAS)

    def bonos(self, verdes=None):
        """{atributo: bono}: por cada casilla con mascota, su stat TOTAL (base +
        verde) en el atributo de la casilla x el % de la casilla, con el Current Max.
        `verdes` = [stats totales de la mascota o None] por casilla."""
        res = {a: 0 for a in ATRIBUTOS + EXTRA}
        for i, (a, v) in enumerate(zip(self.atributos, self.valores)):
            verde = verdes[i] if verdes and i < len(verdes) else None
            if verde and a in ATR_PET:
                res[a] += int(int(verde.get(ATR_PET[a][0]) or 0) * v / 100)
        for a in TOPE:
            res[a] = min(res[a], self.tope(a))
        return res

    def buff(self, verdes=None):
        """Los bonos con las claves de los stats (para logros.con_reputacion)."""
        return {ATR_PET[a][1]: n for a, n in self.bonos(verdes).items() if a in ATR_PET and n}


def _seccion(clave, cuerpo=b''):
    return struct.pack('<IB', clave, 0) + cuerpo


def _mapa(valores):
    return struct.pack('<I', len(valores)) + b''.join(struct.pack('<HI', k, v) for k, v in valores)


def paquete(est, verdes=None):
    bonos = est.bonos(verdes)
    martillos = b''.join(struct.pack('<I', len(ids)) + b''.join(struct.pack('<I', i) for i in ids)
                         for ids in MARTILLOS.values())
    mascotas = [m for m in est.mascotas if m]
    secciones = [
        _seccion(1, martillos),
        _seccion(3, struct.pack('<I', len(mascotas)) + b''.join(struct.pack('<I', m) for m in mascotas)),
        _seccion(5, _mapa([(a, bonos[a]) for a in ATRIBUTOS + EXTRA])),
        _seccion(6, _mapa([(a, bonos[a]) for a in ATRIBUTOS + EXTRA])),
        _seccion(7, _mapa(sorted(TOPE.items()))),
        _seccion(8, bytes(est.atributos)),
        _seccion(9, bytes(est.valores)),
    ]
    return (struct.pack('<HII', S2C, 8, est.abiertas) + struct.pack('<I', len(secciones))
            + b''.join(secciones))


def leer_abrir(cuerpo):
    """c2s 0x015D -> [(a, b, c)]."""
    if len(cuerpo) < 4:
        return []
    n = struct.unpack_from('<I', cuerpo, 0)[0]
    out = []
    for i in range(min(n, 40)):
        off = 4 + i * 14 + 2
        if off + 12 > len(cuerpo):
            break
        out.append(struct.unpack_from('<III', cuerpo, off))
    return out


def leer_cambiar(cuerpo):
    """c2s 0x015C -> (tipo, casilla, x, y)."""
    if len(cuerpo) < 13:
        return None
    return struct.unpack_from('<BIII', cuerpo, 0)
