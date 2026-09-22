"""Compra, venta, uso y destruccion con los bytes reales de la captura.

Los mensajes son los que mando el cliente en Celestia el 22/09:
    comprar   0x0027  02000000 42000000 0a000000 43000000 0a000000
    vender    0x0028  02000000 6b480300 2e23b26a 05000000 ...
    usar      0x002E  2a000000 00
    destruir  0x0013  2900 42000000
"""
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'server'))

import inventario as inv


def test_formato_compra():
    c = bytes.fromhex('02000000420000000a000000430000000a000000')
    n = struct.unpack_from('<I', c, 0)[0]
    assert n == 2, n
    pedido = [struct.unpack_from('<II', c, 4 + 8 * i) for i in range(n)]
    assert pedido == [(66, 10), (67, 10)], pedido
    print('  compra: 2 items, 10 y 10 unidades  OK')


def test_formato_venta():
    c = bytes.fromhex('020000006b4803002e23b26a050000006c4803002e23b26a06000000')
    n = struct.unpack_from('<I', c, 0)[0]
    assert n == 2, n
    for i in range(n):
        off = 4 + 12 * i
        inst = c[off:off + 8]
        cant = struct.unpack_from('<I', c, off + 8)[0]
        assert len(inst) == 8
        assert cant in (5, 6), cant
    print('  venta: instancia de 8 bytes + cantidad  OK')


def test_formato_destruir():
    c = bytes.fromhex('290042000000')
    ranura, item_id = struct.unpack_from('<HI', c, 0)
    assert (ranura, item_id) == (41, 66), (ranura, item_id)
    print('  destruir: casilla 41, item 66  OK')


def test_vaciar_ranura_byte_a_byte():
    # respuesta real del servidor: 0100000002011e0100002900
    esperado = bytes.fromhex('0100000002011e0100002900')
    nuestro = inv.vaciar_ranura(286, 41)
    assert nuestro[:2] == struct.pack('<H', 0x001B)
    assert nuestro[2:] == esperado, nuestro[2:].hex()
    print('  0x001B de casilla vacia identico al capturado  OK')


def test_cantidad_en_el_0x001A():
    """La cantidad va en el offset 44 del mensaje, +40 de la entrada."""
    msg = inv.completo(286, [(41, 66, 10)])
    cuerpo = msg[2:]
    assert struct.unpack_from('<I', cuerpo, 0)[0] == 1
    assert struct.unpack_from('<I', cuerpo, 13)[0] == 66, 'item_id en 13'
    assert struct.unpack_from('<H', cuerpo, 42)[0] == 41, 'casilla en 42'
    assert struct.unpack_from('<I', cuerpo, 44)[0] == 10, 'cantidad en 44'
    print('  item/casilla/cantidad en 13/42/44  OK')


def test_resolver_instancia():
    """Dos montones del MISMO item tienen instancias distintas."""
    instancias = {41: inv.instancia_nueva(), 42: inv.instancia_nueva(),
                  43: inv.instancia_nueva()}
    assert len(set(bytes(v) for v in instancias.values())) == 3
    for ranura, inst in instancias.items():
        assert inv.ranura_de_instancia(instancias, inst) == ranura
    assert inv.ranura_de_instancia(instancias, bytes(8)) is None
    print('  instancia -> casilla, una por monton  OK')


def test_formato_separar():
    # c2s 0x002F real: sacar una pocion de la casilla 41 a la 43
    c = bytes.fromhex('0b2b00290001000000')
    destino, origen = struct.unpack_from('<HH', c, 1)
    cuantas = struct.unpack_from('<I', c, 5)[0]
    assert (origen, destino, cuantas) == (41, 43, 1), (origen, destino, cuantas)
    print('  separar: casilla 41 -> 43, una unidad  OK')


def test_apilable():
    assert inv.es_apilable(66), 'una pocion se apila'
    assert not inv.es_apilable(10), 'un sable no'
    print('  apilable segun si es equipable  OK')


if __name__ == '__main__':
    for f in (test_formato_compra, test_formato_venta, test_formato_destruir,
              test_vaciar_ranura_byte_a_byte, test_cantidad_en_el_0x001A,
              test_resolver_instancia, test_formato_separar,
              test_apilable):
        f()
    print('\nTIENDA Y CANTIDADES: OK')
