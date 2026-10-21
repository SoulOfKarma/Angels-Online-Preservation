"""Small checks for the previously pending title and pathfinding changes."""
import pathlib
import struct
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import logros
import transitable


@pytest.mark.parametrize('add', [True, False])
def test_title_update_uses_single_bit_packet_not_character_recreation(add):
    packet = logros.paquete_titulo_nuevo(123, 137, add)
    assert packet == struct.pack('<HIBBII', 0x001D, 123, 1, 56, 137, int(add))


@pytest.fixture
def wall_map(monkeypatch):
    width = height = 7
    bits = bytearray((width * height + 7) // 8)
    for y in range(height):
        for x in range(width):
            if x == 3 and y < 5:
                continue
            index = y * width + x
            bits[index >> 3] |= 1 << (index & 7)
    monkeypatch.setattr(transitable, '_MAPAS', {999: (width, height, bytes(bits))})
    return 999


def test_path_routes_around_wall_without_cutting_corners(wall_map):
    start, end = (1, 1), (5, 1)
    route = transitable.camino(wall_map, start, end)
    assert route and route[-1] == end
    previous = start
    for tile in route:
        assert transitable.linea_libre(wall_map, previous, tile)
        assert transitable.se_pisa(wall_map, *tile)
        previous = tile
    assert any(y >= 5 for x, y in route)


def test_movement_segment_does_not_animate_through_wall(wall_map):
    start = (1, 1)
    end, reachable = transitable.tramo(wall_map, start, (5, 1), 6)
    assert reachable
    assert transitable.linea_libre(wall_map, start, end)


def test_path_search_is_bounded(wall_map):
    assert transitable.camino(wall_map, (1, 1), (5, 1), limite=2) == []


def test_unknown_maps_keep_previous_straight_line_fallback(monkeypatch):
    monkeypatch.setattr(transitable, '_MAPAS', {})
    assert transitable.camino(999, (0, 0), (3, 0)) == [(1, 0), (2, 0), (3, 0)]
    assert transitable.tramo(999, (0, 0), (3, 0), 4) == ((2, 0), True)
