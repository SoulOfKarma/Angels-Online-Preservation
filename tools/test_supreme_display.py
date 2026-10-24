"""PLV is a client state bit, never a replacement for the real level."""
import copy
import pathlib
import struct
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import combate
import login
import presencia
import supremo


def player(level=410, completed=True):
    p = login.Personaje(nivel=level, char_id=0,
                        habilidades=[(sid, level, sid * 1000) for sid in range(1, 10)])
    p.logros_cont = {'supremo': 1} if completed else {}
    return p


@pytest.mark.parametrize('level,completed,active', [
    (400, True, False), (401, False, False), (410, False, False),
    (401, True, True), (410, True, True), (450, True, True),
])
def test_state_requires_both_level_and_quest(level, completed, active):
    p = player(level, completed)
    before = copy.deepcopy(p.__dict__)
    assert bool(supremo.estado(p) & supremo.ESTADO_SUPREMO) is active
    assert supremo.estado(p) & supremo.ESTADO_PROPIO
    assert p.__dict__ == before


def test_real_state_packet_does_not_send_level_ten():
    p = player()
    packet = supremo.paquete_estado(p)
    assert packet == combate.atributo(p.entity_id, 0x82000000, combate.KIND_ESTADO)
    assert p.nivel == 410 and len(p.habilidades) == 9


def test_ghost_then_revive_keeps_supreme_and_house_flags():
    p = player()
    ghost = supremo.ESTADO_PROPIO | combate.ESTADO_FANTASMA
    assert supremo.estado(p, base=ghost) == 0x8A000000
    assert supremo.estado(p) == 0x82000000


@pytest.mark.parametrize('completed', [False, True])
def test_full_character_packet_has_state_and_actual_level(completed):
    p = player(completed=completed)
    before = copy.deepcopy(p.habilidades)
    packet = login.ficha_actual(p)
    assert packet[:2] == b'\x02\x00'
    assert struct.unpack_from('<I', packet, 6)[0] == supremo.estado(p)
    assert struct.unpack_from('<I', packet, 67)[0] == 410
    assert p.habilidades == before


@pytest.mark.parametrize('completed', [False, True])
def test_public_spawn_uses_supreme_bit_not_private_house_bit(completed):
    p = player(completed=completed)
    s = SimpleNamespace(personaje=p, inventario={}, _entidad_publica=2345)
    packet = presencia._spawn(s)
    assert struct.unpack_from('<I', packet, 6)[0] == (
        supremo.ESTADO_SUPREMO if completed else 0)


def test_real_ghost_and_revive_handlers_preserve_supreme(monkeypatch):
    import app
    p = player()
    packets = []
    s = SimpleNamespace(personaje=p, rol='mundo', entity_id=p.entity_id,
                        muerto=True, inventario={}, usuario=None,
                        enviar=lambda *pk: packets.extend(pk))
    monkeypatch.setattr(app, '_sincronizar_cambio_mapa', lambda *a: None)
    server = app.Servidor.__new__(app.Servidor)
    server.manejar(s, 0x0016, None, None, 'test', struct.pack('<BI', 3, 0))
    assert s.fantasma
    assert supremo.paquete_estado(p, supremo.ESTADO_PROPIO | combate.ESTADO_FANTASMA) in packets
    packets.clear()
    server.manejar(s, 0x0016, None, None, 'test', struct.pack('<BI', 2, 0))
    assert not s.muerto and not s.fantasma
    assert supremo.paquete_estado(p) in packets
    assert p.nivel == 410 and len(p.habilidades) == 9
