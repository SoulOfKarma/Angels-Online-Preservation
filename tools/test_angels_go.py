"""El teletransporte de las Superwing (Angels GO!, c2s 0x0151).

Los tres destinos que se prueban aqui son los tres que se midieron en
Celestia el 24/09/2026, con su casilla de llegada real:

    id 120 -> stage 126 (34,219)   "Instance Entry Point", mismo mapa
    id 119 -> stage 126 (20,23)    "Entrance", mismo mapa
    id 109 -> stage 120 (32,20)    entre mapas, de Fantastic Sand City

La bifurcacion de la respuesta tambien esta medida: si el destino cae en el
mapa en el que ya estas se cierra con un 0x0003 y NO viaja ningun 0x000C; si
es otro mapa se cierra con un 0x0007 de 5B y el 0x000C, como un tornado.
"""
import json
import pathlib
import struct
import sys

sys.path.insert(0, 'server')
sys.stdout.reconfigure(encoding='utf-8')

import app
import login

TABLA = json.loads((pathlib.Path('server/plantillas/angels_go.json')
                    ).read_text(encoding='utf-8'))

print("=== 1. La tabla del cliente contra lo medido ===")
for m in TABLA['medido']:
    d = TABLA['destinos'][str(m['id'])]
    assert d['stage'] == m['stage'], (m['id'], d['stage'], m['stage'])
    assert d['tile'] == m['tile'], (m['id'], d['tile'], m['tile'])
    print("  id %-4d stage %-4d tile %-10s  %s"
          % (m['id'], d['stage'], d['tile'], d.get('punto') or '-'))
print("  los %d destinos de jumpmap.xml cargan" % len(TABLA['destinos']))

print("\n=== 2. Cuantos destinos caen en mapas que ya tenemos ===")
listos = [i for i, d in TABLA['destinos'].items()
          if d['stage'] in app.mapas_poblados()]
print("  %d de %d destinos, en %d escenarios poblados"
      % (len(listos), len(TABLA['destinos']),
         len({TABLA['destinos'][i]['stage'] for i in listos})))
assert len(listos) > 100


def _pj(stage, tile):
    p = login.Personaje(char_id=282, nombre="Karma", stage=stage,
                        tile_x=tile[0], tile_y=tile[1], hp=500, hp_max=500,
                        mp=200, mp_max=200, exp=10000, nivel=11)
    p.entity_id = 286
    return p


class _Ses:
    rol = 'mundo'
    usuario = None
    def __init__(self, stage, tile, superwings=2):
        self.personaje = _pj(stage, tile)
        self.inventario = {54: app.ITEM_SUPERWING}
        self.cantidades = {54: superwings}
        self.monstruos = []
        self.enviado = []
        self.portal_pisado = None
    def enviar(self, *p):
        self.enviado.extend(p)


def _op(p):
    return struct.unpack_from('<H', p, 0)[0]


_SRV = app.Servidor.__new__(app.Servidor)


def _viajar(ses, ido):
    _SRV.manejar(ses, 0x0151, None, None, '(test)',
                 struct.pack('<I', ido))
    return [_op(p) for p in ses.enviado]


print("\n=== 3. Mismo mapa: se cierra con el 0x0003, sin 0x000C ===")
s = _Ses(126, (13, 23))
ops = _viajar(s, 120)
print("  opcodes:", [hex(o) for o in ops])
assert 0x000C not in ops, "no debe cambiar de mapa"
assert ops[0] == 0x0012 and ops[-1] == 0x0003
cuerpo = s.enviado[-1][2:]
ent, tx, ty = struct.unpack('<III', cuerpo)
print("  0x0003 -> entidad %d, tile (%d,%d)" % (ent, tx, ty))
assert (tx, ty) == (34, 219), (tx, ty)
assert (s.personaje.tile_x, s.personaje.tile_y) == (34, 219)
assert s.personaje.stage == 126
assert s.cantidades[54] == 1, "debe gastar UNA Superwing"
print("  quedan %d Superwings" % s.cantidades[54])

print("\n=== 4. Otro mapa: se cierra con 0x0007 y 0x000C ===")
s = _Ses(125, (238, 145))
ops = _viajar(s, 109)
print("  opcodes:", [hex(o) for o in ops])
assert 0x0003 not in ops, "entre mapas no manda el 0x0003"
assert ops[-2] == 0x0007 and ops[-1] == 0x000C
assert struct.unpack_from('<I', s.enviado[-1], 2)[0] == 120
assert s.personaje.stage == 120
assert (s.personaje.tile_x, s.personaje.tile_y) == (32, 20)
print("  stage %d tile (%d,%d), quedan %d Superwings"
      % (s.personaje.stage, s.personaje.tile_x, s.personaje.tile_y,
         s.cantidades[54]))

print("\n=== 5. Lo que NO debe pasar ===")
s = _Ses(126, (13, 23), superwings=0)
s.inventario, s.cantidades = {}, {}
_viajar(s, 119)
assert s.enviado == [], "sin Superwing no se viaja"
assert (s.personaje.tile_x, s.personaje.tile_y) == (13, 23)
print("  sin Superwing en la mochila: no pasa nada")

s = _Ses(126, (13, 23))
_viajar(s, 999999)
assert s.enviado == [] and s.cantidades[54] == 2
print("  id que no esta en jumpmap.xml: no pasa nada y no gasta el item")

sin_poblar = next(i for i, d in TABLA['destinos'].items()
                  if d['stage'] not in app.mapas_poblados())
s = _Ses(126, (13, 23))
_viajar(s, int(sin_poblar))
assert s.enviado == [] and s.cantidades[54] == 2
print("  destino a un stage sin poblar (id %s): no se viaja ni se gasta"
      % sin_poblar)

print("\n=== 6. El Angel Lyceum cuenta como mapa poblado ===")
# El id 1 es el Lyceum (stage 41), que NO vive en PLANTILLAS_POR_STAGE sino
# en la tabla de los dos mapas que se tratan aparte. La primera version del
# manejador miraba solo la primera tabla y dejaba fuera el Lyceum y el
# Fighting Palace, que son mapas poblados desde siempre.
assert TABLA['destinos']['1']['stage'] == 41
assert 41 in app.mapas_poblados() and 57 in app.mapas_poblados()
s = _Ses(126, (13, 23))
ops = _viajar(s, 1)
print("  id 1 -> Angel Lyceum:", [hex(o) for o in ops])
assert ops[-1] == 0x000C and s.personaje.stage == 41

print("\n=== 7. La llegada no rebota por un tornado ===")
# El id 119 deja en (20,23) de Nightmare Palace, a ocho del tornado 112227,
# asi que no hay portal que pisar; pero si lo hubiera, tiene que quedar
# marcado como pisado y no disparar.
s = _Ses(125, (238, 145))
_viajar(s, 119)
print("  portal_pisado tras llegar a (20,23):", s.portal_pisado)
assert app._portal_en(126, 20, 23) is None

print("\nTODOS LOS TESTS PASARON EXITOSAMENTE!")
