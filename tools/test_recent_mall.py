"""Recent original bundles, level gates, atomic claims and NPC redemptions."""
import copy
import sqlite3
import struct

import pytest
from test_competiciones import world,stored
from test_competition_proxy_admission import click,answer,mid
import app
import recent_mall as rm
import item_mall as mall


def test_party_blessing_original_menu_applies_native_stats_rates_and_persistence(world):
    import configuracion,lyceum_services
    s=world.player();s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=174,91
    before=stored(world,s);click(s,71410006);answer(s,3)
    buff=s.personaje.buffs[14955]
    assert buff['fin']==world.now[0]+43200 and buff['persist_death']
    assert buff['hp_bonus']==10000 and buff['mp_bonus']==8000
    assert buff['atk']==buff['matk']==buff['def']==buff['mdef']==4000
    assert buff['recoleccion_pct']==buff['fabricacion_pct']==40
    assert configuracion.multiplicador_exp(s.personaje.buffs)==configuracion.multiplicador_exp()+1
    assert configuracion.multiplicador_skill_exp(s.personaje.buffs)==configuracion.multiplicador_skill_exp()+1
    assert configuracion.multiplicador_drop(s.personaje.buffs)==configuracion.multiplicador_drop()+0.4
    assert stored(world,s)['buffs']['14955']['fin']==buff['fin']
    assert stored(world,s)['custom_field']==before['custom_field']
    s.personaje.tile_x=200
    assert not lyceum_services.bendicion_party(s)


def test_compensation_angel_is_not_published_or_accessible():
    assert all(n['nombre']!='Compensation Angel' and n['entity_id']!=71410009 for n in rm.datos()['npcs'])
    assert '513497' not in rm.datos()['nodes']


def test_daily_clerk_blue_stall_card_exchange_then_native_use(world):
    import inventario
    s=world.player(items={20:22251});s.cantidades[20]=60;world.save(s)
    s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=161,93
    click(s,71410004);answer(s,1);answer(s,5)
    assert s._lyceum_exchange==347
    app.Servidor.__new__(app.Servidor).manejar(s,0x160,None,None,'test',struct.pack('<II',13723,1))
    assert not total(s,22251) and total(s,15715)==1
    slot=next(k for k,v in s.inventario.items() if v==15715)
    use(s,slot)
    assert s.inventario=={166:15718} and inventario.limite_ranuras_puesto(s.inventario)==35
    data=stored(world,s)
    assert data['inventario']=={'166':15718} and data['expiracion_puesto']==0
    assert data['custom_field']=='preserve me'


@pytest.mark.parametrize('voucher,card',[(491,511),(492,512),(493,513),(15715,15718),
                                      (15716,15719),(15717,15720),(79745,511),
                                      (79746,512),(79747,513),(2701,2725)])
def test_stall_service_cards_are_not_treated_as_random_boxes(world,voucher,card):
    import inventario
    s=world.player(items={20:voucher})
    activated,deadline=rm.activar_puesto(s,20)
    assert activated==card and s.inventario=={166:card}
    assert stored(world,s)['inventario']=={'166':card}
    duration=inventario.duracion_tarjeta_puesto(card)
    assert deadline==(world.now[0]+duration if duration else 0)


def test_stall_card_activation_sql_failure_consumes_nothing(world):
    s=world.player(items={20:15715});before=copy.deepcopy(stored(world,s))
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_card BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):rm.activar_puesto(s,20)
    assert stored(world,s)==before and s.inventario=={20:15715}
    assert not any(b'You used' in p for p in s.packets)


def use(s,slot):
    app.Servidor.__new__(app.Servidor).manejar(s,0x2e,None,None,'test',struct.pack('<I',slot))


def total(s,item):
    return sum(s.cantidades.get(k,1) for k,v in s.inventario.items() if v==item)


def test_newbie_box_grants_every_original_reward_and_preserves_data(world):
    s=world.player(items={20:81972,21:74136})
    use(s,20)
    assert 81972 not in s.inventario.values() and total(s,74136)==1
    assert {28866,71987,71988,81974,82004,81999,81973,52201}<=set(s.inventario.values())
    assert stored(world,s)['custom_field']=='preserve me'
    assert any(b'You received' in p for p in s.packets)


def test_full_bundle_failure_keeps_every_item_and_retry_succeeds(world,monkeypatch):
    s=world.player(items={20:81972})
    snapshot=copy.deepcopy(stored(world,s))
    monkeypatch.setattr(app,'_tope_bolsa',lambda bag:22)
    use(s,20)
    assert s.inventario=={20:81972} and stored(world,s)==snapshot
    monkeypatch.setattr(app,'_tope_bolsa',lambda bag:120)
    use(s,20)
    assert total(s,81974)==1 and total(s,71987)==1


def test_database_failure_rolls_back_whole_bundle_and_session(world):
    s=world.player(items={20:81972});before=copy.deepcopy(stored(world,s))
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_bundle BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):rm.usar(s,20)
    assert s.inventario=={20:81972} and stored(world,s)==before


def test_285_and_295_bags_have_level_gates_and_give_all_stones(world):
    s=world.player(level=280,items={20:81974})
    use(s,20)
    assert s.inventario=={20:81974}
    s.personaje.nivel=285;world.save(s);use(s,20)
    assert total(s,71989)==total(s,71990)==total(s,81975)==1
    slot=next(k for k,v in s.inventario.items() if v==81975)
    use(s,slot);assert total(s,81975)==1 and not total(s,81997)
    s.personaje.nivel=295;world.save(s);use(s,slot)
    assert total(s,81997)==total(s,81998)==total(s,81978)==1
    assert total(s,25832)==40


def test_newbie_timed_boosts_have_real_deadlines_and_upper_level_bound(world):
    s=world.player(level=301,items={20:81999})
    use(s,20)
    for item in (82000,82001,82002,82003):
        slot=next(k for k,v in s.inventario.items() if v==item)
        assert s.personaje.mejoras[slot]['mall_fin']==world.now[0]+60*86400
        assert s.personaje.mejoras[slot]['mall_item']==item
        before=copy.deepcopy(stored(world,s));use(s,slot)
        assert stored(world,s)==before and not s.personaje.buffs


def test_original_random_weights_are_not_uniform_or_entire_bundle(world,monkeypatch):
    s=world.player(items={20:82660})
    def choose(rows,*,weights,k):
        assert k==1 and len(rows)==18 and weights[:5]==[2,2,10,20,40]
        assert sum(weights)==10000
        return [rows[2]]
    monkeypatch.setattr(rm.random,'choices',choose)
    use(s,20)
    assert total(s,82665)==20 and len(s.inventario)==1 and not total(s,82661)


def test_original_fixed_bag_with_bag_in_its_name_is_not_random(world):
    s=world.player(items={20:82005});use(s,20)
    assert all(total(s,item)==2 for item in range(82006,82012))


def test_native_gear_menu_exposes_latest_280_exchange(world):
    s=world.player(items={20:82012});s.personaje.stage=41
    s.personaje.tile_x,s.personaje.tile_y=170,93
    click(s,406)
    assert mid(s)==505825
    answer(s,2)
    answer(s,0)
    assert s._lyceum_exchange==615 and struct.pack('<HI',0x151,615) in s.packets
    app.Servidor.__new__(app.Servidor).manejar(s,0x160,None,None,'test',struct.pack('<II',22100,1))
    assert not total(s,82012) and total(s,79396)==total(s,79413)==1
    assert rm.canjear(s,22100,1) and total(s,79396)==1


def test_latest_fashion_menu_and_exchange_require_nearby_npc(world):
    s=world.player(items={20:82664});s.personaje.stage=41
    s.personaje.tile_x,s.personaje.tile_y=158,91
    click(s,71410003);assert mid(s)==504816
    answer(s,0)
    assert s._lyceum_exchange==622 and struct.pack('<HI',0x151,622) in s.packets
    s.personaje.tile_x=200
    assert rm.canjear(s,22490,1) and total(s,82664)==1
    s.personaje.tile_x=158
    assert rm.canjear(s,22490,1) and total(s,82662)==1 and not total(s,82664)
    slot=next(k for k,v in s.inventario.items() if v==82662)
    use(s,slot)
    assert all(total(s,i)==1 for i in (82666,82667,82668,82669,82674,82675))


def test_latest_gear_full_backpack_never_consumes_voucher(world,monkeypatch):
    s=world.player(items={20:82012});s.personaje.stage=41
    s.personaje.tile_x,s.personaje.tile_y=170,93
    click(s,406);answer(s,2);answer(s,0)
    monkeypatch.setattr(app,'_tope_bolsa',lambda bag:20)
    before=copy.deepcopy(stored(world,s))
    assert rm.canjear(s,22098,1)
    assert stored(world,s)==before and s.inventario=={20:82012}


def test_atomic_reward_stacking_splits_at_999_without_metadata_loss(world):
    s=world.player(items={20:52201,21:8101});s.cantidades[21]=950;world.save(s)
    use(s,20)
    assert total(s,8101)==1150
    assert sorted(s.cantidades[k] for k,v in s.inventario.items() if v==8101)==[151,999]


def test_actual_newbie_boosts_are_reusable_apply_rates_and_expire(world,monkeypatch):
    import configuracion as cfg
    import lyceum_services as ly
    s=world.player(level=300,items={20:82000,21:82001,22:82002,23:82003})
    monkeypatch.setattr(app,'_stats_ses',lambda s:b'')
    monkeypatch.setattr(cfg,'es_fin_de_semana',lambda:False)
    for slot in range(20,24):use(s,slot)
    assert s.inventario=={20:82000,21:82001,22:82002,23:82003}
    assert cfg.multiplicador_exp(s.personaje.buffs)==cfg.TASA_EXP_BASE+4
    assert cfg.multiplicador_skill_exp(s.personaje.buffs)==cfg.TASA_SKILL_EXP_BASE+4
    assert ly.bono(s.personaje.buffs,'recoleccion_pct')==50
    assert ly.bono(s.personaje.buffs,'fabricacion_pct')==50
    assert all(v['persist_death'] for v in s.personaje.buffs.values())
    assert all(v['fin']==world.now[0]+1800 for v in s.personaje.buffs.values())


def test_newbie_mall_purchase_cabinet_claim_and_open_are_persisted(world):
    s=world.player()
    product=next(r for r in mall.disponibles() if r['item']==81972)
    assert product['price']==399 and product['quantity']==1
    ident,target=mall.comprar(s,product['id'])
    assert target==s.usuario and mall.saldo(s.usuario)==999601
    mall.retirar(s,ident)
    use(s,next(k for k,v in s.inventario.items() if v==81972))
    assert total(s,71987)==total(s,71988)==1
    assert set(map(int,stored(world,s)['inventario'].values()))==set(s.inventario.values())


def test_recent_catalog_has_final_official_items_with_local_price_provenance():
    rows={r['item']:r for r in mall.disponibles()}
    assert {81972,82270,82408,82660}<=rows.keys()
    assert all(rows[i]['price']==399 and rows[i]['price_source'].startswith('local')
               for i in (81972,82270,82408,82660))


def test_lyceum_has_astral_party_chatbubble_and_fashionable_npcs(world):
    spawns = rm.poblar(41)
    # NPCs must be spawned in stage 41
    names = {s['nombre']: s for s in rm.datos()['npcs']}
    for name in ('Astral Angel', 'Party Angel', 'Chat Bubble Exchange', 'Fashionable'):
        assert name in names
    s = world.player()
    s.personaje.stage = 41
    # Astral Angel dialogue and Star Key exchange
    s.personaje.tile_x, s.personaje.tile_y = 177, 100
    click(s, 71410005); assert mid(s) == 514506
    answer(s, 1); assert s._lyceum_exchange == 393
    # Chat Bubble Exchange dialogue and groups 559, 570
    s.personaje.tile_x, s.personaje.tile_y = 151, 87
    click(s, 71410007); assert mid(s) == 516360
    answer(s, 1); assert mid(s) == 516365
    answer(s, 0); assert s._lyceum_exchange == 559
    click(s, 71410007); answer(s, 1); answer(s, 1); assert s._lyceum_exchange == 570

