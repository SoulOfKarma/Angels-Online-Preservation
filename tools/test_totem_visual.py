"""Crashing Hillock position and rollback of the discarded shadow patch."""
import pathlib
import struct
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
import cliente_local
import totem_war as tw


@pytest.mark.parametrize('faction', [0, 1, 2, 3, 4])
def test_crashing_hillock_spawn_and_packet_use_requested_position(monkeypatch, faction):
    monkeypatch.setattr(tw, 'MODO', 'antigua')
    monkeypatch.setattr(tw, 'nivel_totem', lambda stage: (1, 0))
    monkeypatch.setattr(tw, 'liga_duena', lambda stage: None)
    monkeypatch.setattr(tw, 'faccion_duena', lambda stage: faction)
    mob = tw.crear_totem(8)
    assert (mob.tile_x, mob.tile_y) == (92, 174)
    assert (mob.spawn_x, mob.spawn_y) == (92, 174)
    assert mob.es_estatico and mob.npc_type == 21397
    packet = tw.spawn_totem(mob)
    assert packet[:2] == struct.pack('<H', 0x012E)
    assert struct.unpack_from('<II', packet, 10) == (92, 174)
    assert struct.unpack_from('<H', packet, 36)[0] == tw.sprite_totem(8)
    another = tw.crear_totem(8)
    assert (another.tile_x, another.tile_y) == (92, 174)


def test_other_totem_positions_are_unchanged():
    assert {k: v for k, v in tw.TOTEM_CAMPO.items() if k != 8} == {
        9: (147, 100), 11: (196, 56), 12: (288, 11), 15: (151, 156),
        16: (162, 88), 17: (48, 95), 21: (153, 104)}
    assert tw.TOTEM_TILE == (165, 97)
    assert tw.TOTEM_ENTRENAMIENTO == {
        7: (216, 46), 20: (221, 56), 22: (206, 107), 28: (130, 92)}


def catalog(sprite=60238, flags=b'SP_ATTRIB_DISTURB, SP_ATTRIB_HITTEST, SP_ATTRIB_BIAS'):
    return (b'[OBJECT]\r\nName = \xa6\xd1\xb9\xcf\r\nSequence = '
            + str(sprite).encode() + b'\r\nFlags = ' + flags
            + b'\r\nProcess = SERV_CLASS_TOTEMOBJ\r\n')


@pytest.mark.parametrize('sprite', [60237, 60238, 60239, 60240])
def test_restore_only_our_discarded_shadow_edit(sprite):
    raw = catalog(sprite)
    expected = raw.replace(b'SP_ATTRIB_BIAS', b'SP_ATTRIB_SHADOW, SP_ATTRIB_BIAS')
    assert cliente_local._restaurar_sombra_totems_obd_bytes(raw) == expected
    assert cliente_local._restaurar_sombra_totems_obd_bytes(expected) == expected


def test_unrelated_objects_and_custom_flags_are_preserved():
    raw = catalog(60054) + catalog(60238, b'SP_ATTRIB_HITTEST, SP_ATTRIB_BIAS')
    assert cliente_local._restaurar_sombra_totems_obd_bytes(raw) == raw


def test_startup_restores_applied_patch_without_replacing_whole_pak(tmp_path, monkeypatch):
    pak = tmp_path / 'update26.pak'
    pak.touch()
    raw = catalog()
    writes = []
    monkeypatch.setattr(cliente_local, 'registrar_medalla_en_servidor', lambda: None)
    monkeypatch.setattr(cliente_local, 'ruta_cliente', lambda: tmp_path)
    monkeypatch.setattr(cliente_local, 'RAIZ_PROYECTO', tmp_path)
    monkeypatch.setattr(cliente_local._cf, 'MODO_ESTACION', 'normal')
    monkeypatch.setattr(cliente_local, '_asegurar_bak', lambda p: tmp_path / 'original.bak')
    monkeypatch.setattr(cliente_local, '_extraer_archivo_pak',
                        lambda p, n: raw if p == pak and n == r'SETTING\SERVER.OBD' else b'')
    monkeypatch.setattr(cliente_local, 'actualizar_pak_cliente',
                        lambda p, replacements: writes.append((p, replacements)))
    cliente_local.aplicar_modo_estacion('normal')
    assert writes == [(pak, {r'SETTING\SERVER.OBD':
                            cliente_local._restaurar_sombra_totems_obd_bytes(raw)})]
