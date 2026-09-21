import os
import sys
import struct
import time
import asyncio

sys.path.insert(0, os.path.abspath('server'))
import combate as cb
import app

class MockPersonaje:
    def __init__(self):
        self.entity_id = 0x078300c0
        self.char_id = 4980
        self.nombre = "Karmav2"
        self.hp = 200
        self.hp_max = 304
        self.mp = 94
        self.mp_max = 154
        self.nivel = 1
        self.exp = 0
        self.oro = 0
        self.habilidades = [(9, 1, 0)]
        self.buffs = {}
        self.tile_x = 246
        self.tile_y = 19
        self.stage = 57

class MockSession:
    def __init__(self):
        self.rol = 'mundo'
        self.entity_id = 0x078300c0
        self.personaje = MockPersonaje()
        self.inventario = {}
        self.conectado = True
        self.sentado = False
        self.ultimo_movimiento = 0
        self.ultimo_combate = 0
        self.ultimo_regen_tick = 0
        self.salida = []
        self.vistos = {}

    def enviar(self, *pkgs):
        self.salida.extend(pkgs)

    def drenar(self):
        s = b''.join(self.salida)
        self.salida.clear()
        return s

def test_sitting_toggle():
    srv = app.Servidor(16768, 16769, 21238)
    ses = MockSession()
    addr = ('127.0.0.1', 12345)

    # 1. Press Insert while standing (c2s 0x0016 len=5: action=4)
    srv.manejar(ses, 0x0016, None, {}, addr, cuerpo=struct.pack('<IB', 4, 0))
    assert ses.sentado is True, "Player should be sitting"
    assert len(ses.salida) == 1, f"Should send 1 packet, got {len(ses.salida)}"
    raw = ses.salida.pop(0)
    op, eid, tgt, act = struct.unpack('<HIII', raw)
    assert op == 0x000A and act == 8, f"Should send 0x000A action 8 (sit down), got op={hex(op)} act={act}"

    # 2. Press Insert while sitting
    srv.manejar(ses, 0x0016, None, {}, addr, cuerpo=struct.pack('<IB', 4, 0))
    assert ses.sentado is False, "Player should be standing"
    raw = ses.salida.pop(0)
    op, eid, tgt, act = struct.unpack('<HIII', raw)
    assert op == 0x000A and act == 0, f"Should send 0x000A action 0 (stand up), got act={act}"

    # 3. Sit down then move
    srv.manejar(ses, 0x0016, None, {}, addr, cuerpo=struct.pack('<IB', 4, 0))
    assert ses.sentado is True
    ses.salida.clear()

    # Move (0x0004)
    d = {'cur_x': 246*32, 'cur_y': 19*32, 'path': [{'x': 247*32, 'y': 19*32}], 'n': 1}
    srv.manejar(ses, 0x0004, None, d, addr, cuerpo=b'')
    assert ses.sentado is False, "Movement should stand the player up"
    # Check that 0x000A stand up was sent among the output packets
    stand_pkgs = [p for p in ses.salida if len(p) == 14 and p[:2] == b'\x0a\x00' and struct.unpack_from('<I', p, 10)[0] == 0]
    assert len(stand_pkgs) > 0, "Must send 0x000A action 0 when standing up on movement"
    print("test_sitting_toggle passed!")

def test_mp_regeneration_values():
    assert cb.KIND_MP == 2, f"KIND_MP must be 2, got {cb.KIND_MP}"
    assert cb.KIND_HP == 0, f"KIND_HP must be 0, got {cb.KIND_HP}"

    # Check attribute packet
    pkg = cb.atributo(1001, 139, cb.KIND_MP)
    assert pkg[:2] == b'\x13\x00', "Opcode must be 0x0013"
    op, eid, cnt, k, val = struct.unpack('<HIBBI', pkg)
    assert k == 2, f"Kind must be 2, got {k}"
    assert val == 139, f"Val must be 139, got {val}"
    print("test_mp_regeneration_values passed!")

async def test_regeneration_loop():
    srv = app.Servidor(16768, 16769, 21238)
    ses = MockSession()
    ses.personaje.mp = 94
    ses.personaje.mp_max = 154
    ses.sentado = True

    # Start loop as task
    task = asyncio.create_task(srv._bucle_regeneracion(ses))
    # Let it tick once
    await asyncio.sleep(1.05)
    task.cancel()

    assert ses.personaje.mp == 100, f"After 1s sitting, MP should be 100 (94+6), got {ses.personaje.mp}"
    print("test_regeneration_loop passed!")

if __name__ == '__main__':
    test_sitting_toggle()
    test_mp_regeneration_values()
    asyncio.run(test_regeneration_loop())
    print("\nALL SITTING & REGEN TESTS PASSED!")
