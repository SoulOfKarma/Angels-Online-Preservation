"""Matia (sp_v28_questnpc.xml) contesta con su arbol de spmsg.xml: con nivel
380 o mas ofrece la mision 1590 en vez de decir que falta nivel."""
import pathlib
import struct
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import app
import login

MATIA = 900 + 12   # npc_por_mapa.json, Aurora City (stage 3)


@pytest.fixture
def world(monkeypatch):
    p = login.Personaje(nivel=425, hp=100, hp_max=1000, mp=100, mp_max=1000, stage=3)
    packets = []
    s = SimpleNamespace(personaje=p, inventario=p.inventario, rol='mundo',
                        entity_id=p.entity_id, monstruos={}, usuario=None, muerto=False,
                        enviar=lambda *pk: packets.extend(pk),
                        enviar_inmediato=lambda *pk: packets.extend(pk))
    monkeypatch.setattr(app, '_stats_ses', lambda *a: b'')
    return SimpleNamespace(p=p, s=s, packets=packets,
                           server=app.Servidor.__new__(app.Servidor))


def click(world, entity):
    world.server.manejar(world.s, 0x0005, None, None, 'test', struct.pack('<IH', entity, 0))


def test_matia_es_la_entidad():
    assert app._msgid_sp(3, MATIA) == 159001


def mensaje(world):
    return struct.unpack_from('<I', world.packets[-1], 2)[0]


def test_matia_ofrece_la_mision_con_nivel_380(world):
    click(world, MATIA)
    assert mensaje(world) == 159002


def test_matia_sin_nivel_dice_que_falta(world):
    world.p.nivel = 100
    click(world, MATIA)
    assert mensaje(world) == 159001


# Antes, con la mision cogida, salia la linea raiz 159001 ("no tienes nivel
# 380") aunque el personaje tuviera 425: misiones.py no tenia nada que ofrecer.
def test_matia_con_la_mision_en_curso_manda_a_bella(world):
    world.p.quests = [[1590, 2]]
    click(world, MATIA)
    assert mensaje(world) == 159013


def test_matia_con_la_mision_hecha_pregunta_por_pistas(world):
    world.p.quests = [[1590, 7]]     # 1590 tiene 6 pasos
    click(world, MATIA)
    assert mensaje(world) == 159014
