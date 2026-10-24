"""Battle chat is restricted to active Holy competitors on the same team."""
import pytest
from test_competiciones import world
import app
import competiciones as c


@pytest.mark.parametrize('opcode,body',[(0x133,b'hello\0'),(1,b'hbteam hello\0')])
def test_battle_chat_no_round_registration_active_outside_spectator_and_ended(world,opcode,body):
    server=app.Servidor.__new__(app.Servidor)
    players=[world.player(items={20:8537}) for _ in range(4)]
    a,enemy,ally,observer=players
    server.mundos=players
    def send(who):
        for s in players:s.packets.clear()
        server.manejar(who,opcode,None,None,'test',body)
        return [s for s in players if any(p[:2]==b'\x39\x01' for p in s.packets)]
    assert not send(a)
    c.iniciar(112,60,5)
    for s in (a,enemy,ally):c.entrada(s,112)
    c.entrada(observer,112,True)
    assert not send(a)  # Registration is not active combat.
    r=c.ronda(112)
    world.now[0]=r['inicio']+1
    assert send(a)==[a,ally]
    assert not send(observer)
    a.personaje.stage=114
    assert not send(a)  # Membership cannot authorize chat from the lobby.
    a.personaje.stage=112
    world.now[0]=r['fin']+1
    assert not send(a)
