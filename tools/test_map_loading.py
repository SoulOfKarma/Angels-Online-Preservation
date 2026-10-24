"""Outpost -> Lyceum crash regression: no world updates between C/9."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'server'))
import app
import clases
import combate
import login
from session import Session
from framing import decode_header, submessages


def packets(s):
    wire = getattr(s,'_test_wire',[])
    raw, out, off = b''.join(wire)+s.drenar(), [], 0
    wire.clear()
    while off < len(raw):
        h = decode_header(raw,off)
        msgs,_ = submessages(raw[off+6:off+6+h['length']])
        out.extend(msgs)
        off += h['wire']
    return out


@pytest.mark.parametrize('method',['enviar','enviar_sin_espejo','enviar_inmediato'])
def test_any_change_map_starts_output_barrier_and_discards_old_scene(method):
    s = Session(('test',0))
    s._test_wire = []
    s.writer = NS(write=s._test_wire.append)
    send = getattr(s,method)
    send(clases.cambiar_mapa(41))
    assert s.mapa_cargando
    assert [op for op,_ in packets(s)] == [12]
    # Exact classes seen after CHANGE_MAP in the failed 17:48:15 recording:
    # damage/effect, attributes/buffs, stats, mob movement.
    send(struct.pack('<H',17)+bytes(23),struct.pack('<H',29)+bytes(14),
         combate.atributo(1001,100,combate.KIND_HP),
         struct.pack('<H',66)+bytes(105),struct.pack('<H',5)+bytes(22))
    assert packets(s) == []


def test_inventory_and_chat_deferred_until_after_new_scene_never_old_animations():
    s = Session(('test',0))
    s.enviar(clases.cambiar_mapa(41))
    packets(s)
    s.enviar(struct.pack('<H',27)+b'inventory',struct.pack('<H',13)+b'notice')
    s.enviar(struct.pack('<H',17)+b'old animation')
    assert packets(s) == []
    s.mapa_cargando = False  # REQ_0009 has arrived; rebuild from authoritative state.
    s.enviar(struct.pack('<H',2)+b'new ficha',struct.pack('<H',66)+b'new stats')
    s.terminar_carga_mapa()
    assert [op for op,_ in packets(s)] == [2,66,27,13]
    assert not s._mapa_ui_diferida


def test_measured_travel_prefix_preserved_but_effect_after_change_removed():
    s = Session(('test',0))
    s.enviar(struct.pack('<H',18)+bytes(7),struct.pack('<H',7)+bytes(5),
             clases.cambiar_mapa(41),struct.pack('<H',17)+b'old effect')
    assert [op for op,_ in packets(s)] == [18,7,12]


def test_login_service_does_not_interpret_redirect_as_world_map():
    s = Session(('test',0))
    s.rol = 'login'
    s.enviar(struct.pack('<H',12)+bytes(20),struct.pack('<H',17)+b'login')
    assert [op for op,_ in packets(s)] == [12,17]
    assert not s.mapa_cargando


@pytest.mark.parametrize('op',[4,5,6,7,22,46,337])
def test_old_actions_and_second_superwing_ignored_while_loading(op):
    s = Session(('test',0))
    s.personaje = login.Personaje(stage=41)
    s.mapa_cargando = True
    app.Servidor.__new__(app.Servidor).manejar(s,op,None,{},'test',bytes(16))
    assert not s.salida


def test_outpost_superwing_uses_protected_transition_and_only_one_item(monkeypatch):
    s = Session(('test',0))
    s.personaje = login.Personaje(stage=48,tile_x=198,tile_y=102,faction='Beasts')
    s.entity_id = s.personaje.entity_id
    s.inventario = s.personaje.inventario = {23:app.ITEM_SUPERWING}
    s.cantidades = {23:2}
    s.instancias = {}
    s.monstruos = {}
    cancelled = []
    s.portal_armado = NS(cancel=lambda:cancelled.append(True))
    monkeypatch.setattr(app,'_monstruos_de',lambda st:{})
    monkeypatch.setattr(app,'_guardar_bolsa',lambda *a:None)
    monkeypatch.setattr(app,'_refrescar',lambda *a,**kw:[])
    monkeypatch.setattr(app,'_stats_ses',lambda *a:struct.pack('<H',66)+bytes(105))
    srv = app.Servidor.__new__(app.Servidor)
    srv.manejar(s,337,None,None,'test',struct.pack('<I',1))
    assert s.personaje.stage == 41 and s.mapa_cargando
    assert s.cantidades[23] == 1 and cancelled == [True]
    assert [op for op,_ in packets(s)][-1] == 12
    srv.manejar(s,337,None,None,'test',struct.pack('<I',1))
    assert s.cantidades[23] == 1 and not s.salida


def test_same_map_superwing_remains_a_local_teleport(monkeypatch):
    s = Session(('test',0))
    s.personaje = login.Personaje(stage=41,tile_x=170,tile_y=80,faction='Beasts')
    s.entity_id = s.personaje.entity_id
    s.inventario = s.personaje.inventario = {23:app.ITEM_SUPERWING}
    s.cantidades = {23:2}
    s.instancias = {}
    monkeypatch.setattr(app,'_guardar_bolsa',lambda *a:None)
    monkeypatch.setattr(app,'_refrescar',lambda *a,**kw:[])
    monkeypatch.setattr(app,'_stats_ses',lambda *a:struct.pack('<H',66)+bytes(105))
    app.Servidor.__new__(app.Servidor).manejar(s,337,None,None,'test',struct.pack('<I',1))
    assert not s.mapa_cargando
    assert [op for op,_ in packets(s)][-1] == 3
    assert s.cantidades[23] == 1


def test_actual_map_ready_handler_flushes_ui_only_after_new_ficha(monkeypatch):
    s = Session(('test',0))
    s.personaje = login.Personaje(stage=41)
    s.entity_id = s.personaje.entity_id
    s.inventario = s.personaje.inventario = {}
    s.cantidades = {}
    s.instancias = {}
    s.monstruos = {}
    s.sp = 2000
    monkeypatch.setattr(app,'_monstruos_de',lambda st:{})
    monkeypatch.setattr(app,'_entrar_en_sala',lambda *a:None)
    monkeypatch.setattr(app,'_tw_al_entrar',lambda *a:None)
    monkeypatch.setattr(app,'_stats_ses',lambda *a:struct.pack('<H',66)+bytes(105))
    monkeypatch.setattr(login,'secuencia',lambda p:[struct.pack('<H',2)+b'ficha'])
    s.enviar(clases.cambiar_mapa(41))
    packets(s)
    s.enviar(struct.pack('<H',27)+b'inventory',struct.pack('<H',17)+b'old animation')
    app.Servidor.__new__(app.Servidor).manejar(s,9,None,{},'test')
    ready = packets(s)
    assert ready[0] == (2,b'ficha')
    assert ready[-1] == (27,b'inventory')
    assert not any(op==17 for op,_ in ready)
    assert not s.mapa_cargando and not s._mapa_ui_diferida
