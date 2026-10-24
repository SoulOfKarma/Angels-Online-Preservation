"""Native protocol/doors regression: isolated accounts, no real database writes."""
import struct
import datetime as dt

import pytest
from test_competiciones import world
from test_holy_battlefield import battle,building
import app
import combate
import competiciones as c
import holy_battlefield as hb
import inventario
import presencia


def test_team_packets_use_real_dispatch_tables_and_do_not_reset_on_registration(world):
    c.iniciar(112,60,5)
    a,b=[world.player(items={20:8537}) for _ in range(2)]
    c.entrada(a,112);c.entrada(b,112)
    for s,team in ((a,1),(b,2)):
        s.invocacion={'entity_id':900+team,'hp':1}
        s.personaje.mascota={'fuera':True};s.pet_entity_id=910+team
        packets=c.marcas_actor(s)
        assert struct.unpack('<HIBBII',packets[0])==(29,s.personaje.entity_id,1,38,1,team)
        assert (19,900+team,1,63,team) in [struct.unpack('<HIBBI',p) for p in packets if len(p)==12]
        assert (19,910+team,1,63,team) in [struct.unpack('<HIBBI',p) for p in packets if len(p)==12]
        assert all(p[7]<66 for p in packets if p[:2]==b'\x1d\0')
        assert all(struct.unpack_from('<I',p,12)[0]==0 for p in packets if len(p)==16 and p[7]==42)


def test_start_replaces_wood_with_team_light_and_deduplicates(world):
    r=c.iniciar(112,60,5)
    s=world.player(items={20:8537});c.entrada(s,112)
    hb.sincronizar_puertas(s,r)
    bases={eid for eid,*_ in hb.bases()}
    assert {struct.unpack_from('<I',p,36)[0] for p in s.packets
            if p[:2]==b'\x0e\0' and struct.unpack_from('<I',p,2)[0] in bases}=={60375,60376}
    s.packets.clear()
    world.now[0]=r['inicio']+1
    c.cron(dt.datetime.fromtimestamp(world.now[0],dt.timezone.utc))
    replacements=[p for p in s.packets if p[:2] in (b'\x07\0',b'\x0e\0')]
    assert len(replacements)==10
    assert all(replacements[i][:2]==b'\x07\0' for i in range(0,10,2))
    assert {struct.unpack_from('<I',p,36)[0] for p in replacements[1::2]}=={60402,60403,60404}
    s.packets.clear();hb.sincronizar_puertas(s,r)
    assert not s.packets


def test_paired_light_passages_follow_original_events_without_refilling(battle):
    w,a,b=battle
    for player,passage in zip((a,b),hb.pasajes()):
        eid,tile,tag=passage
        n=len(w.trips)
        hb.pulsar(player,eid)
        assert len(w.trips)==n  # Remote click rejected.
        player.personaje.tile_x,player.personaje.tile_y=tile
        player.personaje.hp=500
        hb.pulsar(player,eid)
        assert (player.personaje.tile_x,player.personaje.tile_y)==tuple(hb.datos()['tags'][str(tag)][0])
        assert player.personaje.hp==500


@pytest.mark.parametrize('side',[0,1])
def test_either_guard_opens_only_door_keeps_arch_and_materials_repair_pair(battle,monkeypatch,side):
    w,a,b=battle
    r=c.ronda(112)
    guards=[d for d in hb.datos()['structures'] if d['team']==2 and d['kind']=='guard' and d['number']==1]
    wall=next(d for d in hb.datos()['walls'] if d['team']==2 and d['number']==1)
    hb.sincronizar_puertas(a,r)
    a.packets.clear()
    monkeypatch.setattr(combate,'ATACANTE',[a])
    hb.monstruos(r)[guards[side]['entity']].recibir(10**9,var_pct=0)
    r=c.ronda(112)
    assert not hb.gate_alive(r,2,1)
    replacements=[p for p in a.packets if p[:2]==b'\x0e\0' and struct.unpack_from('<I',p,2)[0]==wall['entity']]
    assert replacements and struct.unpack_from('<I',replacements[-1],36)[0]==wall['sprite']
    before=b.cantidades[21]
    assert hb.construir(b,'guard',1)==hb.GATE_COST[0]
    assert b.cantidades[21]==before-hb.GATE_COST[0] and hb.gate_alive(c.ronda(112),2,1)
    assert struct.unpack_from('<I',a._holy_puertas[wall['entity']],36)[0]==wall['sprite']-1


def test_guard_click_never_warps(battle):
    w,a,b=battle
    d=next(d for d in hb.datos()['structures'] if d['kind']=='guard' and d['team']==1 and d['number']==1)
    before=len(w.trips)
    assert hb.pulsar(a,d['entity']) and len(w.trips)==before
    b.personaje.tile_x,b.personaje.tile_y=d['tile']
    assert hb.pulsar(b,d['entity']) and len(w.trips)==before
    a.personaje.tile_x,a.personaje.tile_y=d['tile']
    assert hb.pulsar(a,d['entity'])
    assert (a.personaje.tile_x,a.personaje.tile_y)==tuple(d['tile'])


def test_base_light_boundary_blocks_enemy_and_carrier_not_unladen_ally(battle):
    w,a,b=battle
    tile=next(tile for tile,team in hb.limites_base() if team==1)
    start,end=(tile[0]-1,tile[1]),(tile[0]+1,tile[1])
    assert hb.bloquear_paso(b,start,end)
    assert not hb.bloquear_paso(a,start,end)
    c.ronda(112)['portadores']['2']=a.personaje.char_id
    assert hb.bloquear_paso(a,start,end)


def test_late_viewer_gets_summon_color_after_not_before_spawn(battle):
    w,a,b=battle
    a.invocacion=dict(entity_id=900,npc_type=3902,nombre='Guard',hp=10,hp_max=10,
                      tile_x=220,tile_y=210,sprite=42572)
    packets=presencia.paquetes_invocaciones(a)
    mark=hb.equipo(900,1,True)
    spawn=next(i for i,p in enumerate(packets) if p[:2]==b'\x08\0')
    assert packets.index(mark)>spawn


def test_magic_flag_snapshot_keeps_unrelated_bits(world):
    from session import Session
    s=Session(('test',1));s.personaje=world.player().personaje
    s.enviar(struct.pack('<HIII',0x185,s.personaje.entity_id,0x800,0x200))
    s.enviar(hb.estado_portador(s,s.personaje.entity_id))
    assert s.flags_magicos==(0x04000800,0x200)
    s.enviar(hb.estado_portador(s,s.personaje.entity_id,quitar=True))
    assert s.flags_magicos==(0x800,0x200)


def test_crystal_native_visual_default_speed_observers_and_drop_restore(battle,monkeypatch):
    w,a,b=battle
    monkeypatch.setattr(inventario,'velocidad_de_montura',lambda item:150)
    a.inventario[10]=1
    fast=app._velocidad_de(a)
    assert fast>app.VELOCIDAD_JUGADOR
    a.flags_magicos=(0x80,0x10)
    a.personaje.tile_x,a.personaje.tile_y=c.CRISTALES[2][1]
    c.pulsar(a,c.CRISTALES[2][0])
    assert app._velocidad_de(a)==app.VELOCIDAD_JUGADOR
    own=[p for p in a.packets if p[:2]==b'\x85\x01'][-1]
    assert struct.unpack('<HIII',own)==(0x185,a.personaje.entity_id,0x04000080,0x10)
    assert hb.estado_portador(a,presencia.entidad_de(a)) in presencia._vestir(a)
    a.packets.clear();hb.sincronizar_portador(a)
    assert any(p[:2]==b'\x85\x01' for p in a.packets)  # Reapply on same-map load too.
    c.abandonar(a,112)
    assert app._velocidad_de(a)==fast
    own=[p for p in a.packets if p[:2]==b'\x85\x01'][-1]
    assert struct.unpack('<HIII',own)[2:]==(0x80,0x10)


def test_expiry_clears_visual_even_if_generic_buff_loop_already_removed_icon(battle):
    w,a,b=battle
    a.personaje.tile_x,a.personaje.tile_y=c.CRISTALES[2][1]
    c.pulsar(a,c.CRISTALES[2][0])
    a.flags_magicos=(0x04000080,0x10)
    a.personaje.buffs.pop(3141)
    w.now[0]+=301
    hb.tick_cristales()
    assert not c.ronda(112)['portadores']
    assert struct.unpack('<HIII',[p for p in a.packets if p[:2]==b'\x85\x01'][-1])[2:]==(0x80,0x10)
