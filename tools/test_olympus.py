"""Native data + real NPC router, with temporary accounts only."""
import copy
import json
import sqlite3
import struct

import pytest
from test_competiciones import world,stored
from test_competition_proxy_admission import click,answer,mid
import app
import olympus as ot
import dialogos_mapa
import eventos
import eventos_mundo as em
import ranking
import login


@pytest.fixture
def town(world):
    s=world.player(items={20:54260})
    s.personaje.stage=41;s.personaje.tile_x=39;s.personaje.tile_y=16
    return world,s


def ozzy(s):
    s.personaje.tile_x=44;s.personaje.tile_y=14
    click(s,71410002)
    answer(s,0)


def test_olly_exact_native_greeting_menu_information_and_entry(town):
    w,s=town
    click(s,71410001)
    assert mid(s)==8312
    assert [struct.unpack_from('<I',line)[0] for line in s.dlg_guion]==[8312,8353]
    assert [o[0] for o in s.dlg_mapa['opciones']]==[512558,8313,8314,8315,8316,8317]
    answer(s)
    assert struct.unpack_from('<I',s.packets[-1],2)[0]==8353
    answer(s,3)
    assert mid(s)==8323 and len(s.dlg_guion)==9
    assert struct.unpack_from('<I',s.dlg_guion[-1])[0]==8331
    click(s,71410001);answer(s,0)
    assert w.trips[-1][1]==217


def test_mark_blocks_entry_and_has_original_not_renewed_duration(town):
    w,s=town
    s.personaje.buffs={8561:{'fin':w.now[0]+50}}
    click(s,71410001);answer(s,0)
    assert mid(s)==8340 and not w.trips
    assert s.personaje.buffs[8561]['fin']==w.now[0]+50


def test_no_teleport_or_exchange_from_remote_npc(town):
    w,s=town
    s.personaje.tile_x=200
    click(s,71410001)
    assert not w.trips and not getattr(s,'dlg_mapa',None)
    assert stored(w,s)['inventario']=={'20':54260}


def test_ozzy_atomic_daily_claim_and_original_success_reject(town):
    w,s=town
    ozzy(s)
    assert mid(s)==511657 and 54262 in s.inventario.values()
    assert 54260 not in s.inventario.values()
    snapshot=copy.deepcopy(stored(w,s))
    ozzy(s)
    assert mid(s)==511658 and stored(w,s)==snapshot
    w.now[0]+=86401
    ozzy(s)
    assert mid(s)==511659


def test_ozzy_full_bag_keeps_coin_and_allows_retry(town,monkeypatch):
    w,s=town
    monkeypatch.setattr(app,'_tope_bolsa',lambda bag:20)
    ozzy(s)
    assert mid(s)==511660 and s.inventario=={20:54260}
    monkeypatch.setattr(app,'_tope_bolsa',lambda bag:40)
    ozzy(s)
    assert mid(s)==511657


def test_olympus_exchange_opens_original_group_and_requires_olly(town):
    w,s=town
    click(s,71410001);answer(s,2)
    assert s._lyceum_exchange==280 and struct.pack('<HI',0x0151,280) in s.packets


def test_floor_population_is_finite_and_counts_real_generator(town):
    w,s=town;s.personaje.stage=217
    assert ot.generar(s,217,71)
    assert len(s.monstruos)==15
    assert len({tuple(m.tile) for m in s.monstruos.values()})==15
    assert {m.npc_type for m in s.monstruos.values()}=={10870}
    assert all(m.hp_max>50 and m.zona_plantilla==71 for m in s.monstruos.values())
    for m in s.monstruos.values():m.hp=0
    before=set(s.monstruos)
    assert ot.generar(s,217,71) and set(s.monstruos)==before


def test_each_account_gets_its_own_tower_even_with_legacy_same_charid(town):
    w,s=town;t=w.player();t.personaje.stage=s.personaje.stage=217
    t.personaje.char_id=s.personaje.char_id
    assert em._clave_corrida(s)!=em._clave_corrida(t)
    assert em.estado_de(s) is not em.estado_de(t)


def test_start_complete_record_rank_and_reconnect_same_clock(town,monkeypatch):
    w,s=town;s.personaje.stage=217
    monkeypatch.setattr(app,'_buff_a_otro',lambda s,mid,entry,*a:s.personaje.buffs.update({mid:entry}))
    assert ot.efecto(s,111,3600000)
    rid=s._olympus_run
    assert s.personaje.buffs[8561]['fin']==w.now[0]+79200
    assert struct.pack('<HI',0x016A,3600) in s.packets
    w.now[0]+=10;s.personaje.stage=332
    assert ot.efecto(s,111,1800000) and s._olympus_run==rid
    assert len(s.packets)==1  # buff sender replaced above; no second timer
    em.estado_de(s)
    ot.al_entrar(s)
    assert s.packets[-1]==struct.pack('<HI',0x016A,3590)
    assert not ot.clasificacion(38)
    assert ot.efecto(s,112)
    s.personaje.stage=217;s.personaje.tile_x=40;s.personaje.tile_y=126
    click(s,74170538);answer(s,0)
    assert mid(s)==8310
    rows=ot.clasificacion(38)
    assert len(rows)==1 and rows[0]['puntos']==3590
    assert ranking.lista(38)==rows
    assert ranking.lista(38,0)==[]
    click(s,74170538);answer(s,0)
    assert mid(s)==8348 and len(ot.clasificacion(38))==1


def test_timer_timeout_uses_original_return_tag(town,monkeypatch):
    w,s=town;s.personaje.stage=217
    monkeypatch.setattr(app,'_buff_a_otro',lambda s,mid,entry,*a:s.personaje.buffs.update({mid:entry}))
    ot.efecto(s,111,1000);w.now[0]+=2
    ot.tick(s)
    assert w.trips[-1][1]==41 and not ot.clasificacion(38)


def test_no_weekly_prize_is_reported_as_claimed(town):
    w,s=town
    click(s,71410001);answer(s,1)
    assert mid(s)==8318 and s.inventario=={20:54260}


def test_tower_spawn_has_omos_and_objects_but_not_all_floor_mobs():
    packets=ot.poblar(217)
    assert any(b'Omos' in p for p in packets)
    assert len(packets)==23
    assert not any(b'Ollus' in p for p in packets)
    assert eventos.traducir(111,[1800000])==('olympus',111,1800000)


def test_original_start_generates_first_floor_and_gate_waits_for_every_mob(town,monkeypatch):
    w,s=town;s.personaje.stage=217
    monkeypatch.setattr(app,'_buff_a_otro',lambda s,mid,entry,*a:s.personaje.buffs.update({mid:entry}))
    monkeypatch.setattr(app,'_viajar_dentro_del_mapa',lambda *a,**kw:None)
    assert app._recorrer_dialogo_mapa(s,'test',217,1000006)
    assert len(s.monstruos)==60
    effects=em.al_pisar(s,(344,85))
    assert ('dialogo',10004) in effects
    for m in s.monstruos.values():m.hp=0
    effects=em.al_pisar(s,(344,85))
    assert ('ir_a_tag',3) in effects and ('dialogo',10004) not in effects
    app._aplicar_efectos(s,'test',effects)
    assert len(s.monstruos)>60


def test_compiled_population_is_walkable_distinct_and_matches_native_counts():
    import transitable
    from mapa_del_cliente import mapa
    for stage in (217,332):
        spawns=[r for r in ot.datos()['maps'][str(stage)]['spawns'] if r['monstruo']]
        assert len(spawns)==sum(g['cantidad'] for g in mapa(stage).generadores())
        assert len({tuple(r['tile']) for r in spawns})==len(spawns)
        assert all(transitable.se_pisa(stage,*r['tile']) for r in spawns)


def test_first_floor_is_spread_across_platform_and_regular_mobs_are_passive(town):
    w,s=town
    from collections import deque
    import transitable
    for stage in (217,332):
        rows=[r for r in ot.datos()['maps'][str(stage)]['spawns'] if r.get('zona') in (71,72,73,74)]
        assert len(rows)==60
        tiles=[tuple(r['tile']) for r in rows]
        assert min(max(abs(a[0]-b[0]),abs(a[1]-b[1])) for i,a in enumerate(tiles) for b in tiles[i+1:])>=3
        assert max(x for x,y in tiles)-min(x for x,y in tiles)>=50
        reachable={tiles[0]};q=deque(reachable)
        while q:
            x,y=q.popleft()
            for t in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if t not in reachable and transitable.se_pisa(stage,*t):reachable.add(t);q.append(t)
        assert set(tiles)<=reachable
    s.personaje.stage=217;ot.generar(s,217,71)
    assert all(m.agro==0 for m in s.monstruos.values())


def test_original_lyceum_portal_is_visible_and_preserves_fog_dialogue(town):
    w,s=town
    entrance=ot.datos()['entrance']
    assert entrance['tile']==[17,7] and entrance['sprite']==60001
    packets=ot.poblar(41)
    portal=next(p for p in packets if p[:2]==b'\x0e\0' and struct.unpack_from('<I',p,2)[0]==entrance['entity'])
    assert struct.unpack_from('<II',portal,10)==(17*32+16,7*32+16)
    assert struct.unpack_from('<I',portal,36)[0]==60001
    s.personaje.tile_x,s.personaje.tile_y=17,7
    click(s,entrance['entity'])
    assert mid(s)==512557 and not w.trips


def test_heart_box_grants_five_and_heart_removes_only_olympus_mark(town):
    w,s=town
    ozzy(s)
    slot=next(k for k,v in s.inventario.items() if v==54262)
    assert ot.usar(s,slot)
    heart=next(k for k,v in s.inventario.items() if v==54904)
    assert s.cantidades[heart]==5
    s.personaje.buffs={8561:{'fin':w.now[0]+60},9999:{'fin':w.now[0]+30}}
    s.personaje.stage=217
    assert ot.usar(s,heart) and s.cantidades[heart]==5 and 8561 in s.personaje.buffs
    s.personaje.stage=41
    assert ot.usar(s,heart) and s.cantidades[heart]==4
    assert s.personaje.buffs=={9999:{'fin':w.now[0]+30}}
    assert stored(w,s)['buffs']=={'9999':{'fin':w.now[0]+30}}
    assert ot.usar(s,heart) and s.cantidades[heart]==4
