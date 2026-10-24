"""Production schema permits duplicate legacy char IDs across accounts."""
import json
import sqlite3
import datetime as dt
import struct

from test_competiciones import world, stored
import competicion_identidad as identity
import competicion_logros as awards
import competicion_premios as rewards
import competiciones as c


def test_achievement_write_never_replaces_another_account():
    con = sqlite3.connect(':memory:')
    con.execute('CREATE TABLE personajes(usuario TEXT,ranura INTEGER,char_id INTEGER,nombre TEXT,datos TEXT,PRIMARY KEY(usuario,ranura))')
    original = {'nombre':'KarmaV7','nivel':420,'inventario':{'3':19856},'oro':8122}
    target = {'nombre':'KarmaV6','nivel':434,'inventario':{'3':69578},'oro':1892008122}
    winner = {'nombre':'Winner','nivel':410,'inventario':{'3':123},'oro':99}
    for user,cid,data in [('other',1007,original),('target',1007,target),('winner',1005,winner)]:
        con.execute('INSERT INTO personajes VALUES (?,0,?,?,?)',(user,cid,data['nombre'],json.dumps(data)))
    r = dict(id='collision',stage=240,cerrada=True,motivo='last survivor',clasificacion=['1005','1007'],
             miembros={'1007':dict(usuario='target',nombre='KarmaV6',nivel=434,competidor=True,espectador=True,equipo=0),
                       '1005':dict(usuario='winner',nombre='Winner',nivel=410,competidor=True,espectador=False,equipo=0)})
    awards.aplicar(con,r)
    assert json.loads(con.execute("SELECT datos FROM personajes WHERE usuario='other'").fetchone()[0]) == original
    saved = json.loads(con.execute("SELECT datos FROM personajes WHERE usuario='target'").fetchone()[0])
    assert saved['inventario'] == target['inventario'] and saved['oro'] == target['oro']
    assert saved['nombre'] == 'KarmaV6' and saved['logros_cont']['aa:best_rank'] == 2
    assert saved['logros_cont'].get('aa:win',0) == 0
    awards.aplicar(con,r)
    assert saved == json.loads(con.execute("SELECT datos FROM personajes WHERE usuario='target'").fetchone()[0])
    assert identity.fila(con,1007,{'nombre':'unresolved','nivel':434}) is None
    assert identity.fila(con,1007,{'nombre':'KarmaV6','nivel':434})[0] == 'target'


def test_arena_claim_waits_for_clerk_and_rejects_other_owner(world,monkeypatch):
    import app
    monkeypatch.setattr(app,'_stats_ses',lambda s:b'')
    a,b=world.player(),world.player()
    r=c.iniciar(240,30,0,410)
    for s in (a,b):c.entrada(s,240)
    r=c.ronda(240)
    r['premios_config']=[dict(nivel_min=1,nivel_max=10000,puesto_min=1,puesto_max=1,oro=123)]
    c.baja(a,b)
    gold=stored(world,a)['oro']
    assert rewards.entregar(a,automatico=True)==0
    assert stored(world,a)['oro']==gold
    assert rewards.entregar(a)==1
    assert stored(world,a)['oro']==gold+123
    assert rewards.entregar(a)==0


def test_native_arena_mode_wait_minute_and_clean_finish(world,monkeypatch):
    cfg=c.config_eventos()
    monkeypatch.setattr(c,'config_eventos',lambda:dict(cfg,arena_preparacion_segundos=60))
    r=c.iniciar(240,30,5,410)
    a,b=world.player(),world.player()
    for s in (a,b):c.entrada(s,240)
    assert r['registro_fin'] == world.now[0]+300
    assert r['inicio'] == world.now[0]+360
    world.now[0]=r['registro_fin']
    c.cron(dt.datetime.fromtimestamp(world.now[0]).astimezone())
    assert c.fase(c.ronda(240))=='preparacion'
    assert c.motivo_pvp(a,b)
    world.now[0]=r['inicio']
    c.cron(dt.datetime.fromtimestamp(world.now[0]).astimezone())
    assert c.motivo_pvp(a,b)==''
    assert c.modo_arena(a.personaje.entity_id,True) in a.packets
    a.packets.clear();b.packets.clear();world.trips.clear();world.broadcasts.clear()
    b.muerto=True;b.personaje.hp=0
    c.baja(a,b)
    assert b.personaje.stage==114 and not b.muerto
    assert c.modo_arena(b.personaje.entity_id,False) in b.packets
    assert len(world.trips)==2  # One final map change per player, no extra respawn trip.
    banners=[p for p in world.broadcasts if p[:2]==b'\x28\x01' and p[6]==13]
    assert len(banners)==2
    assert b'1 place : player P1.' in banners[0]
    assert b'2 place : player P2.' in banners[1]
