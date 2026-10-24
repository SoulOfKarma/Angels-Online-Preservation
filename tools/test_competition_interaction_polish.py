"""Regression coverage for cooldown, stale paths, repair menus and hit cost."""
import struct

import pytest
from test_competiciones import world
from test_holy_battlefield import battle,building
from test_competition_polish_runtime import timers
import app
import combate
import competiciones as c
import competicion_logros
import desplazamientos as dash
import holy_battlefield as hb


@pytest.mark.parametrize('mid',[276,755])
def test_movement_skill_unlocks_and_recasts_after_its_real_cooldown(world,timers,monkeypatch,mid):
    s=world.player()
    s.personaje.stage=9999
    s.sp=10000
    s.personaje.tile_x,s.personaje.tile_y=160,160
    monkeypatch.setattr(app,'_otorgar_skill_exp',lambda *a,**kw:[])
    mag=combate.datos_magia(mid)
    assert dash.lanzar(s,mid,mag,162,160)
    assert not dash.lanzar(s,mid,mag,164,160)
    delay,ready=timers[-1]
    assert delay==mag['cd_ms']/1000
    world.now[0]+=delay
    ready()
    assert struct.pack('<HIBBII',0x1d,s.personaje.entity_id,1,3,mid,0) in s.packets
    assert dash.lanzar(s,mid,mag,164,160)


def test_old_empty_path_cannot_undo_local_blink_but_new_click_is_not_locked(world):
    s=world.player()
    s.personaje.tile_x,s.personaje.tile_y=160,160
    dash.reubicar(s,(172,160))
    s.packets.clear()
    app.Servidor.__new__(app.Servidor).manejar(s,4,None,{'cur_x':160*32,'cur_y':160*32,'path':[]},'test',b'')
    assert (s.personaje.tile_x,s.personaje.tile_y)==(172,160)
    assert s.packets==[app.Msg.registry[(0x006d,'s2c','*')].build()]
    assert not dash.movimiento_obsoleto(s,172*32,160*32)
    assert s._salto_local is None


@pytest.mark.parametrize('team',[1,2])
@pytest.mark.parametrize('kind',['front','home','statue'])
def test_each_teams_builder_answers_each_selection_without_second_click(battle,team,kind):
    w,a,b=battle
    s=a if team==1 else b
    types={'front':(2435,2476),'home':(2436,2477),'statue':(2434,2475)}
    npc=next(n for n in hb.datos()['npcs'] if n['team']==team and n['npc_type'] in types[kind])
    s.personaje.tile_x,s.personaje.tile_y=npc['tile']
    r=c.ronda(112)
    number=6 if kind=='front' else 1
    if kind!='statue':
        for d in hb.datos()['structures']:
            if d['kind']=='guard' and d['team']==team and d['number']==number:
                r['edificios'][str(d['entity'])]=0
        c._guardar(r)
    assert hb.pulsar(s,npc['entity'])
    router=app.Servidor.__new__(app.Servidor)
    def choose(index):
        router.manejar(s,11,None,{'valor':10+index},'test',b'')
    choose(2)
    if kind!='statue':choose(0)
    assert s.dlg_mapa and s.dlg_mapa['guion'] is s.dlg_guion
    assert (hb.idols(c.ronda(112),team)==11 if kind=='statue' else hb.gate_alive(c.ronda(112),team,number))
    # A second choice operates on a fresh menu, rather than silently closing.
    s.packets.clear()
    choose(0)
    assert any(p[:2]==b'\x12\0' for p in s.packets)
    assert s.dlg_mapa and s.dlg_mapa['guion'] is s.dlg_guion


def test_nonlethal_combo_hit_persists_hp_without_achievements_or_full_scene(battle,monkeypatch):
    w,a,b=battle
    hb.publicar(c.ronda(112))
    target=building(c.ronda(112),2,'guard',7)
    monkeypatch.setattr(combate,'ATACANTE',[a])
    calls=[]
    monkeypatch.setattr(competicion_logros,'aplicar',lambda *args:calls.append(args) or [])
    for s in (a,b):s.packets.clear()
    assert target.recibir(1000)>0
    assert calls==[]
    for s in (a,b):
        assert s.packets==[combate.atributo(target.entity_id,target.porcentaje)]
    c._RONDAS.clear();c._BASE=None
    assert hb.monstruos(c.ronda(112))[target.entity_id].hp==target.hp


def test_guardian_warps_at_contact_instead_of_end_of_long_waypoint(battle,timers):
    w,a,b=battle
    a.personaje.tile_x,a.personaje.tile_y=237,223
    assert hb.paso_guardian(a,(244,230),(237,223),demora=7)
    assert len(timers)==1 and timers[0][0]<7
