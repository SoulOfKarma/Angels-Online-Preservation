"""Alquiler de cofres del banco personal (C2S 0x002F 0x17) en base temporal.

REA confirmada contra el cliente CN (angel-cn-unpacked.exe):
  - el paquete mide 9 bytes: [0x17][LE32 cofre 0..23][LE32 periodo 0..3]
  - el estado "alquilado" vive en el array de registros de cuenta y llega por
    0x001B / 0x004E, no por una respuesta dedicada (game.isbankrent 0x58b530)
  - llaves: 1 dia 1999/79744, 7 dias 2000/19243, 30 dias 2001/79743,
    permanente 2734/79742 (+35771 por el rango 0x8bbb..0x8bcc)
"""
import struct
import time

from test_competiciones import world, stored  # noqa: F401
import app
import cuentas
import inventario
import login


def _rentar(session, cofre, periodo):
    app.Servidor.__new__(app.Servidor).manejar(
        session, 0x2F, None, None, 'test',
        struct.pack('<BII', 0x17, cofre, periodo))


def _ultimo_1b_registros(session):
    """Las entradas del ultimo 0x001B enviado (cuenta=LE32 tras el opcode)."""
    salidas = []
    for pk in session.packets:
        if pk[:2] == struct.pack('<H', 0x001B) and len(pk) >= 6:
            n = struct.unpack_from('<I', pk, 2)[0]
            cuerpo = pk[6:]
            entradas, pos = [], 0
            for _ in range(n):
                if pos >= len(cuerpo):
                    break
                extra = struct.unpack_from('<H', cuerpo, pos + 0x33)[0]
                fin = pos + 0x56 + extra
                entradas.append(cuerpo[pos:fin])
                pos = fin
            salidas.append(entradas)
    return salidas


def test_registro_alquiler_banco_layout(world):
    rec = inventario.registro_alquiler_banco(1234, 0, 2734, 0)
    assert len(rec) == 86
    assert rec[0] == 1                      # marca del tag-1
    assert rec[33] == inventario.CONT_BANCO
    assert struct.unpack_from('<I', rec, 9)[0] == 2734
    assert struct.unpack_from('<H', rec, 38)[0] == 0x74
    assert struct.unpack_from('<I', rec, 47)[0] == 0
    # cofres 7..24 caen en la segunda tanda del array (0x186 + cofre)
    rec7 = inventario.registro_alquiler_banco(1234, 7, 35771, 1799999999)
    assert struct.unpack_from('<H', rec7, 38)[0] == 0x186 + 7
    assert struct.unpack_from('<I', rec7, 47)[0] == 1799999999
    assert struct.unpack_from('<I', rec7, 9)[0] == 35771


def test_alquiler_permanente_consumo_y_estado(world):
    session = world.player(items={20: 2734})
    session.cantidades[20] = 1
    session.banco_activo = 'personal'
    world.save(session)

    _rentar(session, 0, 3)

    p = session.personaje
    assert 20 not in session.inventario
    assert p.banco_alquileres == {0: {'clave': 2734, 'expira': None}}
    guardado = stored(world, session)
    assert guardado['banco_alquileres'] == {'0': {'clave': 2734, 'expira': None}}
    registros = [e for grupo in _ultimo_1b_registros(session) for e in grupo]
    assert registros, 'el cliente debe recibir el registro de alquiler por 0x001B'
    rec = registros[-1]
    assert struct.unpack_from('<I', rec, 9)[0] == 2734
    assert struct.unpack_from('<H', rec, 38)[0] == 0x74
    assert any(b'The bank chest rental succeeded.' in pk for pk in session.packets)


def test_alquiler_limitado_por_dias(world):
    session = world.player(items={21: 1999})
    session.cantidades[21] = 2
    session.banco_activo = 'personal'
    world.save(session)

    _rentar(session, 5, 0)

    p = session.personaje
    alq = p.banco_alquileres[5]
    assert alq['clave'] == 1999
    assert alq['expira'] >= time.time() + 86000
    assert alq['expira'] <= time.time() + 86500
    assert session.cantidades.get(20) is None and 20 not in session.inventario
    assert session.inventario.get(21) == 1999 and session.cantidades[21] == 1


def test_alquiler_7_dias_y_30_dias(world):
    session = world.player(items={20: 2000, 21: 2001})
    session.cantidades = {20: 1, 21: 1}
    session.banco_activo = 'personal'

    _rentar(session, 6, 1)
    _rentar(session, 7, 2)

    p = session.personaje
    assert p.banco_alquileres[6]['clave'] == 2000
    assert 7 * 86400 - 60 <= p.banco_alquileres[6]['expira'] - time.time() <= 7 * 86400 + 60
    assert p.banco_alquileres[7]['clave'] == 2001
    assert 30 * 86400 - 60 <= p.banco_alquileres[7]['expira'] - time.time() <= 30 * 86400 + 60


def test_cofre_ya_alquilado_no_consumo(world):
    session = world.player(items={20: 2734})
    session.cantidades[20] = 3
    session.banco_activo = 'personal'
    session.personaje.banco_alquileres = {0: {'clave': 79742, 'expira': None}}
    world.save(session)

    _rentar(session, 0, 3)

    assert session.inventario == {20: 2734}
    assert session.cantidades == {20: 3}
    assert session.personaje.banco_alquileres == {0: {'clave': 79742, 'expira': None}}
    assert any(b'That bank chest is already rented.' in pk for pk in session.packets)


def test_sin_llave_no_alquila_ni_rompe_el_arrastre(world):
    session = world.player(items={22: 16242})   # objeto que no es llave
    session.cantidades[22] = 1
    session.banco_activo = 'personal'
    world.save(session)

    _rentar(session, 0, 3)

    assert session.personaje.banco_alquileres == {}
    assert session.inventario == {22: 16242}
    assert not any(b'The bank chest rental succeeded.' in pk for pk in session.packets)


def test_arrastre_contenedor_14_no_se_confunde(world):
    session = world.player(items={20: 2734})
    session.cantidades[20] = 1
    session.banco_activo = 'personal'
    session.personaje.banco = {5: (1024, 1)}
    world.save(session)

    app.Servidor.__new__(app.Servidor).manejar(
        session, 0x2F, None, None, 'test',
        struct.pack('<BII', 0x0E, 5, 3))

    assert session.personaje.banco_alquileres == {}
    assert 20 in session.inventario


def test_paquete_banco_incluye_alquileres_vigentes(world):
    session = world.player(items={20: 2734})
    session.cantidades[20] = 1
    session.banco_activo = 'personal'
    session.personaje.banco = {3: (1024, 2), 9: (770, 1)}
    session.personaje.banco_alquileres = {
        0: {'clave': 2734, 'expira': None},
        11: {'clave': 2001, 'expira': time.time() + 86400},
        12: {'clave': 2000, 'expira': time.time() - 10},   # vencido: fuera
    }

    pk = app._paquete_banco_personal(session)
    assert pk[:2] == struct.pack('<H', 0x004E)
    cab = struct.unpack_from('<I', pk, 2)[0]
    tipo, cuenta = divmod(cab, 1000)
    assert tipo == 2
    # 3 objetos (oro + 2 banco) + 2 alquileres vigentes
    assert cuenta == 5
    cuerpo = pk[6:]
    entradas, pos = [], 0
    for _ in range(cuenta):
        extra = struct.unpack_from('<H', cuerpo, pos + 0x33)[0]
        fin = pos + 0x56 + extra
        entradas.append(cuerpo[pos:fin])
        pos = fin
    slots = [struct.unpack_from('<H', e, 38)[0] for e in entradas]
    assert 0x74 in slots            # cofre 0
    assert 0x186 + 11 in slots      # cofre 11
    assert 0x186 + 12 not in slots  # vencido no viaja


def test_carga_guarda_alquileres_en_cuentas(world):
    session = world.player(items={20: 2734})
    session.cantidades[20] = 1
    session.banco_activo = 'personal'

    _rentar(session, 23, 3)

    guardado = stored(world, session)
    assert guardado['banco_alquileres'] == {'23': {'clave': 2734, 'expira': None}}
    # la carga de cuentas.py debe devolver el mismo estado
    p = login.Personaje(char_id=session.personaje.char_id,
                        entity_id=session.personaje.entity_id,
                        nombre='x')
    p.banco_alquileres = {int(k): dict(v)
                          for k, v in (guardado.get('banco_alquileres') or {}).items()}
    assert p.banco_alquileres == {23: {'clave': 2734, 'expira': None}}
