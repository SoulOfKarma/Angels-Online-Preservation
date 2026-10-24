"""Clerk proxy packets + real sparse SQLite persistence, no live accounts."""
import copy
import json
import sqlite3
import struct

import pytest
from test_competiciones import world, stored
import app
import clases
import competiciones as c
import competicion_premios as rewards
import cuentas
import dialogos
import holy_battlefield as hb
import inventario as inv
import login


def click(s,entity):
    app.Servidor.__new__(app.Servidor).manejar(s,5,None,None,'test',struct.pack('<IH',entity,0))


def answer(s,index=None):
    value = 1 if index is None else dialogos.PRIMERA_OPCION+index
    app.Servidor.__new__(app.Servidor).manejar(s,11,None,{'valor':value},'test')


def mid(s):
    return struct.unpack_from('<I',s.dlg_guion[0])[0]


@pytest.mark.parametrize('eid,expected',[(114001,7577),(114003,7577),(114004,7577),(114002,7607)])
def test_closed_response_matches_proxy_byte_for_byte(world,eid,expected):
    s = world.player()
    click(s,eid)
    answer(s,1)
    portrait = 69 if eid==114002 else 71
    assert s.packets[-1]==struct.pack('<HIHBBB',18,expected,portrait,0,0,0)
    assert s.dlg_mapa is None and len(s.dlg_guion)==1
    assert s.personaje.stage==114
    answer(s)
    assert s.packets[-1]==struct.pack('<H',18)+bytes(9)


def test_arena_root_matches_measured_celestia_and_play_packet(world):
    s = world.player()
    click(s,114004)
    # mundo_192143_533481, t3.8668 and mundo_185855_203071,t8.4345.
    payload = bytes.fromhex('ae20000047000005007f1d0000801d0000811d0000471e00009c130000d0420f00de420f00e6420f00e9420f0000000000')
    assert s.packets[-1]==struct.pack('<H',18)+payload


def test_holy_root_matches_measured_profile_with_spectator_option(world):
    s = world.player()
    click(s,114002)
    payload = bytes.fromhex('9d1d000045000005009e1d00009f1d0000a01d0000a11d0000a21d000055420f0056420f0057420f0058420f0000000000')
    assert s.packets[-1]==struct.pack('<H',18)+payload


@pytest.mark.parametrize('level,stage,eid,fee',[(270,239,114003,4000000),(303,239,114003,8000000),(434,240,114004,8000000)])
def test_sparse_real_save_singletons_and_login_deed_allow_paid_admission(world,level,stage,eid,fee):
    s = world.player(level=level,items={20:8536,21:8534},gold=fee+100)
    s.cantidades.update({20:1,21:50,99:1})  # the last is a harmless orphan count
    cuentas.guardar_inventario(s.usuario,s.personaje.char_id,s.inventario,s.cantidades)
    assert stored(world,s)['cantidades']=={'21':50}
    s.inventario[376] = 10115  # login's derived house slot, not an inventory mutation
    c.iniciar(stage,5,15,level)
    click(s,eid)
    answer(s,1)
    assert mid(s)==7571
    assert any(('Registration fee: %s gold.' % format(fee,',')).encode() in p for p in s.packets)
    assert s.oro==fee+100 and s.personaje.stage==114
    answer(s,0)
    assert mid(s)==7574 and s.oro==fee+100
    answer(s)
    assert s.personaje.stage==stage and s.oro==100
    assert stored(world,s)['oro']==100
    # Same acknowledgement cannot charge twice.
    answer(s)
    assert s.oro==100


def test_semantic_comparison_still_rejects_real_item_or_stack_races(world):
    s = world.player(items={20:8537})
    s.cantidades[20] = 2
    world.save(s)
    c.iniciar(112,5,15)
    before = stored(world,s)
    with sqlite3.connect(world.db) as con:
        changed = copy.deepcopy(before)
        changed['cantidades']={'20':3}
        con.execute('UPDATE personajes SET datos=? WHERE char_id=?',(json.dumps(changed),s.personaje.char_id))
    with pytest.raises(c.Rechazo,match='inventory/gold changed'):
        c.entrada(s,112)
    assert stored(world,s)['cantidades']=={'20':3}
    assert not c.ronda(112)['miembros'] and s.cantidades[20]==2


def test_insufficient_funds_and_wrong_level_have_original_dialogues(world):
    s = world.player(level=434,gold=7999999)
    c.iniciar(240,5,15,434)
    click(s,114004)
    answer(s,1)
    assert mid(s)==7576 and s.oro==7999999
    c.iniciar(239,5,15,303)
    click(s,114003)
    answer(s,1)
    assert mid(s)==7575 and s.personaje.stage==114


def test_holy_confirmation_then_success_then_admission_uses_single_stone(world):
    s = world.player(items={20:8537})
    s.cantidades[20]=1
    cuentas.guardar_inventario(s.usuario,s.personaje.char_id,s.inventario,s.cantidades)
    c.iniciar(112,5,15)
    click(s,114002)
    answer(s,1)
    assert mid(s)==7571 and s.inventario[20]==8537
    answer(s,0)
    assert mid(s)==7604 and s.inventario[20]==8537
    answer(s)
    assert s.personaje.stage==112 and 20 not in s.inventario


def test_decline_and_registration_closing_during_dialogue_never_charge(world):
    s = world.player()
    c.iniciar(240,5,15,434)
    click(s,114004)
    answer(s,1)
    answer(s,1)
    assert s.oro==2_000_000_000 and not c.ronda(240)['miembros']
    click(s,114004)
    answer(s,1)
    answer(s,0)
    world.now[0]+=901
    answer(s)
    assert mid(s)==7577
    assert s.oro==2_000_000_000 and s.personaje.stage==114


def test_real_save_never_discards_opened_pass_deadline(world):
    s = world.player(items={20:16762})
    c.desellar_pase(s,20)
    deadline = s.personaje.mejoras[20]['holy_pass_fin']
    for save in (lambda:cuentas.guardar_mejoras(s.usuario,s.personaje.char_id,s.personaje.mejoras),
                 lambda:cuentas.guardar_inventario(s.usuario,s.personaje.char_id,s.inventario,
                                                   s.cantidades,mejoras=s.personaje.mejoras)):
        save()
        assert stored(world,s)['mejoras']['20']['holy_pass_fin']==deadline
    reloaded = cuentas.personaje_de({'personajes':[dict(stored(world,s),ranura=0,
        char_id=s.personaje.char_id,barra=[],quests=[])]})
    assert reloaded.mejoras[20]['holy_pass_fin']==deadline
    pkt = inv.completo(reloaded.char_id,[(20,16764)],mejoras=reloaded.mejoras)
    assert struct.unpack_from('<I',pkt,53)[0]==int(deadline)


def test_material_contribution_accepts_real_sparse_counts(world):
    s = world.player(items={20:8537,21:8536})
    s.cantidades.update({20:1,21:1})
    cuentas.guardar_inventario(s.usuario,s.personaje.char_id,s.inventario,s.cantidades)
    c.iniciar(112,5,0)
    c.entrada(s,112)
    cuentas.guardar_inventario(s.usuario,s.personaje.char_id,s.inventario,s.cantidades)
    assert hb.construir(s,'idol')==1
    assert 21 not in s.inventario


def test_arena_waits_at_waterfall_then_moves_to_fighting_platform(world):
    import eventos
    s = world.player(level=434)
    c.iniciar(240,5,15,434)
    c.entrada(s,240)
    assert (s.personaje.tile_x,s.personaje.tile_y)==tuple(eventos.casillas_de_tag(240,1)[0])
    world.now[0]+=901
    c.cron(c.dt.datetime.fromtimestamp(world.now[0]))
    assert (s.personaje.tile_x,s.personaje.tile_y)==tuple(eventos.casillas_de_tag(240,2)[0])


def test_no_stone_has_original_holy_reply_without_consumption(world):
    s = world.player()
    c.iniciar(112,5,15)
    click(s,114002)
    answer(s,1)
    assert mid(s)==7605 and s.personaje.stage==114
    assert not c.ronda(112)['miembros']


def test_holy_reentry_cannot_register_or_charge_a_new_player(world):
    s = world.player(items={20:8537})
    c.iniciar(112,5,15)
    click(s,114002)
    answer(s,3)
    assert mid(s)==7612 and s.inventario[20]==8537
    assert not c.ronda(112)['miembros']
