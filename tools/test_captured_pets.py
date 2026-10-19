"""Regression checks for the captured-monster pet bridge."""
import pathlib
import struct
import sys


ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'server'))

import combate
import cuentas
import house_services as hs
import mascotas
import presencia


def test_only_official_catch_xml_decides_the_archetype():
    caught = hs.capturable_monsters()
    # These crabs intentionally belong to different official skill archetypes.
    assert caught[32] == 16970
    assert caught[36] == 16972
    assert caught[49] == 16969
    assert caught[52] == 16976
    # House-hatching eggs must not silently make unrelated monsters catchable.
    assert 1217 not in caught


def test_luxurious_poke_egg_is_not_guaranteed():
    # NPC 7001 has base probability 500/10000. Even the 300% egg can fail.
    luxury = hs.capture_chance(300, 1, 100, npc_type=7001)
    assert 1.0 < luxury < 100.0
    assert luxury > hs.capture_chance(60, 1, 100, npc_type=7001)
    assert hs.capture_chance(300, 1, 100, npc_type=7001) > hs.capture_chance(
        300, 99, 100, npc_type=7001)


def test_successful_capture_uses_absorption_after_icy_trap():
    packets = combate.efecto_captura(11, 22, 33, 44, 16982)
    assert len(packets) == 2
    assert int.from_bytes(packets[0][:2], 'little') == 0x0011
    assert int.from_bytes(packets[1][:2], 'little') == 0x0011
    effect_start = packets[0][2] | ((packets[0][3] & 0x0F) << 8)
    effect_end = packets[1][2] | ((packets[1][3] & 0x0F) << 8)
    assert effect_start == 302  # absorption toward the player, success only
    assert effect_end == 302
    assert packets[0][3] & 0x80 == 0x00  # phase 0x00
    assert packets[1][3] & 0x80 == 0x80  # phase 0x80
    assert struct.unpack_from('<II', packets[0], 12) == (33, 44)
    assert struct.unpack_from('<II', packets[1], 12) == (33, 44)
    assert packets[0][22] == 1  # SP_CLASS_MAGIC, as registered in m02.obd
    assert struct.unpack_from('<H', packets[0], 23)[0] == 0  # no attack skill id


def test_failed_attempt_uses_complete_icy_trap_resource_36():
    packets = combate.efecto_cristal_captura(11, 22, 33, 44)
    assert len(packets) == 2
    assert [p[2] | ((p[3] & 0x0F) << 8) for p in packets] == [36, 36]
    assert packets[0][3] & 0x80 == 0x00
    assert packets[1][3] & 0x80 == 0x80
    assert all(struct.unpack_from('<II', p, 12) == (33, 44) for p in packets)


def test_pet_dawn_shield_uses_official_magic_packet_type():
    dawn = combate.datos_magia(2327)
    assert dawn['nombre'] == 'Dawn Shield VIII'
    assert dawn['efecto'] == 23
    assert dawn['es_magia_visual'] is True
    start = combate.efecto_magia_self_inicio(
        6001, dawn['efecto'], 2327, cast_time=dawn['cast_time'], es_magia=True)
    end = combate.efecto_magia_self_fin(
        6001, dawn['efecto'], 2327, es_magia=True)
    assert start[2] == 23 and end[2] == 23
    assert start[22] == 1 and end[22] == 1
    assert struct.unpack_from('<H', start, 23)[0] == 2327
    assert struct.unpack_from('<H', start, 20)[0] == 1000

    tendon = combate.datos_magia(4143)
    assert tendon['nombre'] == 'Tendon Chop VIII'
    assert tendon['es_magia_visual'] is False


def test_pet_and_summon_actions_are_visible_to_other_players():
    class DummySession:
        def __init__(self, eid):
            self.personaje = type('P', (), {'stage': 308, 'entity_id': eid})()
            self._mapa_presencia = 308
            self.writer = object()
            self.sent = []

        def enviar(self, *packets):
            self.sent.extend(packets)

    owner = DummySession(1001)
    observer = DummySession(1002)
    old = list(presencia._POR_MAPA.get(308, []))
    try:
        presencia._POR_MAPA[308] = [owner, observer]
        packets = (combate.ataque(6001, 7001, 832),
                   combate.numero_de_dano(6001, 7001, 50,
                                           ataque=4143, efecto=148))
        presencia.notificar_companero_accion(owner, *packets)
        assert observer.sent == list(packets)
        assert owner.sent == []
    finally:
        presencia._POR_MAPA[308] = old


def test_quality_names_match_the_client_strings():
    assert mascotas.RANGO_NOMBRES == {
        1: 'Common', 2: 'Good', 3: 'Rare', 4: 'Awesome', 5: 'Super'}


def test_quality_does_not_rewrite_stars_or_stats():
    pet = {'sprite': 3403, 'estrellas': 3, 'atk': 100,
           'bonos': {'atk': 8}}
    mascotas.aplicar_rango(pet, rango=5, st=20, mult=1.5)
    assert pet['rango_nombre'] == 'Super'
    assert pet['estrellas'] == 3
    assert pet['atk'] == 100
    assert pet['bonos'] == {'atk': 8}


def test_captured_species_appears_at_advanced_evolution():
    pet = mascotas.recien_nacida('Sky Bird', 3403, npc_type=7014)
    pet['captured_name'] = 'Sky Bird'
    pet['captured_tipo'] = 43210
    old_stars = mascotas.calcular_estrellas_total(pet['bonos'])
    mascotas.evolucionar(pet, 'nice')
    assert pet['sprite'] == 3404       # official skill/stat archetype advanced
    assert pet['nombre'] == 'Sky Bird' # preserves default captured monster name!
    assert pet['tipo'] != 43210
    assert pet['skills'] == list(mascotas.skills_de(3404, pet['nivel']))

    # If the user renamed the pet, the custom name is preserved forever
    pet['renombrada'] = True
    pet['nombre'] = 'Falcon'
    mascotas.evolucionar(pet, 'nice')
    assert pet['nombre'] == 'Falcon'

    mascotas.evolucionar(pet, 'nice')
    assert pet['sprite'] == 3406
    assert pet['nombre'] == 'Falcon'
    assert pet['tipo'] == 43210          # advanced form is captured species
    assert pet['estrellas'] >= old_stars


def test_paquete_renombrar_format_matches_angel_exe():
    pkt = mascotas.paquete_renombrar(5001, 'Rocky', 0)
    assert len(pkt) == 72 + len(b'Rocky\x00')
    assert struct.unpack_from('<H', pkt, 0)[0] == 0x003D
    assert struct.unpack_from('<H', pkt, 2)[0] == len(pkt)
    assert struct.unpack_from('<H', pkt, 6)[0] == 0  # result success
    assert struct.unpack_from('<I', pkt, 8)[0] == 5001 # entity ID
    assert struct.unpack_from('<H', pkt, 70)[0] == 0 # name offset
    assert pkt[72:78] == b'Rocky\x00'


def test_capture_visual_is_targeted_and_has_no_fake_attack_packet():
    pkts = combate.efecto_captura(1, 2, 61, 72)
    assert len(pkts) == 2
    assert struct.unpack_from('<H', pkts[0])[0] == 0x0011
    assert struct.unpack_from('<H', pkts[1])[0] == 0x0011
    assert struct.unpack_from('<II', pkts[0], 4) == (1, 2)
    assert struct.unpack_from('<II', pkts[0], 12) == (61, 72)
    assert not any(p[:2] == b'\x0A\x00' for p in pkts)


def test_old_captured_pet_is_repaired_when_loaded():
    legacy = {
        'nombre': 'Blue Crab', 'sprite': 3406, 'tipo': 42816,
        'nivel': 55, 'npc_type': 7014, 'rango': 4,
        'rango_nombre': 'Top', 'estrellas': 18,
        'bonos': {'hp': 43, 'mp': 29, 'dfs': 40, 'mdef': 25,
                  'rigor': 18, 'agilidad': 12},
    }
    repaired = cuentas._cargar_mascota(legacy)
    identity = hs.captured_monster_identity(7014)
    assert repaired['rango_nombre'] == 'Awesome'
    assert repaired['estrellas'] == mascotas.calcular_estrellas_total(legacy['bonos'])
    assert repaired['nombre'] == mascotas.abreviar_nombre_pet(identity['nombre'])
    assert repaired['tipo'] == identity['sprite']


def test_abbreviate_names_mutated_chimera():
    assert mascotas.abreviar_nombre_pet('Mutated Chimera') == 'Chimera'
    assert mascotas.abreviar_nombre_pet('Mutated Pink Fruit') == 'Pink Fruit'
    assert mascotas.abreviar_nombre_pet('Mutated Hornet') == 'Mut. Hornet'


def test_inventory_move_active_pet_preserves_instance_and_sends_0x0065():
    from unittest import mock
    import app
    import inventario as inv

    class DummyPersonaje:
        def __init__(self):
            self.char_id = 9999
            self.entity_id = 2001
            self.nombre = 'Tester'
            self.nivel = 50
            self.clase = 1
            self.tile_x = 100
            self.tile_y = 100
            self.mejoras = {}
            self.hp = 1000
            self.hp_max = 1000
            self.mp = 1000
            self.mp_max = 1000
            self.habilidades = []
            self.skills_equipadas = []
            self.str = 100
            self.con = 100
            self.int = 100
            self.dex = 100
            self.agi = 100
            self.puntos_status = 0
            self.puntos_skill = 0
            self.exp = 0
            self.exp_max = 100000
            self.mascotas = {}
            self.mascota = None

    class DummySesion:
        def __init__(self):
            self.rol = 'mundo'
            self.usuario = 'tester'
            self.inventario = {15: 16970}  # pet egg in slot 15
            self.cantidades = {15: 1}
            self.instancias = {15: b'\x12\x34\x56\x78\x00\x00\x00\x00'}
            self.personaje = DummyPersonaje()
            self.pet_entity_id = 6001
            self.paquetes = []

        def enviar(self, *pkts):
            self.paquetes.extend(pkts)

    ses = DummySesion()
    pet_ficha = {
        'nombre': 'Chimera',
        'sprite': 3403,
        'tipo': 42816,
        'ranura': 15,
        'instancia': 7777,
        'fuera': True,
        'entidad': 6001,
        'nivel': 72,
        'hp': 500,
        'hp_max': 500,
        'mp': 300,
        'mp_max': 300,
        'saciedad': 100,
        'intimidad': 80,
    }
    ses.personaje.mascotas['15'] = pet_ficha
    ses.personaje.mascota = pet_ficha

    srv = app.Servidor('127.0.0.1', 8888, 8889, 8890)
    # Move item from slot 15 to slot 24 (c2s 0x0012: [u16 org=15][u16 dst=24])
    payload = struct.pack('<HH', 15, 24)
    with mock.patch.object(app, '_guardar_bolsa'):
        srv.manejar(ses, 0x0012, None, None, 'test', payload)

    # 1. Item moved in inventory
    assert 15 not in ses.inventario
    assert ses.inventario[24] == 16970

    # 2. Pet updated in ses.personaje.mascotas and pet_ficha
    assert '24' in ses.personaje.mascotas
    assert pet_ficha['ranura'] == 24

    # 3. CRITICAL: instancia must NOT be overwritten to 1000 + 24!
    # It must retain its active instance (7777) so Angel.exe's 0x5df8 matches!
    assert pet_ficha['instancia'] == 7777

    # 4. CRITICAL: outgoing packets must include 0x0065 (_ms.armar) to re-bind window 878
    opcodes_sent = [struct.unpack_from('<H', p)[0] for p in ses.paquetes]
    assert 0x0065 in opcodes_sent


def test_pet_rename_handler_sets_renombrada_and_sends_0x001b():
    from unittest import mock
    import app

    class DummyPersonaje:
        def __init__(self):
            self.char_id = 9999
            self.entity_id = 2001
            self.mascotas = {}
            self.mascota = None

    class DummySesion:
        def __init__(self):
            self.rol = 'mundo'
            self.usuario = 'tester'
            self.inventario = {10: 16970}
            self.cantidades = {10: 1}
            self.instancias = {}
            self.personaje = DummyPersonaje()
            self.pet_entity_id = 6001
            self.paquetes = []

        def enviar(self, *pkts):
            self.paquetes.extend(pkts)

    ses = DummySesion()
    pet_ficha = {
        'nombre': 'Chimera',
        'sprite': 3403,
        'tipo': 42816,
        'ranura': 10,
        'instancia': 1010,
        'fuera': True,
        'entidad': 6001,
        'nivel': 72,
        'captured_name': 'Chimera',
    }
    ses.personaje.mascotas['10'] = pet_ficha
    ses.personaje.mascota = pet_ficha

    srv = app.Servidor('127.0.0.1', 8888, 8889, 8890)
    # Client sends c2s 0x003D with new name "Shadow"
    payload = b'Shadow\x00'
    with mock.patch.object(app, '_guardar_bolsa'), mock.patch.object(cuentas, 'guardar_mascota'):
        srv.manejar(ses, 0x003D, None, None, 'test', payload)

    # 1. Name updated and flagged as renombrada
    assert pet_ficha['nombre'] == 'Shadow'
    assert pet_ficha['renombrada'] is True

    # 2. Only S2C 0x001B (inventory slot refresh) sent. S2C 0x003D / 0x0050 cause client crash.
    opcodes = [struct.unpack_from('<H', p)[0] for p in ses.paquetes]
    assert 0x001B in opcodes
    assert 0x003D not in opcodes
    assert 0x0050 not in opcodes


def test_inventory_swap_active_pet_preserves_instance_and_sends_0x0065():
    from unittest import mock
    import app

    class DummyPersonaje:
        def __init__(self):
            self.char_id = 9999
            self.entity_id = 2001
            self.nombre = 'Tester'
            self.nivel = 50
            self.clase = 1
            self.tile_x = 100
            self.tile_y = 100
            self.mejoras = {}
            self.hp = 1000
            self.hp_max = 1000
            self.mp = 1000
            self.mp_max = 1000
            self.habilidades = []
            self.skills_equipadas = []
            self.str = 100
            self.con = 100
            self.int = 100
            self.dex = 100
            self.agi = 100
            self.puntos_status = 0
            self.puntos_skill = 0
            self.exp = 0
            self.exp_max = 100000
            self.mascotas = {}
            self.mascota = None

    class DummySesion:
        def __init__(self):
            self.rol = 'mundo'
            self.usuario = 'tester'
            self.inventario = {20: 16970, 25: 1201}  # slot 20: pet egg, slot 25: potion
            self.cantidades = {20: 1, 25: 5}
            self.instancias = {20: b'\x12\x34\x56\x78\x00\x00\x00\x00', 25: b'\x87\x65\x43\x21\x00\x00\x00\x00'}
            self.personaje = DummyPersonaje()
            self.pet_entity_id = 6001
            self.paquetes = []

        def enviar(self, *pkts):
            self.paquetes.extend(pkts)

    ses = DummySesion()
    pet_ficha = {
        'nombre': 'Chimera',
        'sprite': 3403,
        'tipo': 42816,
        'ranura': 20,
        'instancia': 7777,
        'fuera': True,
        'entidad': 6001,
        'nivel': 72,
        'hp': 500,
        'hp_max': 500,
        'mp': 300,
        'mp_max': 300,
        'saciedad': 100,
        'intimidad': 80,
    }
    ses.personaje.mascotas['20'] = pet_ficha
    ses.personaje.mascota = pet_ficha

    srv = app.Servidor('127.0.0.1', 8888, 8889, 8890)
    # Swap item in slot 20 with item in slot 25
    payload = struct.pack('<HH', 20, 25)
    with mock.patch.object(app, '_guardar_bolsa'):
        srv.manejar(ses, 0x0012, None, None, 'test', payload)

    # 1. Slots swapped in inventory
    assert ses.inventario[20] == 1201
    assert ses.inventario[25] == 16970

    # 2. Pet updated to slot 25
    assert '25' in ses.personaje.mascotas
    assert '20' not in ses.personaje.mascotas
    assert pet_ficha['ranura'] == 25

    # 3. Instance preserved!
    assert pet_ficha['instancia'] == 7777

    # 4. Outgoing packets include 0x0065 (_ms.armar)
    opcodes_sent = [struct.unpack_from('<H', p)[0] for p in ses.paquetes]
    assert 0x0065 in opcodes_sent


def test_pet_presence_broadcasts_0x0050_with_owner_link_and_no_dummy_npc():
    import presencia

    class DummyP:
        def __init__(self, name, cid, eid):
            self.nombre = name
            self.char_id = cid
            self.entity_id = eid
            self.tile_x = 50
            self.tile_y = 50
            self.stage = 1
            self.mascota = {
                'nombre': 'Kini',
                'sprite': 3403,
                'fuera': True,
                'entidad': 7001,
                'x': 51,
                'y': 50,
                'saciedad': 150,
                'hp': 1000,
                'hp_max': 1000,
            }

    class DummyS:
        def __init__(self, name, cid, eid):
            self.personaje = DummyP(name, cid, eid)
            self.pet_entity_id = 7001
            self.paquetes = []
            self.conectada = True
            self.rol = 'mundo'

        def enviar(self, *pkts):
            self.paquetes.extend(pkts)

    owner = DummyS('Karma', 101, 2001)
    viewer = DummyS('KarmaV3', 102, 2002)

    pkts = presencia.paquetes_mascota(owner)
    assert len(pkts) >= 3

    # First packet MUST be 0x0050 (entidad_mundo)
    opcodes = [struct.unpack_from('<H', p)[0] for p in pkts]
    assert opcodes[0] == 0x0050
    assert 0x0008 not in opcodes  # NO dummy NPC packet!

    # 0x0050 payload: pet sprite 3403, name Kini, owner ID
    p50 = pkts[0]
    # offset 16 is pet name (first 2 bytes are opcode, so +18 in raw packet)
    assert p50[18:22] == b'Kini'
    # owner entity ID is at offset 75 (+2 opcode = 77)
    owner_pub = presencia.entidad_de(owner)
    assert struct.unpack_from('<I', p50, 77)[0] == owner_pub
    # sprite is at offset 45 (+2 = 47)
    assert struct.unpack_from('<H', p50, 47)[0] == 3403

    # Link packet (0x001D kind 0x2A) connects owner_pub to pet 7001
    link_pkt = pkts[1]
    assert struct.unpack_from('<H', link_pkt)[0] == 0x001D
    assert struct.unpack_from('<I', link_pkt, 2)[0] == owner_pub
    assert link_pkt[7] == 0x2A
    assert struct.unpack_from('<I', link_pkt, 8)[0] == 7001


def test_summon_presence_broadcasts_klass_38_and_owner_links():
    import presencia

    class DummyP:
        def __init__(self, name, cid, eid):
            self.nombre = name
            self.char_id = cid
            self.entity_id = eid
            self.tile_x = 60
            self.tile_y = 60
            self.stage = 1
            self.mascota = None

    class DummyS:
        def __init__(self, name, cid, eid):
            self.personaje = DummyP(name, cid, eid)
            self.pet_entity_id = None
            self.invocacion = {
                'entity_id': 8001,
                'npc_type': 1894,
                'nombre': 'Mercenary',
                'sprite': 40005,
                'hp': 500,
                'hp_max': 500,
                'tile_x': 61,
                'tile_y': 60,
            }
            self.invocacion2 = None
            self.paquetes = []
            self.conectada = True
            self.rol = 'mundo'

        def enviar(self, *pkts):
            self.paquetes.extend(pkts)

    owner = DummyS('Karma', 101, 2001)
    pkts = presencia.paquetes_invocaciones(owner)
    assert len(pkts) == 4

    # Opcode 0x0008 with klass 38
    opcodes = [struct.unpack_from('<H', p)[0] for p in pkts]
    assert 0x0008 in opcodes
    assert 0x0013 in opcodes

    owner_pub = presencia.entidad_de(owner)
    # Check 0x0013 link packets
    link_owner = pkts[2]
    assert struct.unpack_from('<H', link_owner)[0] == 0x0013
    assert struct.unpack_from('<I', link_owner, 2)[0] == owner_pub
    assert link_owner[7] == 0x3D
    assert struct.unpack_from('<I', link_owner, 8)[0] == 8001


def test_other_player_receives_pet_and_summon_combat_packets():
    """The shared-room mirror must carry the complete companion action."""
    from unittest import mock
    import app
    import presencia

    monster = combate.Monstruo(9001, 1, 'Lily', (10, 10))
    shared = {9001: monster}

    class DummySession:
        def __init__(self, eid):
            self.personaje = type('P', (), {'entity_id': eid, 'stage': 1})()
            self.monstruos = shared
            self.pet_entity_id = 7001 if eid == 100 else None
            self.invocacion = {'entity_id': 8001} if eid == 100 else None
            self.invocacion2 = None
            self.cerrada = False
            self.received = []

        def enviar_sin_espejo(self, *packets):
            self.received.extend(packets)

        def volcar(self):
            pass

    owner = DummySession(100)
    viewer = DummySession(200)
    room = type('Room', (), {'stage': 1, 'monstruos': shared,
                             'sesiones': [owner, viewer]})()
    owner._sala = viewer._sala = room

    pet_packets = (
        combate.ataque(7001, 9001, combate.anim_de_monstruo('Lily')),
        combate.numero_de_dano(7001, 9001, 25, ataque=0, efecto=0),
        combate.cierre_de_dano(7001, 9001, ataque=0, efecto=0),
    )
    summon_packets = (
        combate.ataque(8001, 9001, combate.anim_de_monstruo('Mercenary')),
        combate.numero_de_dano(8001, 9001, 40, ataque=656, efecto=136),
        combate.cierre_de_dano(8001, 9001, ataque=656, efecto=136),
    )
    with mock.patch.object(presencia, 'entidad_de', return_value=500100):
        app._espejar(owner, pet_packets + summon_packets)

    assert viewer.received == list(pet_packets + summon_packets)
    assert [struct.unpack_from('<H', p)[0] for p in viewer.received].count(0x000A) == 2
    assert [struct.unpack_from('<H', p)[0] for p in viewer.received].count(0x0011) == 4


