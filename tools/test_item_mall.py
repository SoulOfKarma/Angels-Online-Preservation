"""Native mall packets; temporary accounts, no paid currency or live stock."""
import copy
import struct
import sqlite3

import pytest
from test_competiciones import world,stored
import app
import item_mall as mall


def dispatch(s,op,body=b''):
    app.Servidor.__new__(app.Servidor).manejar(s,op,None,None,'test',body)


def test_catalog_is_original_mall_not_npc_shop():
    assert len(mall.datos()['rows'])>400 and mall.datos()['historical_rows']==475
    assert mall.datos()['historical'] and mall.datos()['purchases_enabled']
    assert mall.datos()['source'].endswith('mall.xml')
    assert {r['category'] for r in mall.datos()['rows']} >= {11,13,16,19,24,25,28,32,35}


def test_catalog_has_no_event_stock_boost_stones_or_placeholder_weapon_boxes():
    rows=mall.datos()['rows'];ids={r['item'] for r in rows}
    assert not ids.intersection({81425,81426,82599,82000,82001,82002,82003,*range(9407,9417),14487,14488})
    assert {r['category'] for r in rows if r['item']==81972}=={23}
    # Same actual class bags are available in each appropriate subcategory;
    # their contained reward equipment is not automatically offered for sale.
    for i in range(80489,80496):
        assert {r['category'] for r in rows if r['item']==i}>={28,29,30}
    assert all(r.get('price_source') for r in rows if r['id']>=10000)


def test_catalog_wire_matches_native_count_and_57_byte_records():
    packet=mall.catalogo(now=2_000_000_000)
    count=struct.unpack_from('<I',packet,2)[0]
    assert packet[:2]==b'\x5f\0' and count>400
    assert len(packet)==6+57*count
    for i,r in enumerate(mall.disponibles(2_000_000_000)):
        data=struct.unpack_from('<9I11siIH',packet,6+57*i)
        assert data[:2]==(r['id'],r['item'])
        assert data[4:7]==(r['category'],r['quantity'],r['price'])
        assert len(data[9])==11 and data[9][-1]==0


def test_recent_fashion_and_bubble_sell_verified_root_bags_not_their_rewards():
    rows=mall.datos()['rows']
    assert len({r['id'] for r in rows})==len(rows)
    for item in (82270,82408,82660):
        assert {r['category'] for r in rows if r['item']==item}>={23,24,25,28}
        assert all(r.get('original_sale',{}).get('source','').startswith('https://ao.igg.com/')
                   for r in rows if r['item']==item)
    assert {r['item'] for r in rows if r['category']==40}=={82270}
    assert not {r['item'] for r in rows}&{82272,82411,82412,82413,82664,82665,82661}


def test_top_sale_uses_local_purchase_totals_across_categories_and_expires_history(world):
    s=world.player()
    by_item=lambda item,category:next(r['id'] for r in mall.disponibles()
                                    if r['item']==item and r['category']==category)
    mall.comprar(s,by_item(82408,24))
    mall.comprar(s,by_item(82270,28));mall.comprar(s,by_item(82270,40))
    top=[r for r in mall.disponibles() if r['category']==22]
    assert [r['item'] for r in top[:2]]==[82270,82408]
    assert [r['sort'] for r in top]==list(range(len(top)))
    future=[r for r in mall.disponibles(world.now[0]+31*86400) if r['category']==22]
    assert future[0]['item']==82660


def test_open_replies_with_catalog_not_fake_radar_currency(world):
    s=world.player();before=copy.deepcopy(stored(world,s))
    dispatch(s,0x012D)
    assert [p[:2] for p in s.packets]==[b'\x5f\0',b'\x61\0',b'\x62\0']
    assert s.packets[-1]==struct.pack('<HI',0x62,1000000)
    assert s.packets[-2]==struct.pack('<HB',0x61,0)
    assert stored(world,s)==before


@pytest.mark.parametrize('opcode',[0x012B,0x012C])
def test_invalid_buy_gift_requests_never_charge_or_create_items(world,opcode):
    s=world.player();before=copy.deepcopy(stored(world,s))
    dispatch(s,opcode,struct.pack('<IB',0xffffffff,0))
    assert stored(world,s)==before and not s.inventario
    assert mall.saldo(s.usuario)==1000000


@pytest.mark.parametrize('command',[20,21,22])
def test_cabinet_requests_do_not_fall_into_inventory_split(world,command):
    s=world.player(items={20:74136});before=copy.deepcopy(stored(world,s))
    dispatch(s,0x002F,struct.pack('<BII',command,20,1))
    assert stored(world,s)==before and s.inventario=={20:74136}


def test_expired_historical_promotions_are_not_listed(monkeypatch):
    expired=[dict(mall.datos()['rows'][0],end='1301010000')]
    monkeypatch.setattr(mall,'datos',lambda:{'rows':expired})
    active={r['id'] for r in mall.disponibles(2_000_000_000)}
    assert all(r['id'] not in active for r in expired)


def receipt(w,s):
    with sqlite3.connect(w.db) as con:
        return con.execute('SELECT id,item,cantidad FROM item_mall_cabinet WHERE usuario=? ORDER BY id',(s.usuario,)).fetchall()


def test_native_purchase_cabinet_claim_and_duplicate_claim(world):
    s=world.player()
    dispatch(s,0x012B,struct.pack('<IB',3011,0))
    assert mall.saldo(s.usuario)==1000000-29 and not s.inventario
    rows=receipt(world,s);assert len(rows)==1 and rows[0][1:]==(23821,1)
    dispatch(s,0x002F,struct.pack('<BII',22,rows[0][0],0xffffffff))
    assert 23821 in s.inventario.values() and receipt(world,s)==[]
    saved=copy.deepcopy(stored(world,s))
    dispatch(s,0x002F,struct.pack('<BII',22,rows[0][0],0xffffffff))
    assert stored(world,s)==saved and mall.saldo(s.usuario)==999971


def test_gift_is_charged_to_sender_and_claimed_only_by_receiver(world):
    a,b,c=world.player(),world.player(),world.player()
    body=struct.pack('<I17s',3011,b.personaje.nombre.encode())
    dispatch(a,0x012C,body)
    rows=receipt(world,b)
    assert len(rows)==1 and mall.saldo(a.usuario)==999971 and mall.saldo(b.usuario)==1000000
    with pytest.raises(mall.Rechazo):mall.retirar(c,rows[0][0])
    assert receipt(world,b)==rows
    mall.retirar(b,rows[0][0])
    assert 23821 in b.inventario.values() and not a.inventario and not c.inventario


def test_no_funds_or_missing_recipient_never_creates_delivery(world):
    s=world.player();mall.saldo(s.usuario)
    with sqlite3.connect(world.db) as con:con.execute('UPDATE item_mall_wallet SET ag=1')
    with pytest.raises(mall.Rechazo):mall.comprar(s,3011)
    assert mall.saldo(s.usuario)==1 and not receipt(world,s)
    with pytest.raises(mall.Rechazo):mall.comprar(s,3011,'MissingPlayer')
    assert mall.saldo(s.usuario)==1


def test_backfill_and_new_account_trigger_grant_once_not_on_login_or_new_character(world):
    s=world.player()
    with sqlite3.connect(world.db) as con:
        con.execute('CREATE TABLE IF NOT EXISTS cuentas(usuario TEXT PRIMARY KEY,password TEXT)')
        con.execute('INSERT INTO cuentas VALUES(?,?)',(s.usuario,''))
        assert mall.inicializar_cuentas(con)==1
        assert mall.inicializar_cuentas(con)==0
        con.execute("INSERT INTO cuentas VALUES('future','')")
    assert mall.saldo('future')==1000000
    assert mall.saldo(s.usuario.upper())==1000000
    mall.comprar(s,3011)
    with sqlite3.connect(world.db) as con:
        assert mall.inicializar_cuentas(con)==0
        assert con.execute("SELECT COUNT(*) FROM item_mall_movimientos WHERE motivo='initial'").fetchone()[0]==2
    assert mall.saldo(s.usuario)==999971
    other=world.player();other.usuario=s.usuario
    assert mall.saldo(other.usuario)==999971  # same account, different character


def test_full_bag_and_sql_failure_leave_entire_delivery_pending(world,monkeypatch):
    s=world.player(items={20:74136})
    ident,_=mall.comprar(s,3011)
    monkeypatch.setattr(app,'_tope_bolsa',lambda bag:20)
    before=copy.deepcopy(stored(world,s))
    with pytest.raises(mall.Rechazo):mall.retirar(s,ident)
    assert stored(world,s)==before and receipt(world,s)
    monkeypatch.setattr(app,'_tope_bolsa',lambda bag:40)
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_claim BEFORE DELETE ON item_mall_cabinet BEGIN SELECT RAISE(ABORT,'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError):mall.retirar(s,ident)
    assert stored(world,s)==before and s.inventario=={20:74136} and receipt(world,s)


def test_purchase_sql_failure_rolls_back_gold_and_delivery(world):
    s=world.player();mall.saldo(s.usuario)
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_purchase BEFORE INSERT ON item_mall_cabinet BEGIN SELECT RAISE(ABORT,'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError):mall.comprar(s,3011)
    assert mall.saldo(s.usuario)==1000000 and not receipt(world,s)


def test_cabinet_wire_is_native_33_byte_record(world):
    s=world.player();ident,_=mall.comprar(s,3011)
    packet=mall.almacen(s.usuario)
    assert len(packet)==36 and packet[:3]==b'\x61\0\x01'
    assert struct.unpack_from('<IIHI',packet,3)==(ident,23821,1,29)


def test_timed_delivery_preserves_deadline_through_save_move_and_expiry(world):
    import cuentas,inventario
    s=world.player()
    row=next(r for r in mall.disponibles() if r['duration'] and not r['flags']&(0x20|0x200))
    ident,_=mall.comprar(s,row['id']);mall.retirar(s,ident)
    slot=next(iter(s.inventario));meta=s.personaje.mejoras[slot].copy()
    assert meta['mall_item']==row['item'] and meta['mall_fin']==world.now[0]+row['duration']*60
    cuentas.guardar_inventario(s.usuario,s.personaje.char_id,s.inventario,s.cantidades,s.personaje.mejoras)
    assert stored(world,s)['mejoras'][str(slot)]==meta
    pkt=inventario.actualizar_ranuras(s.personaje.char_id,[(slot,row['item'],s.cantidades[slot],None)],mejoras=s.personaje.mejoras)
    assert struct.unpack_from('<I',pkt,6+47)[0]==int(meta['mall_fin'])
    world.now[0]=meta['mall_fin']+1
    mall.caducados(s)
    assert not s.inventario and not s.personaje.mejoras
