"""
Construccion de la respuesta de login desde cero (sin plantilla).

CREDITO: la estructura viene del proyecto anterior (F:\Ao Proyect\AO), que
la habia derivado del parser del cliente (sub_51B250 / sub_4C4C60). El login
ahi funcionaba; lo que estaba roto era la creacion de personaje.

Bloque de datos de cuenta, sub-mensaje 0x0000, 654 bytes:

    [0-1]      opcode 0x0000
    [2-3]      codigo de error (0 = exito)
    [4]        flag de cuenta (byte_958A39) -- DEBE SER 0
    [5-445]    3 fichas de personaje de 147 B
    [446-478]  flags y LE32 por ranura
    [479-586]  arreglos de EQUIPO: 9 LE32 por ranura (36 B x 3)
    [587-590]  ranuras maximas (LE32)
    [591-594]  indice de servidor (LE32)
    [595-645]  nombres secundarios por ranura (17 B x 3)
    [646+]     arreglo de nivel por servidor

Ficha de personaje (147 B, en 5 + 147*i), offsets relativos:

    [+0]        indice de ranura
    [+1..4]     nivel LE32
    [+5]        class_id
    [+6..10]    apariencia (5 bytes)
    [+11..14]   stage_id LE32  -- CRITICO: con 0 el cliente crashea al cargar
    [+31..34]   ocupacion de ranura LE32 -- no-cero = la ranura TIENE personaje
    [+35..]     nombre terminado en nulo
    [+109..112] HP actual LE32
    [+113..116] HP maximo LE32
    [+117..120] MP actual LE32
    [+121..124] MP maximo LE32

DOS TRAMPAS que costaron varios crashes:

1. `[4]` invertido. `sub_4C16D0` hace `if (!byte_958A39)` para habilitar la
   creacion: un valor NO CERO la DESHABILITA, y sale el cartel
   "You are unable to create a character unless you buy a character position".

2. `[479-586]` son los 9 ids por ranura que `sub_71C530` pasa a `sub_71C380`,
   que los busca con `sub_58BA30` -- y esa funcion solo acepta 1..36,
   devolviendo NULL fuera de rango. El caller no valida y revienta en
   EIP=0x0071C3F7. Dejarlos en CERO evita el problema: el bucle saltea los
   ceros.
"""
import struct

# 658, no 654: medido contra un bloque REAL capturado de un servidor vivo
# (656 bytes de cuerpo + 2 del opcode). El 654 venia de una estimacion previa.
TAM_CUENTA = 658
TAM_FICHA = 147
BASE_FICHAS = 5
OFF_HP_MAX = 455       # dword_958E0C: HP maximo por ranura
OFF_MP_MAX = 467       # dword_958E10: MP maximo por ranura
OFF_SKILLS = 479       # seis habilidades por ranura, no equipo (ver abajo)
PRIMERA_BOLSA = 20     # de la 20 en adelante es la mochila
RANURAS_VISIBLES = (2, 3, 4, 5, 6)   # cuerpo, mano derecha, izquierda, guantes, pies
OFF_MAX_RANURAS = 587
OFF_NOMBRES2 = 595
OFF_SERVIDOR = 591     # indice de sub-canal; el cliente lo compara con el
                       # 分流 de su server.xml. Mandar 0 lo dejaba sin avanzar.
OFF_CUENTA = 61        # nombre de la CUENTA (no del personaje), 12 bytes.
                       # Diff contra una captura real: ahi decia el usuario y
                       # yo mandaba ceros.
OFF_SRV_DATOS = 646    # arreglo por servidor. La documentacion previa lo
                       # describe como "nivel/requisito por servidor". En la
                       # captura real valia 70, 40, 41 -- pero ESE personaje
                       # era de nivel alto. Copiarlos tal cual probablemente
                       # le decia al cliente que cada canal exige nivel 70,
                       # con un personaje de nivel 1. Se mandan en 0.
MAX_RANURAS = 3


def _ficha(buf, base, idx, p):
    buf[base + 0] = idx & 0xFF
    struct.pack_into('<I', buf, base + 1, p.get('nivel', 1) & 0xFFFFFFFF)
    buf[base + 5] = p.get('class_id', 0) & 0xFF
    for i, v in enumerate(p.get('apariencia', [0] * 5)[:5]):
        buf[base + 6 + i] = v & 0xFF
    # stage_id: con 0 el cliente crashea al cargar el mapa
    struct.pack_into('<I', buf, base + 11, (p.get('stage_id') or 129) & 0xFFFFFFFF)
    # no-cero = la ranura tiene personaje (si no, abre el dialogo de creacion)
    struct.pack_into('<I', buf, base + 31, p.get('char_id', idx + 1) & 0xFFFFFFFF)
    nom = str(p.get('nombre', '')).encode('ascii', 'replace')[:16]
    buf[base + 35: base + 35 + len(nom)] = nom
    buf[base + 35 + len(nom)] = 0
    # HP y MP: el cliente muestra "actual / maximo". El campo entre ambos
    # (+113) figuraba como "desconocido" en la documentacion previa; con el
    # maximo sin escribir la ficha mostraba "50 / 0", asi que casi con certeza
    # +113 es hp_max y +121 mp_max. Se escriben los cuatro.
    # Solo el VALOR ACTUAL vive en la ficha. El MAXIMO va en arreglos
    # aparte (ver OFF_HP_MAX / OFF_MP_MAX en bloque_cuenta).
    struct.pack_into('<I', buf, base + 109, p.get('hp', 0) & 0xFFFFFFFF)
    struct.pack_into('<I', buf, base + 113, p.get('hp_max', p.get('hp', 0)) & 0xFFFFFFFF)
    struct.pack_into('<I', buf, base + 117, p.get('mp', 0) & 0xFFFFFFFF)
    struct.pack_into('<I', buf, base + 121, p.get('mp_max', p.get('mp', 0)) & 0xFFFFFFFF)
    # Equipo que se ve en el muneco del selector: cinco LE32 desde +81.
    # Medido en el bloque que mando el servidor privado para un personaje
    # equipado: +84..+100 del cuerpo, o sea +81..+97 dentro del slot, con
    # 26 (prenda), 10 y 10 (las dos armas), 28 (guantes) y 30 (zapatos),
    # en ese orden. Antes iba todo en cero y por eso el personaje aparecia
    # desnudo en la pantalla de seleccion.
    inv = p.get('inventario') or {}
    puesto = {int(r): it for r, it in inv.items() if int(r) < PRIMERA_BOLSA}
    for k, ranura in enumerate(RANURAS_VISIBLES):
        struct.pack_into('<I', buf, base + 81 + 4 * k,
                         puesto.get(ranura, 0) & 0xFFFFFFFF)


def bloque_cuenta(personajes, ranuras=MAX_RANURAS, subcanal=2,
                  cuenta='', srv_datos=(0, 0, 0)) -> bytes:
    """Devuelve el cuerpo del sub-mensaje 0x0000 (sin el opcode)."""
    a = bytearray(TAM_CUENTA)
    nc = str(cuenta).encode('ascii', 'replace')[:11]
    a[OFF_CUENTA:OFF_CUENTA + len(nc)] = nc
    for k, v in enumerate(srv_datos[:3]):
        struct.pack_into('<I', a, OFF_SRV_DATOS + 4 * k, v)
    # a[2:4] = 0  -> exito
    # a[4]   = 0  -> creacion de personaje HABILITADA (ver trampa 1)
    struct.pack_into('<I', a, OFF_MAX_RANURAS, ranuras)
    # Sub-canal: en la captura real valia 3, igual que el 分流="3" del
    # server.xml de ese cliente. El nuestro declara 分流="2".
    struct.pack_into('<I', a, OFF_SERVIDOR, subcanal)
    for i in range(MAX_RANURAS):
        # El indice de ranura se escribe SIEMPRE, incluso si esta vacia.
        # Medido contra una captura real: en +150 y +297 (ranuras 1 y 2, ambas
        # sin personaje) el servidor mandaba 1 y 2; yo las salteaba enteras y
        # quedaban en cero.
        a[BASE_FICHAS + i * TAM_FICHA] = i & 0xFF
        if i >= len(personajes) or not personajes[i]:
            continue                      # ranura vacia: se puede crear
        base_f = BASE_FICHAS + i * TAM_FICHA
        _ficha(a, base_f, i, personajes[i])
        # Dos valores mas que la captura real trae y yo mandaba en cero.
        # No se sabe que son; se replican por estar medidos.
        struct.pack_into('<I', a, base_f + 52, personajes[i].get('unk_52', 5481))
        a[base_f + 81] = personajes[i].get('unk_81', 26) & 0xFF
        # (el bloque de nombres secundarios de 595+ figura en CERO en la
        #  captura real; escribir ahi era invento mio)
        # HP/MP MAXIMOS: NO van en la ficha. El cliente los lee de arreglos
        # separados. De sub_4C4C60 en el binario:
        #   HP: sprintf("%d / %d", *(&dword_958CB5 + 147*slot), dword_958E0C[8*slot])
        #   MP: sprintf("%d / %d", *(&dword_958CBD + 147*slot), dword_958E10[8*slot])
        # El actual sale de la ficha (+109 y +117); el maximo, de estos
        # arreglos, que se llenan desde los offsets 455 y 467 del bloque.
        # Escribirlos dentro de la ficha dejaba la tarjeta en "205 / 0".
        struct.pack_into('<I', a, OFF_HP_MAX + 4 * i,
                         personajes[i].get('hp_max', personajes[i].get('hp', 0)) & 0xFFFFFFFF)
        struct.pack_into('<I', a, OFF_MP_MAX + 4 * i,
                         personajes[i].get('mp_max', personajes[i].get('mp', 0)) & 0xFFFFFFFF)
    # [479] son las HABILIDADES evaluadas para la clase (sub_71C380).
    # Cada ranura ocupa 36 bytes (9 DWORDs = 36 B, desde 479 + 36 * i):
    # seis habilidades iniciales y tres ceros. Con salto de 24 se solapaban.
    for i in range(min(len(personajes), ranuras)):
        for k, h in enumerate(personajes[i].get('habilidades', [])[:6]):
            sid = h[0] if isinstance(h, (list, tuple)) else h
            struct.pack_into('<I', a, OFF_SKILLS + 36 * i + 4 * k,
                             int(sid) & 0xFFFFFFFF)
    return bytes(a[2:])                   # el opcode lo pone quien empaqueta


def motd(texto: str) -> bytes:
    """Cuerpo del sub-mensaje 0x000C: [LE32 flags][LE32 largo][texto]."""
    t = texto.encode('ascii', 'replace') + b'\x00'
    return struct.pack('<II', 0x69402978, len(t)) + t
