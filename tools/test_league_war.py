"""Native GvG packets and transactional battle/redemption in temporary SQL."""
import copy
import datetime as dt
import json
import sqlite3
import struct
import pytest
from test_competiciones import world,stored
import app
import cuentas
import gremios
import league_war as war
import recent_mall


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(war,'_DB',None);monkeypatch.setattr(war,'_ROUND',None);monkeypatch.setattr(war,'_ROOMS',{})
    monkeypatch.setattr(war.random,'shuffle',lambda xs:None)


def guild(world,s,name,level=6):
    # Exercise the actual guild lookup/schema, not a fake membership predicate.
    cuentas._init_db()
    gid=cuentas.db_crear_gremio(name,s.personaje.char_id,s.personaje.nombre)
    with sqlite3.connect(world.db) as con:con.execute('UPDATE gremios SET nivel=? WHERE guild_id=?',(level,gid))
    return gid


def two(world):
    a=world.player();b=world.player();guild(world,a,'Alpha');guild(world,b,'Beta')
    war.start(10,60);war.register(a,265);war.register(b,265);world.now[0]+=10;war.enter(a);war.enter(b)
    war.loaded(a);war.loaded(b);war.cron();return a,b


def battle(world):
    a,b=two(world);return a,b


def credit(s,points):
    with cuentas._get_conn() as con:
        war._schema(con);con.execute('INSERT OR REPLACE INTO gvg_wallet VALUES(?,?,?)',(s.usuario.casefold(),s.personaje.char_id,points))


def test_original_schedule_eight_maps_native_mines_and_screenshot_prizes(world):
    cfg=war.config()
    assert cfg['schedules']==[{'weekday':2,'start':'21:00'},{'weekday':6,'start':'17:00'},{'weekday':6,'start':'22:30'}]
    offers={o['item']:o['price'] for o in cfg['shop']}
    assert offers[48007]==300 and offers[48015]==600 and offers[48017]==150 and offers[48018]==200
    assert offers[43302]==20 and offers[48051]==10 and offers[48072]==5
    for st in war.STAGES:
        assert len(cfg['maps'][str(st)]['objectives'])==2
        assert len(war.portals(st))==2 and war.resources(st)
        assert all(r['material']==639 for r in war.resources(st))
        assert __import__('transitable').conocido(st)


def test_registration_leader_level_duplicate_full_and_native_listing(world):
    a=world.player();gid=guild(world,a,'Alpha',5);war.start(10)
    with pytest.raises(ValueError,match='Level 6'):war.register(a,265)
    with sqlite3.connect(world.db) as con:con.execute('UPDATE gremios SET nivel=6 WHERE guild_id=?',(gid,))
    b=world.player();cuentas.db_agregar_miembro_gremio(gid,b.personaje.char_id,b.personaje.nombre)
    with pytest.raises(ValueError,match='Leader'):war.register(b,265)
    war.register(a,265)
    with pytest.raises(ValueError,match='already'):war.register(a,266)
    outsider=world.player();guild(world,outsider,'Beta');war.register(outsider,265)
    third=world.player();guild(world,third,'Gamma');war.register(third,265)
    with pytest.raises(ValueError,match='entry opens'):war.enter(third)
    srv=app.Servidor.__new__(app.Servidor);srv.mundos=world.players
    srv.manejar(a,0x16,None,None,'test',struct.pack('<BI',64,0))
    assert {struct.unpack_from('<H',p)[0] for p in a.packets}>={0x173,0x174,0x175,0x176}
    listing=next(p for p in a.packets if p[:2]==b'\x73\x01')
    assert len(listing)==6+40 and struct.unpack_from('<I',listing,6)[0]==265
    row=struct.unpack_from('<10I',listing,6)
    date=dt.datetime.fromtimestamp(war.current()['start'])
    assert row[3]==date.year*10000+date.month*100+date.day
    assert max(row[4:8])<1440
    before=copy.deepcopy(war.current());war.process(a,0x158,struct.pack('<BII',0,266,0))
    assert before==war.current() and b'expired' in a.packets[-1]


def test_two_leagues_share_room_both_auras_and_enemy_only_damage(world):
    a,b=two(world)
    assert app._sala_para(a) is app._sala_para(b)
    assert war.motivo_pvp(a,b)==''
    world.now[0]+=10;war.cron()
    assert __import__('pvp_liga').permitido(a,b)
    ally=world.player();g=gremios.obtener_gremio_de(a.personaje.char_id)
    cuentas.db_agregar_miembro_gremio(g['guild_id'],ally.personaje.char_id,ally.personaje.nombre)
    war.enter(ally);war.loaded(ally)
    assert not __import__('pvp_liga').permitido(a,ally)
    own,enemy=sorted(a.monstruos.values(),key=lambda m:m.gvg_team)
    assert not war.can_target(a,own) and war.can_target(a,enemy)
    for s in (a,b):
        assert any(p[:2]==b'\x1d\0' and len(p)==16 and p[7]==63 and struct.unpack_from('<I',p,8)[0]==1 for p in s.packets)
    cuentas.db_remover_miembro_gremio(b.personaje.char_id)
    assert war.motivo_pvp(a,b) and not war.can_target(b,own)


def test_statue_and_kill_points_once_no_normal_loot_or_exp(world,monkeypatch):
    a,b=battle(world)
    monkeypatch.setattr(__import__('competiciones'),'_reubicar',lambda s,st,tile:None)
    enemy=next(m for m in a.monstruos.values() if m.gvg_team==2)
    enemy.hp=0;enemy.vivo=False
    app._procesar_muerte_monstruo(a,enemy,a.personaje.entity_id,'test')
    assert war.current()['matches'][str(a.personaje.stage)]['scores']['1']==20
    app._procesar_muerte_monstruo(a,enemy,a.personaje.entity_id,'test')
    assert war.current()['matches'][str(a.personaje.stage)]['scores']['1']==20
    b.personaje.hp=0;b.muerto=True;war.kill(a,b)
    assert war.current()['matches'][str(a.personaje.stage)]['scores']['1']==100 and b.muerto
    war.kill(a,b);assert war.current()['matches'][str(a.personaje.stage)]['scores']['1']==100
    world.now[0]+=5;war.cron();assert not b.muerto
    war.kill(a,b);assert war.current()['matches'][str(a.personaje.stage)]['scores']['1']==100
    war._ROOMS.clear();assert not next(m for m in war.room(a.personaje.stage).monstruos.values() if m.gvg_team==2).vivo


@pytest.mark.parametrize('scores,expected',[(('4','1'),(120,40)),(('2','2'),(80,80)),(('0','7'),(40,120))])
def test_finish_win_draw_loss_persisted_once_and_reconnect(world,scores,expected):
    a,b=battle(world);r=copy.deepcopy(war.current());r['matches'][str(a.personaje.stage)]['scores']={'1':int(scores[0]),'2':int(scores[1])};war._save(r)
    assert war.finish();assert not war.finish()
    assert (war.wallet(a),war.wallet(b))==expected
    assert len(war.ranking(war.periods()[1]))==2
    war._DB=None;assert war.current()['state']=='done'
    assert (war.wallet(a),war.wallet(b))==expected
    before=(war.wallet(a),war.wallet(b));war.cron();assert (war.wallet(a),war.wallet(b))==before


def test_no_opponent_no_rewards_cancel_and_automatic_schedule_once(world):
    s=world.player();guild(world,s,'Solo');war.start(10,10);war.register(s,265)
    world.now[0]+=10;war.enter(s);war.cron();war.finish();assert war.wallet(s)==0
    when=dt.datetime(2026,10,25,16,45)
    world.now[0]=when.timestamp();war.cron(when);ident=war.current()['id']
    war.cron(when);assert war.current()['id']==ident
    war.finish(cancel=True);war.cron(when);assert war.current()['state']=='done'


def test_redemption_exact_prices_atomic_funds_capacity_and_message(world):
    s=world.player();guild(world,s,'Alpha');credit(s,1000)
    # The original reward census now has 38 entries; use the native row ID,
    # not the old provisional index of the potion box.
    potion=next(r['id'] for r in war.config()['shop'] if r['item']==48072)
    war.redeem(s,[(1,1),(potion,2)])
    assert war.wallet(s)==690 and 48007 in s.inventario.values()
    assert sum(s.cantidades.get(k,1) for k,v in s.inventario.items() if v==48072)==2
    assert any(b'rewards delivered' in p for p in s.packets)
    before=copy.deepcopy(stored(world,s))
    with pytest.raises(recent_mall.Rechazo,match='Not enough'):war.redeem(s,[(1,3)])
    assert war.wallet(s)==690 and stored(world,s)==before
    s.inventario.clear();s.inventario.update({i:20 for i in range(20,160)});s.cantidades={i:999 for i in s.inventario};world.save(s)
    with pytest.raises(recent_mall.Rechazo,match='full'):war.redeem(s,[(1,1)])
    assert war.wallet(s)==690


def test_donation_commits_inventory_and_score_together_and_certificate(world):
    a,b=battle(world);a.inventario[20]=37362;a.cantidades[20]=200;world.save(a)
    war.process(a,0x15a,struct.pack('<IBH',10,1,0))
    assert 20 not in a.inventario and war.current()['matches'][str(a.personaje.stage)]['scores']['1']==20
    before=copy.deepcopy(war.current());war.process(a,0x15a,struct.pack('<IBH',10,1,0));assert war.current()==before
    a.inventario[20]=63519;world.save(a);assert war.use(a,20)
    assert war.wallet(a)==120 and 20 not in a.inventario and stored(world,a)['custom_field']=='preserve me'


def test_original_potion_boxes_deliver_twenty_and_full_backpack_preserves_box(world):
    s=world.player(items={20:48072,21:48073})
    recent_mall.usar(s,20);recent_mall.usar(s,21)
    for item in (48053,48054):
        assert sum(s.cantidades.get(k,1) for k,v in s.inventario.items() if v==item)==20


def test_previous_week_and_season_claims_no_replay_or_newcomer_reward(world):
    a,b=battle(world);war.finish();week,season=war.periods()
    world.now[0]+=7*86400;war.claim(a,'week');assert war.wallet(a)==1080
    with pytest.raises(ValueError,match='No unclaimed'):war.claim(a,'week')
    newcomer=world.player();gid=gremios.obtener_gremio_de(a.personaje.char_id)['guild_id']
    cuentas.db_agregar_miembro_gremio(gid,newcomer.personaje.char_id,newcomer.personaje.nombre)
    with pytest.raises(ValueError):war.claim(newcomer,'week')
    world.now[0]+=28*86400
    # Align next season exactly, regardless of starting week within the season.
    nowweek,nowseason=war.periods();world.now[0]-=(nowseason-season-1)*28*86400
    war.claim(a,'season');assert war.wallet(a)==5080


def test_native_production_summons_share_hp_and_robot_removal(world,monkeypatch):
    a,b=battle(world)
    a.personaje.habilidades=[(22,300,0),(28,290,0),(32,300,0)]
    a.inventario[20]=37362;a.cantidades[20]=200;world.save(a)
    own=next(m for m in a.monstruos.values() if m.gvg_team==1);own.hp-=200
    war.infuse(a,2)
    assert a.cantidades[20]==100 and a.monstruos is b.monstruos
    assert own.hp==own.hp_max-200
    summon=next(m for m in a.monstruos.values() if hasattr(m,'gvg_owner'))
    assert 'Mercenary' in summon.nombre and summon.npc_type==17098
    assert not war.can_target(a,summon) and war.can_target(b,summon)
    war.infuse(a,4);assert 37388 in a.inventario.values()
    before=copy.deepcopy(stored(world,a))
    with pytest.raises(ValueError,match='already'):war.infuse(a,4)
    assert stored(world,a)==before
    a.personaje.buffs['gvg_field']={'fin':war.current()['end'],'hp_pct':100}
    war.before_travel(a,41)
    assert 37388 not in a.inventario.values() and 'gvg_field' not in a.personaje.buffs
    assert stored(world,a)['custom_field']=='preserve me'


def test_statue_respawn_twenty_seconds_and_repeat_kill_decay(world,monkeypatch):
    a,b=battle(world)
    monkeypatch.setattr(__import__('competiciones'),'_reubicar',lambda *args:None)
    statue=next(m for m in a.monstruos.values() if m.gvg_team==2)
    statue.hp=0;statue.vivo=False;war.monster_dead(a,statue)
    world.now[0]+=19;war.cron();assert not statue.vivo
    world.now[0]+=1;war.cron();assert statue.vivo and statue.hp==statue.hp_max
    for expected in (100,140,160,170):
        b.personaje.hp=0;b.muerto=True;war.kill(a,b)
        assert war.current()['matches'][str(a.personaje.stage)]['scores']['1']==expected
        world.now[0]+=5;war.cron()


def test_mercenary_tick_hits_enemy_and_never_ally(world,monkeypatch):
    a,b=battle(world);a.personaje.habilidades=[(22,300,0)];world.save(a)
    a.inventario[20]=37362;a.cantidades[20]=100;world.save(a);war.infuse(a,2)
    unit=next(m for m in a.monstruos.values() if hasattr(m,'gvg_owner'))
    a.personaje.tile_x=a.personaje.tile_y=0
    b.personaje.tile_x,b.personaje.tile_y=unit.tile_x,unit.tile_y
    b.personaje.hp=1;before=a.personaje.hp
    war.tick()
    assert a.personaje.hp==before and b.muerto
    assert war.current()['matches'][str(a.personaje.stage)]['scores']['1']>0


@pytest.mark.parametrize('spell',[656,645,650,73,269,5515,15090,15612])
def test_native_combat_router_can_hit_statue_or_cast_with_field_bonus(world,monkeypatch,spell):
    a,b=battle(world)
    a.personaje.habilidades=[(9,410,0),(1,410,0),(3,410,0),(15,410,0),(32,410,0)]
    a.personaje.mp=100000;a.sp=10000;a.esfuerzo=1000;a.oro=a.personaje.oro=100000
    a.volcar=lambda:None;a.enviar_sin_espejo=a.enviar
    statue=next(m for m in a.monstruos.values() if m.gvg_team==2)
    a.personaje.tile_x,a.personaje.tile_y=statue.tile_x,statue.tile_y
    before=statue.hp
    router=app.Servidor.__new__(app.Servidor);router.mundos=world.players
    target=0 if spell in (15090,15612) else statue.entity_id
    router.manejar(a,6,None,None,'test',struct.pack('<HI',spell,target))
    if target:assert statue.hp<before


def test_combo_completes_each_hit_without_periodic_battle_window_resets(world,monkeypatch):
    a,b=battle(world)
    a.personaje.habilidades=[(32,410,0)];a.personaje.mp=100000;a.sp=10000
    a.volcar=lambda:None;a.enviar_sin_espejo=a.enviar
    statue=next(m for m in a.monstruos.values() if m.gvg_team==2)
    a.personaje.tile_x,a.personaje.tile_y=statue.tile_x,statue.tile_y
    callbacks=[]
    class Timer:
        def __init__(self):self.dead=False
        def cancelled(self):return self.dead
        def cancel(self):self.dead=True
    def later(delay,fn,*args):
        timer=Timer();callbacks.append((delay,fn,args,timer));return timer
    monkeypatch.setattr(__import__('asyncio'),'get_event_loop',lambda:__import__('types').SimpleNamespace(call_later=later))
    a.packets.clear();war.update(a);war.update(a)
    assert not a.packets
    srv=app.Servidor.__new__(app.Servidor);srv.mundos=world.players
    srv.manejar(a,6,None,None,'test',struct.pack('<HI',5515,statue.entity_id))
    hp=statue.hp
    for delay,fn,args,timer in sorted(callbacks,key=lambda r:r[0]):
        if delay<1 and not timer.cancelled():fn(*args)
    assert statue.hp<hp
    numbers=[p for p in a.packets if p[:2]==b'\x0b\0' and struct.unpack_from('<I',p,2)[0]==statue.entity_id]
    assert len(numbers)==3
    a.packets.clear();r=copy.deepcopy(war.current())
    r['matches'][str(a.personaje.stage)]['scores']['1']+=5;war._save(r);war.update(a)
    assert len(a.packets)==1 and a.packets[0][7]==63
