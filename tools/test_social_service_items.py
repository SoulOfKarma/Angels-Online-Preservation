"""Native love input, atomic service cards, and team distribution modes."""
import copy
import sqlite3
import struct
from types import SimpleNamespace

import pytest
from test_competiciones import world,stored
import app,equipos,love_broadcasting as love


def confirm(s,name,slot=20):
    body=bytes([slot])+name.encode('ascii').ljust(17,b'\0')
    app.Servidor.__new__(app.Servidor).manejar(s,0x4d,None,None,'test',body)


@pytest.mark.parametrize('item',sorted(love.ITEMS))
def test_love_original_dialog_confirm_consumes_one_and_broadcasts_to_both(world,item):
    sender=world.player(items={20:item});target=world.player()
    sender.cantidades[20]=2;world.save(sender)
    confirm(sender,target.personaje.nombre.lower())
    assert sender.cantidades[20]==1 and stored(world,sender)['cantidades']['20']==1
    public=[p for p in sender.packets if p[:2]==b'\x28\x01']
    assert len(public)==1 and public[0] in target.packets
    assert target.personaje.nombre.encode() in public[0]
    confirm(sender,target.personaje.nombre)
    assert sender.cantidades[20]==1  # duplicate confirm is not another purchase


def test_love_invalid_target_and_missing_item_never_consume_or_broadcast(world):
    sender=world.player(items={20:4892});before=copy.deepcopy(stored(world,sender))
    confirm(sender,'Nobody')
    assert stored(world,sender)==before
    assert any(b'does not exist' in p for p in sender.packets)
    sender.packets.clear();confirm(sender,'Nobody',21)
    assert not sender.packets and sender.inventario=={20:4892}


def test_love_database_failure_keeps_item_and_does_not_announce(world):
    sender=world.player(items={20:4892});target=world.player()
    before=copy.deepcopy(stored(world,sender))
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_love BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):confirm(sender,target.personaje.nombre)
    assert stored(world,sender)==before and sender.inventario=={20:4892}
    assert not target.packets


@pytest.mark.parametrize('mode',[0,1])
def test_native_party_mode_reaches_reward_distribution_and_survives_promotion(world,monkeypatch,mode):
    equipos.olvidar_todo()
    a=world.player();b=world.player()
    srv=app.Servidor.__new__(app.Servidor);srv.mundos=[a,b]
    body=b.personaje.nombre.encode('ascii').ljust(17,b'\0')+bytes([mode])
    srv.manejar(a,0x17,None,None,'test',body)
    invitation=next(p for p in b.packets if p[:2]==b'\x23\0')
    assert invitation[23]==mode
    assert equipos.aceptar(b) and equipos.modo_de(a)==mode
    assert equipos.lista_del_grupo(a.personaje.char_id)[6]==mode
    monkeypatch.setattr(app,'_companeros',lambda s:[b] if s is a else [a])
    monkeypatch.setattr(app,'_grupo_en_sala',lambda s:[a,b])
    mob=SimpleNamespace(dano_por={a.personaje.char_id:90,b.personaje.char_id:10})
    rewards=app._repartir_muerte(a,mob)
    fractions={s.personaje.char_id:f for s,f,_ in rewards}
    assert fractions==({a.personaje.char_id:.5,b.personaje.char_id:.5} if mode==0
                       else {a.personaje.char_id:.9,b.personaje.char_id:.1})
    assert equipos.ascender(a,b.personaje.char_id) and equipos.modo_de(a)==mode
    assert equipos.lista_del_grupo(b.personaje.char_id)[6]==mode
    assert equipos.accion(a,255)=='nada' and len(equipos.grupo_de(a))==2
    equipos.salir(b);assert not equipos.grupo_de(a)
    equipos.olvidar_todo()


def test_pending_party_invites_cannot_overfill_group(world):
    equipos.olvidar_todo()
    players=[world.player() for _ in range(6)]
    lookup=lambda name:next((s for s in players if s.personaje.nombre==name),None)
    for s in players[1:]:assert equipos.invitar(players[0],s.personaje.nombre,lookup)[0]
    for s in players[1:5]:assert equipos.aceptar(s)
    assert not equipos.aceptar(players[5]) and len(equipos.grupo_de(players[0]))==5
    equipos.olvidar_todo()


def test_rejected_share_invitation_can_be_retried_as_alone(world):
    equipos.olvidar_todo()
    a=world.player();b=world.player()
    srv=app.Servidor.__new__(app.Servidor);srv.mundos=world.players
    name=b.personaje.nombre.encode().ljust(17,b'\0')
    srv.manejar(a,0x17,None,None,'test',name+b'\0')
    assert equipos.rechazar(b)
    b.packets.clear();srv.manejar(a,0x17,None,None,'test',name+b'\1')
    assert next(p for p in b.packets if p[:2]==b'\x23\0')[23]==1
    assert equipos.aceptar(b) and equipos.modo_de(a)==1
    equipos.olvidar_todo()


def friend_request(srv,s,target):
    srv.manejar(s,0x19,None,None,'test',target.personaje.nombre.encode().ljust(17,b'\0')+bytes(4))


def test_friend_lists_restored_on_each_map_loaded_and_keep_sql_contacts(world):
    import amigos,social_state
    amigos._PENDIENTES.clear()
    a=world.player();b=world.player()
    srv=app.Servidor.__new__(app.Servidor);srv.mundos=world.players
    friend_request(srv,a,b);srv.manejar(b,0x1b,None,None,'test',bytes(4))
    for stage in [41,29,88]:
        a.personaje.stage=stage;a.packets.clear();social_state.loaded(a,world.players)
        packet=next(p for p in a.packets if p[:2]==b'\x27\0')
        assert struct.unpack_from('<I',packet,6)[0]==1
        assert b.personaje.nombre.encode() in packet
        assert any(p[:2]==b'\x28\0' for p in a.packets)


def test_friend_native_invitation_accept_persist_and_reconnect(world):
    import amigos
    amigos._PENDIENTES.clear()
    a=world.player();b=world.player();stranger=world.player()
    srv=app.Servidor.__new__(app.Servidor);srv.mundos=world.players
    friend_request(srv,a,b)
    invitation=next(p for p in b.packets if p[:2]==b'\x29\0')
    assert len(invitation)==25 and invitation[8:25].rstrip(b'\0')==a.personaje.nombre.encode()
    srv.manejar(stranger,0x1b,None,None,'test',bytes(4))
    assert not stranger.packets
    srv.manejar(b,0x1b,None,None,'test',bytes(4))
    assert any(p[:2]==b'\x2a\0' and len(p)==86 for p in a.packets)
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT COUNT(*) FROM social_friends').fetchone()[0]==2
    srv.manejar(b,0x1b,None,None,'test',bytes(4))
    a.packets.clear();b.desconectado=True
    amigos.sincronizar(a,world.players)
    packet=next(p for p in a.packets if p[:2]==b'\x27\0')
    assert len(packet)==52 and struct.unpack_from('<I',packet,6)[0]==1
    assert struct.unpack_from('<I',packet,10)[0]==b.personaje.char_id
    assert struct.pack('<HII',0x2e,a.personaje.char_id,b.personaje.char_id) in a.packets
    assert not any(p[:2]==b'\x28\0' for p in a.packets)
    assert a.inventario==stranger.inventario=={}


def test_friend_decline_timeout_and_disconnect_cannot_be_accepted(world):
    import amigos
    amigos._PENDIENTES.clear()
    a=world.player();b=world.player()
    srv=app.Servidor.__new__(app.Servidor);srv.mundos=world.players
    friend_request(srv,a,b);srv.manejar(b,0x1c,None,None,'test',b'')
    assert not amigos._PENDIENTES
    friend_request(srv,a,b);world.now[0]+=61
    srv.manejar(b,0x1b,None,None,'test',bytes(4))
    friend_request(srv,a,b);amigos.sincronizar(a,world.players,offline=True)
    srv.manejar(b,0x1b,None,None,'test',bytes(4))
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT COUNT(*) FROM social_friends').fetchone()[0]==0


def test_friend_accept_transaction_failure_does_not_add_half_of_friendship(world):
    import amigos
    amigos._PENDIENTES.clear()
    a=world.player();b=world.player()
    srv=app.Servidor.__new__(app.Servidor);srv.mundos=world.players
    friend_request(srv,a,b)
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_friend BEFORE INSERT ON social_friends WHEN NEW.owner='u2' BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):srv.manejar(b,0x1b,None,None,'test',bytes(4))
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT COUNT(*) FROM social_friends').fetchone()[0]==0
        con.execute('DROP TRIGGER fail_friend')
    srv.manejar(b,0x1b,None,None,'test',bytes(4))
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT COUNT(*) FROM social_friends').fetchone()[0]==2
