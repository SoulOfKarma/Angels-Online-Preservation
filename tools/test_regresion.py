"""
Prueba de regresion de los dos crashes que mataban sesiones en el emulador viejo.

  1. packet_builders.py:784  struct.pack('<HIIIIIH', ...)  con y = -3
     -> struct.error: argument out of range   (sesion muerta, sin pista de que campo)

  2. handlers/npc.py:489     struct.pack('<HIIIIIB', ...)  con 6 de 7 argumentos
     -> struct.error: pack expected 7 items for packing (got 6)

Ambos escapaban hasta _handle_client y cerraban la conexion del jugador.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'proto'))
from codec import Msg
import messages

MOVE = Msg.registry[(0x0005, 's2c', '*')]

print("CASO 1: coordenada negativa (caminar hacia el borde norte del mapa)")
try:
    MOVE.build(entity_id=7, cur_x=1000, cur_y=37, dst_x=1040, dst_y=-3, speed=110)
    print("   FALLO: deberia haber sido rechazado")
except ValueError as e:
    print(f"   rechazado con mensaje util -> {e}")

print("\nCASO 2: falta un campo")
try:
    MOVE.build(entity_id=7, cur_x=1000, cur_y=37, dst_x=1040, dst_y=431)
    print("   FALLO: deberia haber sido rechazado")
except KeyError as e:
    print(f"   rechazado nombrando el campo -> {e}")

print("\nCASO 3: uso correcto")
b = MOVE.build(entity_id=7, cur_x=5200, cur_y=2383, dst_x=5072, dst_y=2543, speed=50)
print(f"   {len(b)} bytes: {b.hex(' ')}")
d = MOVE.parse(b[2:])
print(f"   reparseado: entity={d['entity_id']} cur=({d['cur_x']},{d['cur_y']}) "
      f"dst=({d['dst_x']},{d['dst_y']}) speed={d['speed']}")
print(f"   roundtrip exacto: {MOVE.roundtrip(b[2:])}")
print("\n   ^ estos son los valores de una muestra real del servidor privado")
