"""Native game cards, consent, hidden hands, legal turns and full matches."""
import copy
import sqlite3
import struct
import pytest
from test_competiciones import world,stored
import app
import minigames as games
import minigame_rules as rules


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(games,'_GAMES',{});monkeypatch.setattr(games,'_PENDING',{})


def send(srv,s,sub,raw=b''):
    srv.manejar(s,0x10,None,None,'test',struct.pack('<H',sub)+raw)
def use(srv,s):srv.manejar(s,0x2e,None,None,'test',struct.pack('<BI',20,0))
def setup(world,card=494):
    a=world.player(items={20:card});b=world.player();c=world.player()
    srv=app.Servidor.__new__(app.Servidor);srv.mundos=world.players
    return srv,a,b,c
def invite(srv,a,b,kind):
    send(srv,a,0,struct.pack('<H17s',kind,b.personaje.nombre.encode().ljust(17,b'\0')))
def begin(world,card,kind):
    srv,a,b,c=setup(world,card);use(srv,a);invite(srv,a,b,kind)
    send(srv,b,1,struct.pack('<IB',a.personaje.char_id,1))
    game=games._game(a)
    assert game is games._game(b) and games._game(c) is None
    send(srv,a,3,bytes(4));assert game.state=='lobby'
    send(srv,b,3,bytes(4))
    return srv,a,b,c,game


@pytest.mark.parametrize('card,kind',[(494,1),(496,2),(495,3),(497,4)])
def test_map_change_keeps_match_and_replays_only_own_private_state(world,card,kind):
    srv,a,b,c,g=begin(world,card,kind)
    before=copy.deepcopy((g.board,g.hands,g.turn,g.state))
    own=[packet for key,packet in g.transcript if key is None or key==games._key(a)]
    private_other=[packet for key,packet in g.transcript if key==games._key(b)]
    a.packets.clear();b.packets.clear();a.mapa_cargando=True
    send(srv,a,2)
    assert games._game(a) is g
    a.personaje.stage=41;a.mapa_cargando=False;games.loaded(a)
    assert a.packets[1:]==own and not b.packets
    assert all(packet not in a.packets for packet in private_other)
    assert (g.board,g.hands,g.turn,g.state)==before and games._access(a,kind)


@pytest.mark.parametrize('voucher',list(games._VOUCHERS))
def test_native_access_card_activation_reserved_slot_duration_and_reconnect(world,voucher):
    srv,a,b,c=setup(world,voucher);a.cantidades[20]=2;world.save(a)
    hidden,slot,kind,seconds=games.card(voucher)
    use(srv,a)
    assert a.inventario[slot]==hidden and a.cantidades[20]==1
    assert stored(world,a)['inventario'][str(slot)]==hidden
    assert games._access(a,kind)
    before=copy.deepcopy(stored(world,a));use(srv,a)
    assert stored(world,a)==before and a.cantidades[20]==1
    if seconds:
        assert a.personaje.mejoras[slot]['mini_game_fin']==world.now[0]+seconds
        world.now[0]+=seconds+1;assert not games._access(a,kind)


def test_native_invitation_requires_host_card_only_and_rejects_uninvited_accept(world):
    srv,a,b,c=setup(world)
    invite(srv,a,b,1);assert games._key(b) not in games._PENDING
    use(srv,a);invite(srv,a,b,1)
    assert b.packets[-1][:4]==b'\x1f\0\0\0' and len(b.packets[-1])==31
    send(srv,c,1,struct.pack('<IB',a.personaje.char_id,1));assert not games._GAMES
    send(srv,b,1,struct.pack('<IB',a.personaje.char_id,1))
    assert games._game(b) is not None and not b.inventario
    games.desconectar(b);assert not games._GAMES


def test_game_invitation_respects_block_and_timeout(world):
    srv,a,b,c=setup(world);use(srv,a)
    srv.manejar(b,0x106,None,None,'test',bytes(21)+a.personaje.nombre.encode().ljust(17,b'\0'))
    invite(srv,a,b,1);assert not games._PENDING
    srv.manejar(b,0x107,None,None,'test',bytes(21)+a.personaje.nombre.encode().ljust(17,b'\0'))
    invite(srv,a,b,1);world.now[0]+=61
    send(srv,b,1,struct.pack('<IB',a.personaje.char_id,1));assert not games._GAMES


def test_five_in_a_row_native_turns_and_win_without_changing_gold(world):
    srv,a,b,c,g=begin(world,494,1);before=(a.oro,b.oro)
    send(srv,c,20,struct.pack('<II',0,0));assert not g.board
    send(srv,b,20,struct.pack('<II',0,0));assert not g.board
    for x in range(5):
        send(srv,a,20,struct.pack('<II',x,0))
        if x<4:send(srv,b,20,struct.pack('<II',x,1))
    assert g.state=='finished' and (a.oro,b.oro)==before
    assert any(p[:4]==b'\x1f\0\x17\0' for p in a.packets)
    snapshot=copy.deepcopy(g.board);send(srv,b,20,struct.pack('<II',10,10));assert g.board==snapshot


def test_bingo_rejects_bad_board_repeated_numbers_and_finishes_natively(world):
    srv,a,b,c,g=begin(world,496,2)
    send(srv,a,30,struct.pack('<25I',*([1]*25)));assert not g.bingo
    board=list(range(1,26))
    send(srv,a,30,struct.pack('<25I',*board));send(srv,b,30,struct.pack('<25I',*board))
    assert g.state=='playing'
    for number in range(1,26):
        if g.state=='finished':break
        player=g.players[g.turn]
        send(srv,player,31,struct.pack('<II',number,number-1))
    assert g.state=='finished' and games._bingo_lines(g,0)>=5
    assert any(p[:4]==b'\x1f\0\x22\0' for p in b.packets)


def test_othello_server_validates_flips_and_a_complete_game(world):
    srv,a,b,c,g=begin(world,497,4)
    send(srv,a,32,struct.pack('<IIB',0,0,1));assert g.turn==0
    send(srv,a,32,struct.pack('<IIB',0,0,0));assert len(g.board)==4
    for _ in range(130):
        if g.state=='finished':break
        moves=rules.legal_moves(g.board,g.turn+1)
        x,y=moves[0] if moves else (0,0)
        send(srv,g.players[g.turn],32,struct.pack('<IIB',x,y,int(not moves)))
    assert g.state=='finished' and len(g.board)<=64
    assert any(p[:4]==b'\x1f\0\x26\0' for p in a.packets)


def test_big_two_cards_stay_private_moves_require_owned_cards_and_match_finishes(world):
    srv,a,b,c,g=begin(world,495,3)
    assert len(g.hands)==2 and not g.hands[0]&g.hands[1] and 41 in g.hands[g.turn]
    for player,hand in zip((a,b),g.hands):
        packet=next(p for p in player.packets if p[:4]==b'\x1f\0\x1a\0')
        assert set(struct.unpack_from('<13i',packet,8))==hand
    forged=next(iter(g.hands[1-g.turn]));before=copy.deepcopy(g.hands)
    send(srv,g.players[g.turn],25,struct.pack('<BI5i',0,0,forged,-1,-1,-1,-1));assert g.hands==before
    for turn in range(250):
        if g.state=='finished':break
        index=g.turn;hand=sorted(g.hands[index],key=rules.card_rank)
        options=[c for c in hand if rules.beats([c],g.previous)]
        if all(len(h)==13 for h in g.hands):options=[41]
        if options:send(srv,g.players[index],25,struct.pack('<BI5i',0,0,options[0],-1,-1,-1,-1))
        else:send(srv,g.players[index],26)
    assert g.state=='finished' and any(not h for h in g.hands)
    assert any(p[:4]==b'\x1f\0\x1c\0' for p in a.packets)


def test_card_database_failure_does_not_consume_or_enable_game(world):
    srv,a,b,c=setup(world)
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_games BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):use(srv,a)
    assert a.inventario=={20:494} and not games._access(a,1)


def test_big_two_native_bombs_and_straight_order():
    #4f6c90:3=straight,4=full house,5=quads,6=straight flush.7 is a UI cursor.
    low_straight=[0,14,28,42,4]  #A2345
    high_straight=[1,15,29,43,5]  #23456
    royal=[0,22,36,50,12]        #10JQKA
    straight_flush=[2,3,4,5,6]
    quads=[2,15,28,41,3]
    house=[2,15,28,3,16]
    flush=[2,4,6,8,10]
    assert rules.combination(flush) is None
    assert rules.combination(house)[0]==4 and rules.combination(quads)[0]==5
    assert rules.combination(straight_flush)[0]==6
    assert rules.beats(high_straight,royal) and rules.beats(royal,low_straight)
    assert rules.beats(quads,[1]) and rules.beats(straight_flush,quads)
    assert not rules.beats(house,low_straight)


def test_big_two_host_can_invite_four_players_and_deals_unique_full_deck(world):
    srv,a,b,c=setup(world,495);d=world.player();use(srv,a)
    for target in (b,c,d):
        invite(srv,a,target,3);send(srv,target,1,struct.pack('<IB',a.personaje.char_id,1))
    g=games._game(a);assert len(g.players)==4
    for s in (a,b,c,d):send(srv,s,3,bytes(4))
    assert g.state=='playing' and set.union(*g.hands)==set(range(52))
    assert sum(len(h) for h in g.hands)==52 and 41 in g.hands[g.turn]
