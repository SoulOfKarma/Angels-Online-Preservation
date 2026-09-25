"""Las estatuas de Seaside Grotto: hablarles teletransporta.

Mecanismo medido el 25/09/2026 en el cliente oficial de Taiwan, y distinto de
todo lo que ya habia. No es el 0x0016 de los portales internos de Lost Trail
ni el menu de los de Bearscape: aqui hay que HABLARLE al objeto.

    c2s 0x0005 [u32 entidad][u16 0]    clic sobre la estatua
    s2c 0x0012 mensaje 516358 con dos opciones, Yes y No
    c2s 0x000B [0a]                    se elige la primera
    s2c 0x0012 de nueve ceros          se cierra el cuadro
    s2c 0x0003 [u32 yo][u32 x][u32 y]  y aparece al otro lado

El 0x0a es 10, que es dialogos.PRIMERA_OPCION, o sea el indice 0: "Yes".

COMO SE ENCONTRO, que costo dos intentos. Primero se miro el c2s 0x000F que
sale justo despues del dialogo, y no era: aparece 95 veces por sesion, es un
latido. El bueno es el 0x000B, que sale DOS o TRES veces en toda la sesion y
coincide exactamente con las cinco veces que hubo salto, faltando en las tres
que no lo hubo.
"""
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'proto'))

import app          # noqa: E402
import dialogos     # noqa: E402

ESTATUA = 871761017          # la de (215,131), la que mas se uso
LLEGADA = [244, 143]


def test_config():
    """La estatua esta declarada en portales.json y se encuentra por entidad."""
    e = app._estatua_con_entidad(402, ESTATUA)
    assert e is not None, 'la estatua de Seaside Grotto no esta declarada'
    assert e['msg'] == 516358
    assert e['opciones'] == [516031, 516032]
    assert e['llegada'] == LLEGADA
    # Y no aparece donde no debe.
    assert app._estatua_con_entidad(13, ESTATUA) is None
    assert app._estatua_con_entidad(402, 12345) is None


def test_dialogo_bien_armado():
    """El 0x0012 sale con la cabecera de nueve bytes, las dos opciones y las
    dos acciones, en ese orden. Mide 2 + 9 + 4*2 + 4*2 = 27 bytes con el
    opcode, o sea 25 de cuerpo, que es lo que midio la captura."""
    e = app._estatua_con_entidad(402, ESTATUA)
    b = app._dialogo_de_estatua(e)
    assert b[:2] == struct.pack('<H', 0x0012)
    cuerpo = b[2:]
    assert len(cuerpo) == 25, len(cuerpo)
    assert struct.unpack_from('<I', cuerpo, 0)[0] == 516358
    assert cuerpo[7] == 2, 'el numero de opciones va en el offset 7'
    assert struct.unpack_from('<I', cuerpo, 9)[0] == 516031     # Yes
    assert struct.unpack_from('<I', cuerpo, 13)[0] == 516032    # No
    assert struct.unpack_from('<I', cuerpo, 17)[0] == 1000044   # accion del Yes
    assert struct.unpack_from('<I', cuerpo, 21)[0] == 0         # el No no hace nada


def test_el_0a_es_la_primera_opcion():
    """El byte que mando el cliente al aceptar. Si esto cambia, el salto
    dejaria de dispararse sin que nada mas fallara."""
    assert dialogos.PRIMERA_OPCION == 10
    assert dialogos.es_opcion(0x0a)
    assert dialogos.indice_opcion(0x0a) == 0


if __name__ == '__main__':
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith('test_') and callable(fn):
            try:
                fn()
                print('  OK   ' + nombre)
            except AssertionError as e:
                fallos += 1
                print('  FALLA ' + nombre + ': ' + str(e))
    print('fallos:', fallos)
    sys.exit(1 if fallos else 0)
