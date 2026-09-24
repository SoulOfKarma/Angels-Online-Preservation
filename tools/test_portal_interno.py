"""Portales que llevan a otro punto del MISMO mapa.

Medido en Forbidden Sector (stage 228) el 24/09/2026, con seis cruces entre
sus dos tubos de teletransporte. En 1401 segundos de sesion no viajo ni un
solo 0x000C: el mapa NO se recarga, solo se recoloca al personaje.

    s2c 0x0016  [u32 entidad][u8 direccion]
    s2c 0x0012  siete bytes a cero
    s2c 0x0003  [u32 entidad][u32 x][u32 y]

Ojo con el 0x0012: aqui son SIETE ceros, no los nueve de dialogos.FIN.
"""
import struct
import sys

sys.path.insert(0, 'server')
sys.stdout.reconfigure(encoding='utf-8')

import app
import login

SUR, NORTE = (226, 143), (197, 75)


def _pj(stage, tile):
    p = login.Personaje(char_id=282, nombre="Karma", stage=stage,
                        tile_x=tile[0], tile_y=tile[1], hp=500, hp_max=500,
                        mp=200, mp_max=200, exp=1, nivel=11)
    p.entity_id = 286
    return p


class _Ses:
    rol = 'mundo'
    usuario = None
    def __init__(self, stage, tile):
        self.personaje = _pj(stage, tile)
        self.enviado = []
        self.portal_pisado = None
        self.monstruos = []
    def enviar(self, *p):
        self.enviado.extend(p)


print("=== 1. Los dos portales estan registrados como del mismo mapa ===")
for tile in (SUR, NORTE):
    p = app._portal_en(228, *tile)
    assert p is not None, tile
    assert p['destino'] == 228, p['destino']
    assert p.get('mismo_mapa') is True
    print("  %-10s -> stage %d tile %s  direccion %s"
          % (tile, p['destino'], p['llegada'], p.get('direccion')))

print("\n=== 2. Cruzar no recarga el mapa ===")
s = _Ses(228, (227, 145))
por = app._portal_en(228, *SUR)
app._viajar_por_portal(s, '(test)', por)
ops = [struct.unpack_from('<H', x, 0)[0] for x in s.enviado]
print("  opcodes:", [hex(o) for o in ops])
assert 0x000C not in ops, "NO debe cambiar de mapa"
assert ops == [0x0016, 0x0012, 0x0003], ops
assert s.personaje.stage == 228
assert (s.personaje.tile_x, s.personaje.tile_y) == (195, 69)
print("  sigue en el stage 228 y ahora esta en (195,69)")

print("\n=== 3. Los bytes, contra lo capturado ===")
# 0x0016: entidad 286, direccion 5
assert s.enviado[0] == bytes.fromhex('16001e01000005'), s.enviado[0].hex()
# 0x0012: SIETE ceros, no nueve
assert s.enviado[1] == bytes.fromhex('120000000000000000'), s.enviado[1].hex()
assert len(s.enviado[1]) == 2 + 7
# 0x0003: entidad 286 a (195,69) = 0xc3, 0x45
assert s.enviado[2] == bytes.fromhex('03001e010000c300000045000000'), s.enviado[2].hex()
for b in s.enviado:
    print("  %s" % b.hex())
print("  los tres coinciden byte a byte con la captura")

print("\n=== 4. El sentido contrario ===")
s = _Ses(228, (196, 74))
app._viajar_por_portal(s, '(test)', app._portal_en(228, *NORTE))
ops = [struct.unpack_from('<H', x, 0)[0] for x in s.enviado]
assert 0x000C not in ops and ops == [0x0016, 0x0012, 0x0003]
assert (s.personaje.tile_x, s.personaje.tile_y) == (239, 149)
assert s.enviado[0][-1] == 1, "la direccion al llegar al sur es 1"
print("  llega a (239,149) mirando hacia 1")

print("\n=== 5. Las llegadas no rebotan ===")
# Cada llegada tiene que quedar FUERA del radio del portal de vuelta.
for lleg, otro in [((195, 69), NORTE), ((191, 76), NORTE),
                   ((239, 149), SUR), ((235, 153), SUR)]:
    d = max(abs(lleg[0] - otro[0]), abs(lleg[1] - otro[1]))
    assert app._portal_en(228, *lleg) is None, lleg
    print("  llegada %-11s a %2d del otro portal: no dispara" % (str(lleg), d))

print("\n=== 6. Los seis tramos medidos SI disparan ===")
for tramo, esp in [((227, 145), SUR), ((227, 144), SUR), ((224, 143), SUR),
                   ((196, 74), NORTE), ((197, 74), NORTE), ((200, 76), NORTE)]:
    p = app._portal_en(228, *tramo)
    assert p is not None and tuple(p['tile']) == esp, (tramo, p)
    print("  tramo %-11s -> portal %s" % (str(tramo), esp))

print("\n=== 7. Los portales normales del mapa siguen igual ===")
for tile, esp in [((287, 32), 225), ((25, 7), 354), ((286, 174), 227)]:
    p = app._portal_en(228, *tile)
    assert p and p['destino'] == esp and not p.get('mismo_mapa')
    print("  %-11s -> stage %d" % (str(tile), esp))

print("\nTODOS LOS TESTS PASARON EXITOSAMENTE!")
