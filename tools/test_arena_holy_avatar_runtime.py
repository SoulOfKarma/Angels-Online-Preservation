import struct
from types import SimpleNamespace

from test_competiciones import world
import app
import avatar_clones
import combate
import competiciones as c
import holy_battlefield as hb
import presencia


def test_level_cap_and_test_notice_are_not_internal_sentinels(world,monkeypatch):
    monkeypatch.setattr(c,'_modo_pruebas',lambda:True)
    r=c.iniciar(240,30,5,434)
    assert r['max']==combate.nivel_maximo()==471
    assert c.tramo(472) is None
    assert not any(b'10000' in p or b'TEST ROUND' in p for p in world.broadcasts)
    monkeypatch.setattr(combate,'_CURVA_NIVEL',{1:0,480:1})
    assert combate.nivel_maximo()==480 and c.tramo(480)[1]==480


def test_native_hostile_bit_and_team_marks_for_players_and_companions(world):
    a=world.player(items={20:8537})
    c.iniciar(112,60,0)
    c.entrada(a,112)
    a.invocacion=dict(entity_id=900,hp=99)
    a.avatar_clon=dict(entity_id=901,hp=10)
    a.personaje.mascota={'fuera':True};a.pet_entity_id=902
    packets=c.marcas_actor(a)
    hostile=[struct.unpack('<HIBBII',p) for p in packets if p[7]==42]
    assert {p[-2] for p in hostile}=={a.personaje.entity_id,900,901,902}
    assert all(p[-1]==1 for p in hostile)
    assert all(p[-1]==0 for p in (struct.unpack('<HIBBII',p) for p in c.marcas_actor(a,quitar=True) if len(p)==16) if p[3]==42)
    assert any(p[7]==62 and struct.unpack_from('<I',p,8)[0]==1 for p in a.packets)==False
    c.al_entrar(a)
    assert any(p[:2]==b'\x1d\0' and len(p)==16 and p[7]==62 and struct.unpack_from('<I',p,8)[0]==1 for p in a.packets)


def test_phantom_substitute_spawns_complete_doll_and_absorbs_without_replacing_summon(world,monkeypatch):
    a=world.player(items={3:69578,167:82670})
    a.personaje.mp=10000
    a.personaje.apariencia=[0,1,2,3,4]
    a.invocacion={'entity_id':88,'hp':100}
    callbacks=[]
    monkeypatch.setattr(avatar_clones.asyncio,'get_event_loop',lambda:SimpleNamespace(call_later=lambda delay,fn:callbacks.append(fn)))
    stats=bytearray(80)
    for offset in (26,38,46,54):struct.pack_into('<I',stats,offset,1000)
    monkeypatch.setattr(app,'_stats_ses',lambda s:bytes(stats))
    monkeypatch.setattr(app,'_otorgar_skill_exp',lambda *a,**kw:[])
    monkeypatch.setattr(presencia,'notificar_invocacion_spawn',lambda *a:None)
    monkeypatch.setattr(presencia,'notificar_companero_accion',lambda *a:None)
    mag=combate.datos_magia(15617)
    assert mag['es_invocacion'] and not mag['es_buff'] and mag['dur_invoca']==1200
    assert avatar_clones.lanzar(a,15617,mag)
    callbacks.pop()()
    assert a.invocacion['entity_id']==88 and a.avatar_clon['clon_sustituto']
    packet=avatar_clones.spawn(a,a.avatar_clon)
    assert len(packet)==112 and packet[65:70]==bytes([0,4,3,2,1])
    assert struct.unpack_from('<I',packet,70)[0]==82670
    assert struct.unpack_from('<I',packet,102)[0]==69578
    assert avatar_clones.absorber(a,700)==0
    assert a.avatar_clon['hp']==50
    assert avatar_clones.absorber(a,200)==150
    assert a.avatar_clon is None


def test_holy_original_entry_light_doors_and_walk_capture(world):
    c.iniciar(112,60,0)
    a,b=world.player(items={20:8537}),world.player(items={20:8537})
    c.entrada(a,112);c.entrada(b,112)
    assert (a.personaje.tile_x,a.personaje.tile_y)==(32,282)
    assert (b.personaje.tile_x,b.personaje.tile_y)==(301,15)
    doors=hb.puertas_base()
    assert len(doors)==3
    assert {struct.unpack_from('<I',p,36)[0] for p in doors}=={60403,60404}
    x,y=c.CRISTALES[2][1]
    a.personaje.tile_x,a.personaje.tile_y=x-1,y
    hb.contacto_cristal(a)
    assert c.ronda(112)['portadores']['2']==a.personaje.char_id
    own=c.CRISTALES[1][1]
    b.personaje.tile_x,b.personaje.tile_y=own
    hb.contacto_cristal(b)
    assert c.ronda(112)['portadores']['1']==b.personaje.char_id


def test_walk_crystal_rejects_dead_own_and_duplicate_then_delivers(world):
    c.iniciar(112,60,0)
    a,b=world.player(items={20:8537}),world.player(items={20:8537})
    c.entrada(a,112);c.entrada(b,112)
    a.personaje.tile_x,a.personaje.tile_y=c.CRISTALES[1][1]
    hb.contacto_cristal(a)
    assert not c.ronda(112)['portadores']  # Own crystal stays home.
    a.personaje.tile_x,a.personaje.tile_y=c.CRISTALES[2][1]
    a.muerto=True
    hb.contacto_cristal(a)
    assert not c.ronda(112)['portadores']
    a.muerto=False
    hb.contacto_cristal(a);hb.contacto_cristal(a)
    assert c.ronda(112)['portadores']=={'2':a.personaje.char_id}
    assert 3141 in a.personaje.buffs
    angel=next(eid for eid,(team,tile) in c.ENTREGAS.items() if team==1)
    a.personaje.tile_x,a.personaje.tile_y=c.ENTREGAS[angel][1]
    c.pulsar(a,angel);c.pulsar(a,angel)
    assert c.ronda(112)['puntos']['1']==1
    assert not c.ronda(112)['portadores'] and 3141 not in a.personaje.buffs
