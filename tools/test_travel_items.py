"""Real C2S item route, native scroll destinations and atomic mark/book use."""
import copy,sqlite3,struct
import pytest
from test_competiciones import world,stored
import app,eventos,travel_items as travel


def use(s,slot,target=None):
    body=struct.pack('<I',slot) if target is None else struct.pack('<II',slot,target)
    app.Servidor.__new__(app.Servidor).manejar(s,0x2e,None,None,'test',body)


def place(s):
    s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=177,100


@pytest.mark.parametrize('ident,stage',[(16993,153),(20564,170),(23818,194)])
def test_city_scrolls_use_native_magic16_revival_tag_and_consume_one(world,ident,stage):
    s=world.player(items={20:ident});s.cantidades[20]=2;world.save(s)
    use(s,20)
    assert s.personaje.stage==stage and world.trips[-1][1:]==(stage,*eventos.casillas_de_tag(stage,61)[0])
    assert s.cantidades[20]==1 and stored(world,s)['stage_id']==stage
    assert stored(world,s)['custom_field']=='preserve me'


def test_mark_stone_persists_character_point_and_portal_returns_without_reload(world):
    s=world.player(items={20:3693,21:3694});place(s);use(s,20)
    assert 20 not in s.inventario and stored(world,s)['travel_mark']==dict(stage=41,x=177,y=100)
    s.personaje.tile_x,s.personaje.tile_y=175,99;s.packets.clear();use(s,21)
    assert (s.personaje.stage,s.personaje.tile_x,s.personaje.tile_y)==(41,177,100)
    assert not s.inventario and any(p[:2]==b'\x03\0' for p in s.packets)
    assert not any(p[:2]==b'\x0c\0' for p in s.packets)


def test_two_maple_marks_have_independent_immutable_points_and_spend_scroll_only(world):
    s=world.player(items={20:20565,21:20565,22:20566});s.cantidades[22]=2;world.save(s)
    place(s);use(s,20);s.personaje.tile_x=175;use(s,21)
    assert s.personaje.mejoras[20]['maple_mark']['x']==177
    assert s.personaje.mejoras[21]['maple_mark']['x']==175
    s.personaje.tile_x=174;use(s,20)
    assert s.personaje.tile_x==177 and s.cantidades[22]==1
    use(s,21);assert s.personaje.tile_x==175 and 22 not in s.inventario
    assert s.inventario=={20:20565,21:20565}
    before=copy.deepcopy(stored(world,s));use(s,20)
    assert stored(world,s)==before and s.personaje.tile_x==175
    assert stored(world,s)['mejoras']['20']['maple_mark']['x']==177


def test_unmarked_scroll_and_restricted_record_spend_nothing(world):
    s=world.player(items={20:3694,21:3693,22:20566});before=copy.deepcopy(stored(world,s))
    use(s,20);use(s,22)
    assert stored(world,s)==before
    s.personaje.stage=112;use(s,21)
    assert stored(world,s)==before and not s.personaje.travel_mark


def test_sql_failure_does_not_spend_scroll_or_move_session(world):
    s=world.player(items={20:23818});before=copy.deepcopy(stored(world,s))
    with sqlite3.connect(world.db) as con:con.execute("CREATE TRIGGER fail_tp BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):use(s,20)
    assert stored(world,s)==before and not world.trips and s.inventario=={20:23818}


@pytest.mark.parametrize('ident,summon',[(2987,False),(1333,True)])
def test_party_books_move_only_selected_teammate_and_commit_with_payment(world,monkeypatch,ident,summon):
    import equipos
    a=world.player(items={20:ident});b=world.player();place(a);place(b)
    b.personaje.stage=153;b.personaje.tile_x,b.personaje.tile_y=eventos.casillas_de_tag(153,61)[0]
    monkeypatch.setattr(equipos,'grupo_de',lambda s:[a,b])
    use(a,20,b.personaje.char_id)
    assert not a.inventario
    if summon:
        assert b.personaje.stage==41 and stored(world,b)['stage_id']==41 and a.personaje.stage==41
    else:assert a.personaje.stage==153 and b.personaje.stage==153


def test_party_book_rejects_event_target_without_spending(world,monkeypatch):
    import equipos
    a=world.player(items={20:2987});b=world.player();place(a);b.personaje.stage=112
    monkeypatch.setattr(equipos,'grupo_de',lambda s:[a,b])
    before=copy.deepcopy(stored(world,a));use(a,20,b.personaje.char_id)
    assert stored(world,a)==before and not world.trips
