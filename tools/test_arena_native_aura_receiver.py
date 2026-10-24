"""Native006000B0 receiver-class regression, backed by live actor fields."""
import struct

import pytest
from test_competiciones import world
import app
import competiciones as c
import holy_battlefield as hb
import presencia


def native42(packet,local_id,remote_id):
    """The client's class gate, not merely an assertion of packet presence."""
    _,outer,count,kind,target,active=struct.unpack('<HIBBII',packet)
    assert count==1 and kind==42
    classes={local_id:0x1102,remote_id:0x80000102}
    if classes.get(outer)!=0x1102:return False
    return classes.get(target) in (0x1102,0x80000102) and bool(active)


@pytest.mark.parametrize('reverse',[False,True])
def test_native_remote_ring_requires_local_receiver_not_remote_actor(world,monkeypatch,reverse):
    monkeypatch.setattr(app,'_stats_ses',lambda s:b'')
    c.iniciar(240,30,0,434)
    a,b=world.player(level=434),world.player(level=434)
    for s in (a,b):c.entrada(s,240)
    viewer,other=(b,a) if reverse else (a,b)
    local_id=viewer.personaje.entity_id
    remote_id=presencia.entidad_de(other)
    old=next(p for p in c.marcas_actor(other,True) if len(p)==16 and p[7]==42)
    # Exact old output is ignored by the native class check.
    assert not native42(old,local_id,remote_id)
    viewer.packets.clear()
    presencia._mandar(viewer,*c.marcas_actor(other,True))
    packet=next(p for p in viewer.packets if len(p)==16 and p[7]==42)
    assert native42(packet,local_id,remote_id)
    assert struct.unpack_from('<I',packet,8)[0]==remote_id
    # The direct phase/re-entry snapshot has the same recipient contract.
    viewer.packets.clear()
    c.al_entrar(viewer)
    assert any(native42(p,local_id,remote_id) for p in viewer.packets
               if len(p)==16 and p[7]==42 and struct.unpack_from('<I',p,8)[0]==remote_id)


def test_recipient_conversion_preserves_holy_team_target_pet_and_clear(world):
    a,b=world.player(),world.player()
    remote_id=presencia.entidad_de(b)
    team=hb.equipo(remote_id,2)
    assert presencia.para_receptor(a,team)==team
    for target in (remote_id,90000001):
        for active in (0,1):
            old=struct.pack('<HIBBII',0x1d,remote_id,1,42,target,active)
            expected=struct.pack('<HIBBII',0x1d,a.personaje.entity_id,1,42,target,active)
            assert presencia.para_receptor(a,old)==expected
            assert presencia.para_receptor(b,old)!=expected


def test_spawn_refresh_hostility_marks_also_use_receivers_local_actor(world):
    c.iniciar(112,60,0)
    a,b=world.player(items={20:8537}),world.player(items={20:8537})
    for s in (a,b):c.entrada(s,112)
    a.packets.clear()
    # Every spawn/equipment/transform refresh passes _vestir through _mandar.
    presencia._mandar(a,*presencia._vestir(b))
    mark=next(p for p in a.packets if len(p)==16 and p[7]==42)
    assert struct.unpack_from('<I',mark,2)[0]==a.personaje.entity_id
    assert struct.unpack_from('<I',mark,8)[0]==presencia.entidad_de(b)
