"""Regresiones de textos y despacho x86 del mapa (sin abrir el juego)."""
import pathlib
import struct
import sys

import pytest

import recuperar_traducciones_update32 as recovery
import parchear_angel_update32 as patch


def test_text_only_keeps_new_rows_and_taiwan_stats():
    old = ('<root><道具 編號="1" 原型介面="5" 基本名稱="60星幸運錘" '
           '價格="20" 說明定義="舊說明" 物品類別="幸運骰"/>'
           '<道具 編號="99" 基本名稱="new patch" 價格="42"/></root>').encode()
    source = ('<root><道具 編號="1" 原型介面="5" 基本名稱="60-star Lucky Hammer" '
              '價格="10" 說明定義="A &amp; B" 物品類別="幸運骰"/></root>').encode()
    new, changes, conflicts = recovery.recuperar(old, source)
    assert not conflicts
    assert changes['1']['基本名稱'] == '60-star Lucky Hammer'
    assert b'A &amp; B' in new and b'amp;amp' not in new
    assert '價格="20"'.encode() in new
    assert '物品類別="幸運骰"'.encode() in new
    assert '<道具 編號="99" 基本名稱="new patch" 價格="42"/>'.encode() in new
    assert recovery.recuperar(new, source) == (new, {}, [])


def test_reused_id_is_not_a_translation():
    old = '<r><道具 編號="83266" 原型介面="1" 基本名稱="機兵蛋"/></r>'.encode()
    ref = '<r><道具 編號="83266" 原型介面="2" 基本名稱="Rank Promotion Medal"/></r>'.encode()
    new, changes, conflicts = recovery.recuperar(old, ref)
    assert new == old and not changes and conflicts


def test_unknown_source_does_not_replace_target_text():
    old = '<r><道具 編號="1" 基本名稱="Translated"/></r>'.encode()
    ref = '<r><道具 編號="1" 基本名稱="未翻譯"/></r>'.encode()
    assert recovery.recuperar(old, ref) == (old, {}, [])


@pytest.fixture(scope='module')
def native():
    path = pathlib.Path(r'C:\AO\Angels Online\angel.dat')
    if not path.exists():
        pytest.skip('se requiere el IGG local para comprobar su switch real')
    data = bytearray(path.read_bytes())
    secs, _ = patch.secciones(data)
    # Despues de instalar, recuperar el switch original para comparar.
    off = patch.a_fichero(secs, patch.DRAW_HOOK)
    data[off:off + 10] = patch.DRAW_ORIGINAL
    for i, section in enumerate(secs):
        if section[0] == '.twmap':
            # Cabecera/bytes de la seccion se conservan; quitarla de la
            # lista para que el parche pueda generar su nueva seccion.
            pe = struct.unpack_from('<I', data, 0x3c)[0]
            table = pe + 24 + struct.unpack_from('<H', data, pe + 20)[0]
            assert i == len(secs) - 1
            data[table + i * 40:table + (i + 1) * 40] = bytes(40)
            struct.pack_into('<H', data, pe + 6, i)
    return bytes(data)


def emulate(data, page):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'work/vendor'))
    unicorn = pytest.importorskip('unicorn')
    from unicorn import x86_const as x86
    uc = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    uc.mem_map(0x400000, 0x900000)
    uc.mem_map(0x1000000, 0x10000)
    uc.mem_map(0x2000000, 0x10000)
    for _, va, _, raw, size in patch.secciones(data)[0]:
        uc.mem_write(va, bytes(data[raw:raw + size]))
    this, esp, stop = 0x2000000, 0x1008000, 0x400010
    uc.mem_write(this + 0x11c, struct.pack('<I', page & 0xffffffff))
    uc.mem_write(esp, struct.pack('<III', stop, 0, 0))
    uc.reg_write(x86.UC_X86_REG_ECX, this)
    uc.reg_write(x86.UC_X86_REG_ESP, esp)
    calls = []

    def hook(uc, addr, size, user):
        if addr in (0x5AA6A0, patch.DRAW_REGION):
            sp = uc.reg_read(x86.UC_X86_REG_ESP)
            ret = struct.unpack('<I', uc.mem_read(sp, 4))[0]
            region = None if addr == 0x5AA6A0 else struct.unpack('<I', uc.mem_read(sp + 4, 4))[0]
            calls.append((addr, region, uc.reg_read(x86.UC_X86_REG_ECX)))
            uc.reg_write(x86.UC_X86_REG_ESP, sp + (4 if region is None else 8))
            uc.reg_write(x86.UC_X86_REG_EIP, ret)

    uc.hook_add(unicorn.UC_HOOK_CODE, hook)
    uc.emu_start(0x5AA3D0, stop, count=1000)
    assert uc.reg_read(x86.UC_X86_REG_EIP) == stop
    assert uc.reg_read(x86.UC_X86_REG_ESP) == esp + 12
    return calls


@pytest.mark.parametrize('page', list(range(32)) + [-1])
def test_native_dispatch_old_pages_unchanged_and_30_draws_region29(native, page):
    patched = patch.parchear_dibujo_region30(bytearray(native))
    result = emulate(patched, page)
    if page == 30:
        assert emulate(native, page) == []  # Reproduce el fallo anterior.
        assert result == [(patch.DRAW_REGION, 29, 0x2000000)]
    else:
        assert result == emulate(native, page)


def test_map_patch_idempotent_and_rejects_other_code(native):
    patched = patch.parchear_dibujo_region30(bytearray(native))
    assert patch.parchear_dibujo_region30(bytearray(patched)) == patched
    secs, _ = patch.secciones(native)
    corrupt = bytearray(native)
    corrupt[patch.a_fichero(secs, patch.DRAW_HOOK)] ^= 1
    with pytest.raises(ValueError):
        patch.parchear_dibujo_region30(corrupt)
