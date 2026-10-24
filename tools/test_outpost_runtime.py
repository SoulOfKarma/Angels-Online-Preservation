"""Regression coverage for permanent PvP, travel and companion lifecycle."""
import json
import pathlib
import struct
import sys
import time
from types import SimpleNamespace as NS

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'server'))
import app
import dialogos
import eventos
import invocaciones_pvp
import outpost_pvp
import presencia
import pvp_liga


def session(stage=48, faction='Aurora', cid=1):
    packets = []
    p = NS(stage=stage, faction=faction, char_id=cid, entity_id=cid,
           tile_x=50, tile_y=50, hp=10000, buffs={})
    return NS(personaje=p, rol='mundo', muerto=False, enviar=lambda *pk: packets.extend(pk),
              packets=packets, _mapa_presencia=stage, usuario=None)


def test_name_with_menu_preserves_actions_and_non_name_parameters():
    raw = dialogos.armar_linea(100, 49, [5080, 5081],
                              ['1', 'Old', '2', '42'], [12345, 0])[2:]
    actual = dialogos._con_nombre(raw, 'KarmaV4')
    assert actual[:25] == raw[:25]
    assert actual[25:] == b'1\0KarmaV4\x002\x0042\0'


@pytest.mark.parametrize('opcode', [4, 5, 6, 7, 22])
def test_old_map_actions_blocked_until_ready(opcode):
    s = session(41)
    s.mapa_cargando = True
    app.Servidor.__new__(app.Servidor).manejar(s, opcode, None, {}, 'test')
    assert not s.packets


@pytest.mark.parametrize('path', [[], [{'x':768, 'y':224}]])
def test_old_position_rejected_before_ack_even_after_load(path):
    s = session(41)
    s.personaje.tile_x, s.personaje.tile_y = 158, 82
    s.mapa_cambiado_en = time.time()
    app.Servidor.__new__(app.Servidor).manejar(s, 4, None,
        {'cur_x':24*32, 'cur_y':7*32, 'path':path}, 'test')
    assert not s.packets
    assert (s.personaje.tile_x, s.personaje.tile_y) == (158,82)


def test_map_dialogue_playername_action_not_hardcoded(monkeypatch):
    import dialogos_mapa
    import eventos_mundo
    s = session(41)
    s.personaje.nombre = 'KarmaV4'
    monkeypatch.setattr(dialogos_mapa, '_arbol', lambda st: {
        '123': {'m':10001, 'c':49, 'a':[[2,[1,0]]]}})
    monkeypatch.setattr(eventos_mundo, 'ContextoSesion', lambda ses: object())
    assert app._recorrer_dialogo_mapa(s, 'test', 41, 123)
    assert b'1\0KarmaV4\0' in s.packets[0]


@pytest.mark.parametrize('stage', [47, 48])
def test_portals_have_original_landings_no_immediate_bounce(stage):
    portals = json.loads((ROOT/'server/plantillas/portales.json').read_text('utf-8'))['mapas'][str(stage)]
    assert len(portals) == 16
    for portal in portals:
        for tile in eventos.casillas_de_tag(stage, portal['outpost_tag']):
            assert all(max(abs(tile[0]-p['tile'][0]), abs(tile[1]-p['tile'][1])) > p['radio'] for p in portals)


@pytest.mark.parametrize('faction,destination', [('Aurora',3), ('Beasts',29), ('Steel',38), ('Shadow',26)])
def test_exit_goes_to_own_city(faction, destination):
    s = session(faction=faction)
    result = outpost_pvp.resolver_portal(s, {'outpost_evento':906})
    assert result['destino'] == destination


def test_foreign_base_denied_and_pvp_mode_cleared():
    s = session(faction='Aurora')
    assert outpost_pvp.resolver_portal(s, {'outpost_evento':902}) is None
    outpost_pvp.al_entrar(s)
    assert s.outpost_modo_pvp
    s.personaje.stage = 41
    outpost_pvp.al_salir(s)
    assert not s.outpost_modo_pvp


def test_companions_despawn_on_departure_and_clear_only_on_disconnect(monkeypatch):
    s = session()
    inv = dict(entity_id=999, hp=100, hp_max=100, objetivo=object())
    s.invocacion = inv
    gone = []
    monkeypatch.setattr(presencia, 'notificar_invocacion_despawn', lambda ses, eid: gone.append(eid))
    monkeypatch.setattr(presencia, 'liberar_entidad', lambda s: None)
    monkeypatch.setattr(presencia, '_vivas', lambda st: [])
    presencia.salir(s)
    assert gone == [999] and s.invocacion is inv and inv['objetivo'] is None
    s.desconectado = True
    presencia.salir(s)
    assert s.invocacion is None


def test_dead_or_expired_summons_not_respawned():
    s = session()
    s.invocacion = dict(entity_id=999, hp=0, hp_max=100)
    s.invocacion2 = dict(entity_id=998, hp=100, hp_max=100, expira=time.time()-1)
    assert presencia.paquetes_invocaciones(s) == []


def test_summon_pvp_uses_own_attack_cadence_and_entity(monkeypatch):
    s, rival = session(), session(faction='Beasts', cid=2)
    inv = dict(entity_id=999, hp=100, tile_x=50, tile_y=50, atk=1000,
               atk_range=3, crit_rate=0, skills=[])
    hits = []
    monkeypatch.setattr(presencia, '_vivas', lambda st: [s, rival])
    monkeypatch.setattr(pvp_liga, '_por_que_no', lambda a,b: '')
    monkeypatch.setattr(app, '_stats_ses', lambda ses: bytes(100))
    monkeypatch.setattr(pvp_liga, 'mitigacion', lambda *a: 0.5)
    monkeypatch.setattr(pvp_liga, '_aplicar', lambda *a, **kw: hits.append((a,kw)))
    assert invocaciones_pvp.tick(s, inv, 100)
    assert 480 <= hits[0][0][2] <= 520
    assert hits[0][1]['origen_eid'] == 999
    invocaciones_pvp.tick(s, inv, 100.1)
    assert len(hits) == 1
    monkeypatch.setattr(pvp_liga, '_por_que_no', lambda a,b: 'same faction')
    assert not invocaciones_pvp.tick(s, inv, 102)


def test_pvp_damage_defense_applied_before_multiplier():
    assert pvp_liga.dano_pvp(1000, 100, 2, 0) == 1800
    assert pvp_liga.dano_pvp(1000, 1100, 2, 0) == round(2000*420/1520)
