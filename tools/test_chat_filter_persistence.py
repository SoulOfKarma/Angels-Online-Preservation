"""Original chat-filter netcommand7 must survive reconnect, including all-off."""
import struct
import pytest
from test_competiciones import world,stored
import app
import chat_filtros as filters
import cuentas
import login


@pytest.mark.parametrize('tab',range(4))
def test_native_check_uncheck_and_reconnect(world,monkeypatch,tab):
    import totem_war
    monkeypatch.setattr(totem_war,'paquete_territorios',lambda:b'')
    s=world.player()
    server=app.Servidor.__new__(app.Servidor)
    # Captured sequence: disable Item, Char.EXP, then Skill EXP.
    for mask in (0x80ff,0x80df,0x809f,0x801f,0x8000):
        server.manejar(s,0x16,None,None,'test',struct.pack('<BI',7,(tab<<16)|mask))
        assert s.personaje.chat_filtros[tab]==mask
        saved=stored(world,s)
        assert saved['chat_filtros'][str(tab)]==mask
        assert saved['custom_field']=='preserve me'
        assert s.packets[-1]==struct.pack('<HIBBII',0x1d,s.personaje.entity_id,1,7,tab,mask)
    saved.update(char_id=s.personaje.char_id,ranura=0,barra=[],quests=[])
    restored=cuentas.personaje_de({'personajes':[saved]},0)
    assert restored.chat_filtros=={tab:0x8000}
    expected=struct.pack('<HIBBII',0x1d,restored.entity_id,1,7,tab,0x8000)
    assert expected in login.secuencia(restored)


def test_tabs_characters_and_invalid_commands_are_isolated(world):
    a,b=world.player(),world.player()
    assert filters.guardar(a,(0<<16)|0x801f)
    assert filters.guardar(a,(2<<16)|0x80ff)
    assert filters.guardar(b,(0<<16)|0x80ff)
    before=stored(world,a)
    for invalid in ((4<<16)|0x801f,0x1f,0xffff):
        assert not filters.guardar(a,invalid)
    assert stored(world,a)==before
    assert a.personaje.chat_filtros=={0:0x801f,2:0x80ff}
    assert b.personaje.chat_filtros=={0:0x80ff}
    assert not cuentas.guardar_chat_filtros(a.usuario,999,{0:0x8000})
    assert stored(world,a)==before


def test_old_character_without_filters_keeps_client_defaults():
    assert not filters.paquetes(login.Personaje())
