"""
Eleccion de clase.

La ventana "Choose profession skills" (id 13300 en setting/eng/wnd04.xml) la
abre el CLIENTE por su cuenta: en la captura pasan 3,5 segundos entre que se
cierra el dialogo de Angel Raphael y que llega el mensaje de eleccion, sin un
solo paquete en medio. El servidor no la abre ni la puede abrir.

Lo unico que viaja es la confirmacion:

    C -> S  0x003A  [U8 skill_id] x 6 + 3 bytes en cero

Los seis valores son las habilidades de la clase elegida. Para Swordsman
llegaron 9, 12, 13, 15, 16 y 33, que en setting/eng/skill.xml son Sword,
Enhance, Grapple, Reserve, Finesse y Garment: los mismos seis que el cliente
muestra en el panel del personaje.

El servidor contesta, por cada habilidad:

    S -> C  0x000D  [LE16 333][U8 7][nombre NUL][2 ceros]   aprendiste esto
    S -> C  0x0042  los stats recalculados

y despues 0x001C con el arbol de habilidades, tres 0x000D mas con los
hechizos iniciales (id de mensaje 425) y los items de regalo (id 492).

PENDIENTE: los stats. skill.xml trae los bonus de cada habilidad (Enhance da
+2 de defensa y +2 de constitucion, Grapple +4 de precision, y el texto de
ayuda lo confirma), asi que se pueden calcular, pero aca todavia no se hace.
"""
import pathlib
import re
import struct

PAKS = pathlib.Path('G:/extracted_paks')
MSG_HABILIDAD = 333        # "aprendiste una habilidad"
MSG_HECHIZO = 425          # "aprendiste un hechizo"
MSG_ITEM = 492             # "obtuviste un item"
_SKILLS = None


def _cargar():
    """Lee setting/eng/skill.xml: numero de habilidad -> nombre en ingles."""
    global _SKILLS
    if _SKILLS is not None:
        return _SKILLS
    _SKILLS = {}
    for pak in ('UPDATE18', 'UPDATE13', 'data1'):
        f = PAKS / pak / 'setting' / 'eng' / 'skill.xml'
        if not f.exists():
            continue
        t = f.read_text(encoding='utf-8', errors='replace')
        for m in re.finditer(r'\u7de8\u865f="(\d+)"\s+\u540d\u7a31="([^"]*)"', t):
            _SKILLS.setdefault(int(m.group(1)), m.group(2))
    return _SKILLS


def nombre(skill_id: int) -> str:
    return _cargar().get(skill_id, f'Skill{skill_id}')


# Los tres hechizos que el servidor real manda al elegir clase, con id de
# mensaje 425. Cuales son depende del arma: en magic.xml cada rama tiene
# exactamente tres registros de nivel 1 bajo su 技能限制1. La correspondencia
# entre la rama china y el numero de habilidad sale de comparar el nombre
# ingles de skill.xml (9 = Sword) con el de la rama (劍術技能 = espada).
RAMA_POR_SKILL = {
    9: '劍術技能',      # Sword       -> Slicing Hit / Swiftness Song / Injury Cure
    10: '斧錘技能',     # Axe         -> Basic Beating / Ferocious Song / Fighting Shield
    11: '槍術技能',     # Spear       -> Basic Attack / Bloody Song / Endless Energy
    17: '弓箭技能',     # Longbow     -> Basic Shot / Accurate Song / Dodge Step
    32: '影刃技能',     # Mantle      -> Stab / Nimble / Poisoned Dagger
    1: '生命技能',      # Life        -> Shock Wave / Cure Spell / Silver Shield
    2: '死靈技能',      # Wraith      -> Poison Hit / Soul Entangle / Summon Skeleton
    3: '混亂技能',      # Chaos       -> Magic Bomb / Charming Blessing / Sage Blessing
    4: '大地技能',      # Earth       -> Flying Dart / Earth Blessing / Shining Charm
}
_HECHIZOS = None


def _cargar_hechizos():
    """magic.xml: rama -> [(numero, nombre)] de los hechizos de nivel 1."""
    global _HECHIZOS
    if _HECHIZOS is not None:
        return _HECHIZOS
    _HECHIZOS = {}
    for pak in ('update26', 'UPDATE18', 'data1'):
        f = PAKS / pak / 'setting' / 'eng' / 'magic.xml'
        if not f.exists():
            continue
        for l in f.read_text(encoding='utf-8', errors='replace').splitlines():
            if '技能等限="1"' not in l or '法術等級="1"' not in l:
                continue
            rama = re.search(r'技能限制1="([^"]+)"', l)
            num = re.search(r'編號="(\d+)"', l)
            nom = re.search(r'名稱="([^"]+)"', l)
            if not (rama and num and nom) or nom.group(1).startswith('test-'):
                continue
            _HECHIZOS.setdefault(rama.group(1), []).append(
                (int(num.group(1)), nom.group(1)))
        if _HECHIZOS:
            break
    for v in _HECHIZOS.values():
        v.sort()
    return _HECHIZOS


def hechizos_iniciales(skill_ids):
    """Los tres hechizos de nivel 1 del arma elegida, en el orden de magic.xml.

    Devuelve [(numero, nombre)] en el orden de magic.xml.

    En la captura llegan como tres 0x000D seguidos, uno por hechizo, justo
    despues del 0x001C del arbol (logs/proxy/mundo_103243_666191_s2c.bin,
    offset 36618), y enseguida un 0x001D que es el que los otorga de verdad.
    Ese log es de un personaje de ESPADA (los ids son 601/602/603) y trae
    "Slicing Chop I": ese servidor tiene la 601 renombrada, en el cliente se
    llama "Slicing Hit I".
    """
    tabla = _cargar_hechizos()
    for sid in skill_ids:
        rama = RAMA_POR_SKILL.get(sid)
        if rama and tabla.get(rama):
            return tabla[rama][:3]
    return []


KIND_HECHIZO = 9


def otorgar_hechizos(entity_id: int, numeros) -> bytes:
    """0x001D: el mensaje que pone los hechizos en la barra F1..F3.

    El 0x000D de arriba solo escribe "Learn Basic Attack I" en el chat; los
    iconos no aparecen hasta que llega esto. Medido en
    logs/proxy/mundo_103243_666191_s2c.bin offset 36709:

        22 00 1d 00 | 64 00 00 00 | 03 | 09 59 02 00 00 01 00 00 00 | ...

        [LE32 entidad][U8 cantidad] y luego, por hechizo,
        [U8 kind=9][LE32 numero de magic.xml][LE32 nivel]
    """
    cuerpo = struct.pack('<IB', entity_id, len(numeros))
    for n in numeros:
        cuerpo += struct.pack('<BII', KIND_HECHIZO, n, 1)
    return struct.pack('<H', 0x001D) + cuerpo


def parsear_eleccion(cuerpo: bytes):
    """Los seis skill_id que manda el cliente al confirmar la clase."""
    return [b for b in cuerpo[:6] if b]


def aviso(texto: str, tipo: int = 7, msg_id: int = MSG_HABILIDAD) -> bytes:
    """Sub-mensaje 0x000D: el cartel de 'aprendiste X' / 'obtuviste X'.

    Formato sacado de la captura: [LE16 id][U8 tipo][nombre NUL][2 ceros].
    El tipo vale 7 en las habilidades y 0 en los items.

    Devuelve el sub-mensaje COMPLETO, con su opcode delante. Sin el, los
    dos primeros bytes del cuerpo (el id de mensaje, 333) se leian como
    si fueran el opcode y salia un 0x014D que no existe.
    """
    n = texto.encode('ascii', 'replace')
    return (struct.pack('<H', 0x000D)
            + struct.pack('<HB', msg_id, tipo) + n + bytes(3))


# Lo que el servidor entrega al elegir clase, leido del inventario capturado
# justo despues: dos Sabre en las ranuras 3 y 4, los guantes en la 5 y los
# zapatos en la 6. Antes de elegir solo estaban el oro y la prenda del cuerpo.
#
# El arma depende de la clase y aqui solo esta medida la de Swordsman. Para
# las demas hara falta otra captura; no se inventan.
# Arma inicial por habilidad de arma. Se cruza el nombre de la habilidad en
# setting/eng/skill.xml con la categoria del item Freshman correspondiente en
# item.xml, que son los que el juego entrega al elegir clase:
#
#     19826 FreshmanSabre         刀    <- Sword   (9)
#     19832 FreshmanStick         錘    <- Axe     (10)
#     19838 FreshmanSpear         槍    <- Spear   (11)
#     19820 FreshmanRound Shield  盾    <- Shield  (14)
#     19850 FreshmanWalking Stick 杖    <- Staff Hit (8)
#     19844 FreshmanCatapult      彈弓  <- Longbow (17)
#     19856 FreshmanSharp Knife   影刃  <- Mantle  (32)
#     19814 FreshmanCask          機甲  <- Mechanism (24)
#
# El emparejamiento sale de los nombres, no de una captura. Lo unico medido es
# lo del Swordsman, y ahi el servidor privado entrego DOS armas (ranuras 3 y 4)
# y ademas dio el item 10 "Sabre" en vez del 19826 "FreshmanSabre". Se usan los
# Freshman porque son los que corresponden al juego; si el privado entrega
# otros es cosa suya.
# Medido de AngelWar (mundo_163130_471128): Swordsman recibe dos FreshmanSabre (item 10)
# en ranuras 3 y 4.
ARMA_POR_SKILL = {
    8: 19850, 9: 10, 10: 19832, 11: 19838,
    14: 19820, 17: 19844, 24: 19814, 32: 19856,
}
# Con que mano se empuna. Las reglas salen de lo poco medido y de como
# funcionan las clases en el juego:
#
#   - quien lleva Shield (14) va con arma en la derecha y escudo en la
#     izquierda: es el Protector, y el personaje de nivel 42 capturado lo
#     confirma (Sword, Axe, Grapple, Shield, Reserve, Garment -> Protector)
#   - el Swordsman va con dos armas iguales: medido, el servidor privado le
#     entrego DOS Sabre, en las ranuras 3 y 4
#   - el resto, una sola arma en la derecha
SKILL_ESCUDO = 14
ESCUDO = 19820                     # FreshmanRound Shield
DOS_ARMAS = {9, 10, 32}            # Sword (9), Axe/Hammer (10 - Warrior), Mantle (32 - Shadowblade): armas dobles
# Las clases magicas (Priest, Summoner, Wizard, Magician) no tienen habilidad
# de arma cuerpo a cuerpo, pero llevan baston. Si entre las seis hay alguna
# habilidad de magia y ninguna de arma, se les da el baston.
SKILLS_MAGIA = {1, 2, 3, 4, 5, 6}
BASTON = 19850                     # FreshmanWalking Stick

# Guantes y zapatos NO van con la clase: el tutorial los entrega mas tarde,
# en el tramo en que Angel Raphael dice "I will give you the uniform of the
# Angel Lyceum, you will need to learn how to put it on". Ver RECOMPENSAS.
ROPA_DE_CLASE = []

# Lo que entrega cada tramo del tutorial de Raphael, medido de la captura:
#   tramo 1  los guantes y los zapatos, para aprender a equiparse
#   tramo 2  diez monedas, para comprar el examen al Angel Aide
# Ya no se usa: con el tutorial de dos pasos, lo que se entrega sale de
# premio_final(), que depende de las habilidades elegidas.
RECOMPENSAS = {}

# El examen que Angel Aide vende por 10 monedas. En item.xml el 1386 es
# "Newbie Physical Examination File" y su precio es justo 10, que es lo que
# Raphael entrega en el tramo anterior.
ITEM_EXAMEN = 1386
PRECIO_EXAMEN = 10
ENTIDAD_TIENDA = 21        # Angel Aide
# Angel Raphael no deja pasar del tramo 2 al 3 sin el examen en la mochila.
# Que hace falta para pasar a cada etapa. La 1 pide haber elegido clase: sin
# esto, al cerrar el primer dialogo el tutorial avanzaba igual y entregaba los
# guantes y los zapatos antes de que el jugador eligiera nada, todo de una vez.
REQUISITO_ETAPA = {}
ETAPA_PIDE_CLASE = 1

# class_id del slot en el bloque de cuenta.
# setting/eng/class.xml: id="7" name="Swordsman"
CLASE_POR_SKILL = {9: 7}


def regalo(ids):
    """[(ranura, item_id)] que se entregan al elegir clase.

    ids: las seis habilidades que mando el cliente. El arma sale de la
    primera que sea de arma; si no hay ninguna (las clases de produccion no
    la tienen), solo se dan los guantes y los zapatos.
    """
    # El escudo no cuenta como arma principal: si lo lleva, va en la izquierda.
    principal = next((i for i in ids
                      if i in ARMA_POR_SKILL and i != SKILL_ESCUDO), None)
    if principal is None and any(i in SKILLS_MAGIA for i in ids):
        arma, principal = BASTON, 8
    else:
        arma = ARMA_POR_SKILL.get(principal)
    salida = []
    if arma is not None:
        salida.append((3, arma))
    if SKILL_ESCUDO in ids:
        salida.append((4, ESCUDO))
    elif arma is not None and principal in DOS_ARMAS:
        salida.append((4, arma))
    elif principal == 17:
        salida.append((4, 458))    # Wooden Arrow
    return salida


def class_id(skill_principal: int):
    return CLASE_POR_SKILL.get(skill_principal)


# --------------------------------------------------------------- 0x001C
# El arbol de habilidades. Sin el, el panel de habilidades del cliente sale
# lleno de interrogantes: no es que falten las elegidas, es que no conoce
# ninguna de las otras treinta.
#
#     +0    504 bytes en cero
#     +504  36 registros de 14 bytes, uno por habilidad
#
# Cada registro:
#     +0   U8  skill_id
#     +1   U8  nivel
#     +3   U8  disponible (1)
#     +9   U8  categoria: la pestana del panel (Mana, Combat, Shoot,
#              Mining, Craft)
#     +13  U8  orden: 1..6 en las seis elegidas, 0 en el resto
#
# Las seis elegidas van primero y el resto detras, como en la captura.
ARBOL = pathlib.Path(__file__).parent / 'plantillas' / 'arbol_skills.json'
_ARBOL = None


def _arbol():
    global _ARBOL
    if _ARBOL is None:
        import json
        d = json.loads(ARBOL.read_text(encoding='utf-8'))
        _ARBOL = {
            'cabecera': bytes.fromhex(d['cabecera']),
            # {skill_id: registro} para poder reordenarlos
            'regs': {bytes.fromhex(r)[0]: bytearray(bytes.fromhex(r))
                     for r in d['registros']},
        }
    return _ARBOL


def arbol(ids) -> bytes:
    """Sub-mensaje 0x001C con las 36 habilidades, nivel real y las seis elegidas marcadas."""
    a = _arbol()
    niveles = {}
    lista_ids = []
    for item in ids:
        if isinstance(item, (tuple, list)):
            sid = item[0]
            niveles[sid] = item[1] if len(item) > 1 else 1
            lista_ids.append(sid)
        else:
            niveles[item] = 1
            lista_ids.append(item)
    elegidas = [i for i in lista_ids if i in a['regs']]
    resto = [i for i in sorted(a['regs']) if i not in elegidas]
    salida = bytearray(a['cabecera'])
    for puesto, sid in enumerate(elegidas + resto):
        r = bytearray(a['regs'][sid])
        r[1] = max(1, min(100, niveles.get(sid, 1)))
        r[13] = puesto + 1 if puesto < len(elegidas) else 0
        salida += r
    return struct.pack('<H', 0x001C) + bytes(salida)



# --------------------------------------------------------------- tienda
# La ventana de tienda la abre el CLIENTE por su cuenta: en la captura, entre
# el dialogo con el Shopkeeper y la compra no viaja ni un mensaje. El cliente
# sabe que vende cada NPC (la tabla shop de content.db tiene 226 tiendas) y
# arma la lista solo. El servidor solo tiene que atender la compra:
#
#     C -> S  0x0027  [LE32 tienda][LE32 item_id][LE32 cantidad]
#     S -> C  0x001B  descuenta el oro
#     S -> C  0x000D  "N Gold"     id de mensaje 500 = pagaste
#     S -> C  0x000D  nombre       id de mensaje 492 = obtuviste
#     S -> C  0x001B  entrega el item
#     S -> C  0x0035  [LE32 item_id][LE32 cantidad]   confirmacion
#
# Medido comprando unos Gathering Gloves (item 63, precio 1 en item.xml) al
# Shopkeeper del Lyceum.
MSG_PAGO = 500


def parsear_compra(cuerpo: bytes):
    """(item_id, cantidad) del 0x0027, o None si no se entiende."""
    if len(cuerpo) < 12:
        return None
    _tienda, item_id, cantidad = struct.unpack_from('<III', cuerpo, 0)
    if not item_id or not cantidad:
        return None
    return item_id, cantidad


# --------------------------------------------------- cambio de mapa
# Medido al terminar el tutorial en el servidor privado:
#
#     S -> C  0x000C  [LE32 stage_id][24 bytes en cero]   "cambia a este mapa"
#     C -> S  0x0009  vacio                               "listo, mandamelo"
#     S -> C  la secuencia de entrada entera otra vez, con la ficha ya en el
#             mapa nuevo, y despues un 0x0003 colocando al jugador
#
# En la captura el 0x000C llevaba 0x39 = 57, que es el Fighting Palace, y el
# cliente respondio con el 0x0009 y recibio de nuevo 0x0014, 0x0002, 0x0064,
# 0x0155 y todo lo demas.
STAGE_LYCEUM = 41          # "Angel Lyceum" en stage.xml
STAGE_FIGHTING = 57        # "Fighting Palace", el del tutorial de combate
# Tile de llegada. NO esta medido para el Lyceum: en la captura solo se vio el
# del Fighting Palace, (39, 205). Se usa el centro de la zona jugable y se
# puede cambiar con AO_TILE_LYCEUM.
# MEDIDO, y por fin del sitio correcto: setting/eng/jumpmap.xml da el tile de
# llegada de cada mapa, y el del Angel Lyceum es (152,74). Antes se puso
# (100,100) a ojo y despues (131,87), que era el tile del Shopkeeper sacado de
# una captura. El dato estaba en el cliente todo el tiempo.
TILE_LYCEUM = tuple(int(x) for x in
                    __import__('os').environ.get('AO_TILE_LYCEUM', '152,74').split(','))


def cambiar_mapa(stage_id: int) -> bytes:
    """Sub-mensaje 0x000C: le dice al cliente que se mude de mapa."""
    return struct.pack('<HI', 0x000C, stage_id) + bytes(24)


# ------------------------------------------- tutorial customizado
# ESTO NO ES COMO EL JUEGO ORIGINAL. En el privado el tutorial son cuatro
# conversaciones con Angel Raphael, mas una compra al Angel Aide, y termina en
# el Fighting Palace. Aqui se acorto a dos pasos a pedido del jugador:
#
#     1  elegir clase   -> las seis habilidades y el arma
#     2  volver a hablar -> lo que falta del set de Student, las cajas de la
#                           clase, y derecho al Angel Lyceum
#
# Las tres cajas de clase salen de item.xml y vienen en tres familias, una por
# tipo de personaje, con un nivel minimo cada una:
#
#     Guerrero          1948 (nv5)  1949 (nv10)  1951 (nv25)
#     Mago              1952 (nv5)  1953 (nv10)  1955 (nv25)
#     Arquero/Productor 1944 (nv5)  1945 (nv10)  1947 (nv25)
#
# Y las Growth Box van de diez en diez niveles, de la 20103 (nivel 1) a la
# 20113 (nivel 100). Se entrega la primera.
CAJAS_GUERRERO = [1948, 1949, 1951]
CAJAS_MAGO = [1952, 1953, 1955]
CAJAS_ARQUERO = [1944, 1945, 1947]
GROWTH_BOX = 20103
SKILLS_ARQUERO = {17, 18, 19}          # arco y punteria
SKILLS_PRODUCCION = set(range(20, 32))  # recoleccion y oficios


def cajas_de(ids):
    """Las tres cajas que le tocan a esas habilidades."""
    if any(i in SKILLS_MAGIA for i in ids):
        return list(CAJAS_MAGO)
    if any(i in SKILLS_ARQUERO or i in SKILLS_PRODUCCION for i in ids):
        return list(CAJAS_ARQUERO)
    return list(CAJAS_GUERRERO)


def premio_final(ids):
    """[(ranura, item_id)] del segundo y ultimo paso del tutorial.

    Los zapatos y los guantes van a sus ranuras de equipo; las cajas, a la
    mochila, empezando en la 20.
    """
    salida = [(5, 28), (6, 30)]
    for k, caja in enumerate(cajas_de(ids) + [GROWTH_BOX]):
        salida.append((20 + k, caja))
    return salida
