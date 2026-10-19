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
    import json
    _SKILLS = {}
    f_json = pathlib.Path(__file__).parent / 'plantillas' / 'client_tables.json'
    if f_json.exists():
        try:
            raw = json.loads(f_json.read_text(encoding='utf-8'))
            for k, v in (raw.get('skill_names') or {}).items():
                _SKILLS[int(k)] = v
            if _SKILLS:
                return _SKILLS
        except Exception:
            pass
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
# Nombre en ingles de cada rama, el que el cliente enseña al equipar o
# descargar una. Los numeros son los mismos que usa el servidor real: en la
# captura, cambiar con 0x002F contenedor 10 manda "Chaos" con el 3 y
# "Meditate" con el 6.
NOMBRE_RAMA = {
    1: 'Life', 2: 'Wraith', 3: 'Chaos', 4: 'Earth', 5: 'Curse',
    6: 'Meditate', 7: 'Hit', 8: 'Staff Hit', 9: 'Sword', 10: 'Axe',
    11: 'Spear', 12: 'Enhance', 13: 'Grapple', 14: 'Shield', 15: 'Reserve',
    16: 'Finesse', 17: 'Longbow', 18: 'Snipe', 19: 'Eagle Eye',
    20: 'Collect', 21: 'Fishing', 22: 'Dig', 23: 'Lumber',
    24: 'Mechanism', 25: 'Drive', 26: 'Weapon', 27: 'Armor',
    28: 'Sew', 29: 'Technics', 30: 'Alchemy', 31: 'Cooking',
    32: 'Mantle', 33: 'Garment', 34: 'Vestment',
    35: 'Avatar', 36: 'Assault',
}


def nombre_de_rama(sid: int) -> str:
    return NOMBRE_RAMA.get(int(sid), 'Skill %d' % sid)


_HECHIZOS = None


def _cargar_hechizos():
    """magic.xml: rama -> [(numero, nombre)] de los hechizos de nivel 1."""
    global _HECHIZOS
    if _HECHIZOS is not None:
        return _HECHIZOS
    import json
    _HECHIZOS = {}
    f_json = pathlib.Path(__file__).parent / 'plantillas' / 'client_tables.json'
    if f_json.exists():
        try:
            raw = json.loads(f_json.read_text(encoding='utf-8'))
            for rama, lst in (raw.get('hechizos_nivel_1') or {}).items():
                _HECHIZOS[rama] = [(int(x[0]), str(x[1])) for x in lst]
            if _HECHIZOS:
                return _HECHIZOS
        except Exception:
            pass
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


MSG_EXP = 501            # "Obtain <n> Exp."
MSG_SKILL_EXP = 503        # "<skill> has obtained <n> Exp."
MSG_SKILL_SUBE = 508       # "The level of the spell <skill> has been upgraded."


def aviso_doble(msg_id: int, s1: str, s2: str = '', tipo: int = 2) -> bytes:
    """0x000D con DOS cadenas, que es como llega la skill exp.

    Medido: 0d 00 | f7 01 | 02 | "Sword" | "100" | 00 00
    Antes la skill exp se mandaba como 0x000B tipo 4 con el numero de la
    habilidad, y el cliente lo dibujaba como un numero flotante sobre el
    personaje: ese era el "9" verde que aparecia junto al dano.
    """
    nul = bytes([0])
    return (struct.pack('<HHB', 0x000D, msg_id, tipo)
            + s1.encode('latin-1', 'replace') + nul
            + s2.encode('latin-1', 'replace') + nul
            + nul)


def hechizos_iniciales(skill_ids):
    """Devuelve [(numero, nombre)] de todos los hechizos de nivel 1 de las ramas elegidas."""
    import skills
    return skills.hechizos_iniciales_de(skill_ids)


def hechizos_de_rama(sid: int):
    """Devuelve [(numero, nombre)] de los hechizos iniciales de una rama concreta."""
    import skills
    return skills.hechizos_de_rama(sid)


def hechizos_de_ramas_activas(skill_ids, solo_maximo: bool = True, **kwargs):
    """Hechizos actuales de esas ramas, leidos de la tabla magic."""
    import skills
    return skills.hechizos_de_ramas_activas(skill_ids, solo_maximo=solo_maximo, **kwargs)


def info_pergamino(item_id: int):
    """Consulta si un item es un pergamino de habilidad y que hechizo enseña."""
    import skills
    return skills.info_pergamino(item_id)


def skill_de_magia(magic_id: int):
    """Devuelve el skill_id de la rama a la que pertenece este hechizo/habilidad."""
    import skills
    return skills.skill_de_magia(magic_id)


KIND_HECHIZO = 9



def otorgar_hechizos(entity_id: int, numeros) -> bytes:
    """0x001D: el mensaje que pone los hechizos en la barra F1..F3.

    El 0x000D de arriba solo escribe "Learn Basic Attack I" en el chat; los
    iconos no aparecen hasta que llega esto. Medido en
    logs/proxy/mundo_103243_666191_s2c.bin offset 36709:

        22 00 1d 00 | 64 00 00 00 | 03 | 09 59 02 00 00 01 00 00 00 | ...

        [LE32 entidad][U8 cantidad] y luego, por hechizo,
        [U8 kind=9][LE32 numero de magic.xml][LE32 nivel]

    Como la cantidad es un U8, en un mensaje no caben mas de 255, asi que
    con mas hechizos hacen falta VARIOS mensajes. Y TIENEN QUE IR SUELTOS:
    esto devuelve una LISTA, no un churro de bytes.

    Antes se devolvian pegados, y ahi se perdian igual. Cada cosa que se le
    pasa a ses.enviar() lleva delante su propio LE16 de largo
    (proto/framing.pack_submessages), asi que los dos mensajes pegados
    viajaban como UNO SOLO: el cliente (sub_5F0EF0, 0x5F0EF0) lee la
    cantidad del byte +6, procesa esos 255 y TIRA lo que quede detras
    dentro del mismo sub-mensaje. Los 29 ultimos no llegaban nunca.

    Como ademas la lista venia de un set(), cuales eran esos 29 cambiaba de
    sesion en sesion: por eso Gnash se perdia, volvia y se volvia a perder.
    """
    import skills
    fuera = []
    numeros = list(numeros)
    for i in range(0, max(1, len(numeros)), 255):
        trozo = numeros[i:i + 255]
        if not trozo:
            break
        cuerpo = struct.pack('<IB', entity_id, len(trozo))
        for n in trozo:
            if isinstance(n, (tuple, list)):
                mid, mlv = n[0], n[1]
            else:
                mid = n
                mlv = skills.nivel_de_magia(mid)
            cuerpo += struct.pack('<BII', KIND_HECHIZO, mid, mlv)
        fuera.append(struct.pack('<H', 0x001D) + cuerpo)
    return fuera


def parsear_eleccion(cuerpo: bytes):
    """Los seis skill_id que manda el cliente al confirmar la clase."""
    return [b for b in cuerpo[:6] if b]


MSG_QUEST = 510            # "You accept the quest [%s]"

# EL AVISO DE TEXTO LIBRE. El 0x000D no manda texto: manda un numero de
# cadena del cliente y los trozos que rellenan sus %s. El 510 es la frase
# de ACEPTAR UNA MISION, asi que mandar cualquier otra cosa con el sale
# envuelto en ella, y asi es como el jugador acabo leyendo
#
#     You accept the quest [Quest [The Reivers]: Missing items (0/1)]
#
# cuatro veces seguidas, una por cada intento de entregar sin los objetos.
# El 732 es '%s' a secas, que es lo que hace falta para un aviso propio.
# Sale de setting/eng/string.xml, que es la tabla de los numeros bajos; la
# de msg.xml empieza en el 5001 y es otra cosa.
MSG_TEXTO = 732            # '%s'

# Las cuatro misiones de registro, una por ciudad, y la de elegir pais.
QUEST_ELEGIR_PAIS = 103
QUEST_POR_FACCION = {
    'Aurora': 127,
    'Dark City': 128,
    'Iron Castle': 129,
    'Breeze Woods': 130,
}


_NOMBRES_QUEST = None


_NOMBRES_MAPA = None


def nombre_de_mapa(stage: int) -> str:
    """El nombre del mapa, de la tabla stage de los datos del cliente."""
    global _NOMBRES_MAPA
    if _NOMBRES_MAPA is None:
        import sqlite3
        _NOMBRES_MAPA = {}
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            try:
                con = sqlite3.connect(db)
                con.text_factory = str
                for fila in con.execute('select * from stage'):
                    try:
                        _NOMBRES_MAPA[int(fila[0])] = str(fila[1] or '')
                    except (TypeError, ValueError):
                        continue
                con.close()
            except Exception:
                pass
    return _NOMBRES_MAPA.get(int(stage or 0), '')


def nombre_de_quest(qid: int) -> str:
    """El nombre de la mision, de la tabla quest de los datos del cliente."""
    global _NOMBRES_QUEST
    if _NOMBRES_QUEST is None:
        import sqlite3
        _NOMBRES_QUEST = {}
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            try:
                con = sqlite3.connect(db)
                con.text_factory = str
                # La columna 1 es el nombre. Se lee por POSICION porque su
                # nombre quedo ilegible al montar la base de datos.
                for fila in con.execute('select * from quest'):
                    i, n = fila[0], fila[1]
                    try:
                        _NOMBRES_QUEST[int(i)] = str(n or '')
                    except (TypeError, ValueError):
                        continue
                con.close()
            except Exception:
                pass
    return _NOMBRES_QUEST.get(int(qid), 'Quest %d' % qid)


def mision(char_id: int, quest_id: int, paso: int = 0, sello: int = 0) -> bytes:
    """0x0022: otorga o actualiza UNA mision.

    Medido en la captura del Graduation Palace:
        01000000 482a1600 6700 00 00000000 00000000 482a01
    es decir [u32 n=1][u32 personaje][u16 quest][u8 paso][u32 sello]
    [u32 0][u16 los 16 bits bajos del personaje][u8 1]. Al completarla
    llega la misma con el paso en 1 y el sello con la hora.
    """
    return (struct.pack('<HIIHBII', 0x0022, 1, char_id, quest_id, paso,
                        sello, 0)
            + struct.pack('<HB', char_id & 0xFFFF, 1))


def borrar_mision(char_id: int, quest_id: int) -> bytes:
    """0x0022 con modo 2 (byte 17 = 2): elimina UNA mision del registro del cliente."""
    return (struct.pack('<HIIHBII', 0x0022, 1, char_id, quest_id, 0,
                        0, 0)
            + struct.pack('<HB', char_id & 0xFFFF, 2))


def paquete_quest_log(char_id: int, quests: list) -> bytes:
    """0x0021 QUEST_LOG: sincroniza la lista completa de misiones del personaje."""
    if not quests:
        return struct.pack('<HI', 0x0021, 0)
    import misiones as _mis
    recs = []
    for q, s in quests:
        comp = _mis.mision_completada_raw(q, s)
        paso_red = _mis.total_pasos_mision(q) if comp else max(0, s - 1)
        recs.append(struct.pack('<IHB11s', char_id, q, paso_red, b'\x00' * 11))
    return struct.pack('<HI', 0x0021, len(recs)) + b''.join(recs)


def aviso(texto: str, tipo: int = 7, msg_id: int = MSG_TEXTO) -> bytes:
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


def chat_publico(entity_id: int, canal: int, nombre: str, texto: str) -> bytes:
    """S2C 0x0128 para los canales que usan una linea normal de chat."""
    if int(canal) not in (2, 10):
        raise ValueError('canal de chat no soportado')
    autor = str(nombre or '').encode('latin-1', 'replace')[:16].ljust(17, b'\x00')
    mensaje = str(texto or '').encode('latin-1', 'replace')[:1000] + b'\x00'
    return struct.pack('<HIB17s', 0x0128, int(entity_id), int(canal), autor) + mensaje


def chat_broadcast(entity_id: int, nombre: str, texto: str) -> bytes:
    """Broadcast/Public: ``[public]name>text`` (style 1, string 181)."""
    return chat_publico(entity_id, 2, nombre, texto)


def chat_super_broadcast(entity_id: int, nombre: str, texto: str,
                         portrait_selector: int = 0) -> bytes:
    """Super Broadcast: banda grande con retrato, autor y mensaje.

    La rama 11 quita el primer byte y lo conserva como selector del retrato.
    Los paquetes oficiales usan ``'0'`` o ``'1'``; no debe fijarse siempre a
    uno porque eso dibuja el avatar equivocado.
    """
    autor = str(nombre or '').encode('latin-1', 'replace')[:16].ljust(17, b'\x00')
    selector = b'1' if int(portrait_selector or 0) else b'0'
    mensaje = selector + str(texto or '').encode('latin-1', 'replace')[:999] + b'\x00'
    return struct.pack('<HIB17s', 0x0128, int(entity_id), 11, autor) + mensaje


def chat_trade(entity_id: int, nombre: str, texto: str) -> bytes:
    """Trade: ``[Trade]name>text`` (style 2, string 198)."""
    return chat_publico(entity_id, 10, nombre, texto)


def chat_privado(entity_id: int, canal: int, nombre: str, texto: str) -> bytes:
    """S2C 0x0126 para League=4, Team=5 y Marriage=14."""
    if int(canal) not in (4, 5, 14):
        raise ValueError('canal privado no soportado')
    autor = str(nombre or '').encode('latin-1', 'replace')[:16].ljust(17, b'\x00')
    mensaje = str(texto or '').encode('latin-1', 'replace')[:1000] + b'\x00'
    return struct.pack('<HIBI17s', 0x0126, int(entity_id), int(canal), 0, autor) + mensaje


# CANAL 4 = EQUIPO y 5 = LIGA. Sacado del cliente con REA (19/10/2026): el
# envio (0x6366a0) manda el 4 desde la pestana de equipo -- si no hay grupo
# avisa "You are not a member of any teams." -- y el 5 desde la de liga --
# "You are not in any league now." --, y al recibir (0x5f3c40 -> 0x632e70)
# el 4 sale con la etiqueta de equipo y el 5 con la de liga. Estaban al reves.
CANAL_EQUIPO, CANAL_LIGA, CANAL_MATRIMONIO = 4, 5, 14


def chat_team(entity_id: int, nombre: str, texto: str) -> bytes:
    return chat_privado(entity_id, CANAL_EQUIPO, nombre, texto)


def chat_league(entity_id: int, nombre: str, texto: str) -> bytes:
    return chat_privado(entity_id, CANAL_LIGA, nombre, texto)


def chat_marriage(entity_id: int, nombre: str, texto: str) -> bytes:
    return chat_privado(entity_id, 14, nombre, texto)


def chat_battle(nombre: str, texto: str, label_id: int = 2214) -> bytes:
    """S2C 0x0139 para el canal Battle / Jabaly (sub_5F3CE0, string 2214)."""
    autor = str(nombre or '').encode('latin-1', 'replace')[:16].ljust(17, b'\x00')
    mensaje = str(texto or '').encode('latin-1', 'replace')[:1000] + b'\x00'
    return struct.pack('<H17sI', 0x0139, autor, int(label_id)) + mensaje


def chat_whisper(emisor: str, receptor: str, texto: str, err_code: int = 0) -> bytes:
    """S2C 0x0127 para susurros privados (sub_5F36F0)."""
    src = str(emisor or '').encode('latin-1', 'replace')[:16].ljust(17, b'\x00')
    dst = str(receptor or '').encode('latin-1', 'replace')[:16].ljust(17, b'\x00')
    mensaje = str(texto or '').encode('latin-1', 'replace')[:1000] + b'\x00'
    return struct.pack('<HIH17s17sH', 0x0127, 0, int(err_code), src, dst, 0) + mensaje


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
DOS_ARMAS = {9, 10}                # Sword (9), Axe/Hammer (10 - Warrior): armas dobles. Shadowblade (32) lleva UNA, en la mano derecha
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


def class_id(skills_input):
    import skills
    if isinstance(skills_input, (list, tuple, set)):
        return skills.calcular_class_id(skills_input)
    return skills.calcular_class_id([skills_input])


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
#
# EL ORDEN DE LOS REGISTROS IMPORTA, y mucho. El panel de personaje tiene
# NUEVE filas de verdad (wnd01.xml: las seis de siempre, 318..335, y las
# tres nuevas 27663..27671 con sus candados "Reach Supreme Lv"), pero el
# cliente NO dibuja el registro i en la fila i. Dibuja en la fila
#
#     fila = i + sub_654F90(i)
#
# y ese desplazamiento sale de QUE RAMA es, no de donde esta (0x646370 y
# 0x654F90 del binario):
#
#   - una rama cualquiera con id > 11 baja una fila por cada una de estas
#     que el personaje lleve: la 30 (Alchemy) si su id esta entre 12 y 29,
#     y la 35 (Avatar) y la 36 (Assault) si su id esta entre 20 y 34;
#   - las ramas 30, 35 y 36 no se quedan donde estan: se meten en la fila
#     de la PRIMERA rama de su grupo y empujan al resto hacia abajo.
#
# O sea que el cliente da por hecho que los registros vienen ORDENADOS POR
# ID con la 30, la 35 y la 36 al final, que es como venian en la captura.
# Mandandolos en el orden en que el jugador los eligio, dos ramas caian en
# la misma fila y otra se quedaba sin nadie: por eso Vestment salia dos
# veces al principio y despues la fila sexta se quedo en blanco y al
# 100,00%. El paquete estaba bien; lo que estaba mal era el orden.
#
# ordenar_para_el_panel() deja el orden que el cliente espera y ademas lo
# COMPRUEBA emulando su cuenta, que es lo unico que de verdad vale.
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


# Experiencia que pide cada nivel de habilidad, del 1 al 10. Medido en los
# 98 arboles capturados: el offset 9 del registro vale 3 en nivel 1, 12 en el
# 4, 16 en el 5, 30 en el 6, 40 en el 7, 55 en el 8, 70 en el 9 y 85 en el 10.
# Comprobacion: un registro con exp=2 y req=3 da 66.67%, y el Grapple al
# 62.50% de la captura es 5 de 8.
# Como sube cada una de las 36 habilidades. Sale de setting/eng/skill.xml:
# la descripcion lo dice en ingles y los atributos chinos lo marcan
# (採藥 recolectar, 釣魚 pescar, 挖礦 minar, 伐木 talar, 製作武器 armas,
# 製作防具 armaduras, 裁縫 costura, 工藝 artesania, 烹飪 cocina,
# 近程攻擊 cuerpo a cuerpo, 遠程攻擊 a distancia).
#
# Antes se le daba experiencia a todas las habilidades en cada golpe, asi que
# un espadachin subia Cook y Fishing pegandole a un Slarm.
ACCION_POR_SKILL = {
    # Magia
    1: 'magia', 2: 'magia', 3: 'magia', 4: 'magia', 5: 'magia', 6: 'magia', 7: 'magia', 8: 'magia', 34: 'magia', 35: 'magia', 36: 'magia',
    # Armas melee
    9: 'melee', 10: 'melee', 11: 'melee', 32: 'melee', 14: 'melee',
    # Distancia
    17: 'distancia',
    # Recoleccion
    20: 'recolectar', 21: 'recolectar', 22: 'recolectar', 23: 'recolectar',
    # Produccion
    26: 'producir', 27: 'producir', 28: 'producir', 29: 'producir', 30: 'producir', 31: 'producir',
}

# Lo que sube SIEMPRE con cada actividad, ademas de la habilidad concreta.
# Definido por el usuario a partir de como funciona el juego:
#
#   melee (espada, hacha, lanza, arco, shadowblade) -> Enhance, Grapple,
#       Reserve, Finesse y la armadura (Garment o Mantle, la que se lleve)
#   arco -> ademas Snipe y Eagle Eye
#   espada o hacha -> ademas Shield
#   magia -> Curse, Hit, Staff Hit, Meditate y Vestment
#   recolectar -> ademas Drive y Mechanism
#
# Como despues se filtra por las habilidades que el personaje REALMENTE tiene,
# poner Garment y Mantle juntos no hace que suban las dos: sube la que lleve.
PASIVAS_POR_ACCION = {
    'melee': [16, 13, 12, 15, 14, 35, 36, 33, 32],       # Finesse, Grapple, Enhance, Reserve, Shield, Avatar, Assault, Garment, Mantle
    'distancia': [17, 18, 19, 32],                        # Bow, Snipe, Eagle Eye, Mantle
    'magia': [1, 2, 3, 4, 5, 6, 7, 8, 34, 35, 36],       # Life, Wraith, Chaos, Earth, Curse, Meditate, Hit, Staff Hit, Vestment, Avatar, Assault
    'recolectar': [20, 21, 22, 23, 24, 25, 32],           # Collect, Fish, Dig, Lumber, Mechanism, Drive, Mantle
    'producir': [26, 27, 28, 29, 30, 31, 24, 25, 32],     # Weapon, Armor, Sew, Technics, Alchemy, Cook, Mechanism, Drive, Mantle
}

# Que armas arrastran ademas otra habilidad al golpear.
EXTRA_POR_ARMA = {
    9: [14],            # espada -> Shield
    10: [14],           # hacha  -> Shield
    11: [14],           # lanza  -> Shield
    17: [18, 19, 32],   # arco   -> Snipe, Eagle Eye, Mantle
    8: [6, 34, 35, 36], # baston -> Meditate, Vestment, Avatar, Assault
}


# Categoria del arma (物品類別 de item.xml) -> numero de habilidad.
# Medido: el hacha Freshman (19832) es 錘, el escudo (19820) es 盾 y ademas
# trae 技能限制1="14", y el sable (19826) es 刀.
# Categorias tal como aparecen en item.xml, contadas sobre todo lo que lleva
# 右手裝備 o 左手裝備. Las que habia escritas a mano (弓, 弩, 矛, 匕首) no
# existen: el arco es 弓箭 y la daga 影刃, por eso el arco caia en el ataque
# por defecto.
SKILL_POR_CATEGORIA = {
    '劍': 9, '刀': 9,          # espada (226) y sable (167) -> Sword
    '斧': 10, '錘': 10,        # hacha (210) y martillo (178) -> Axe
    '槍': 11,                  # lanza (384) -> Spear
    '弓箭': 17, '彈弓': 17,    # arco (363) y tirachinas (21) -> Longbow
    '影刃': 32,                # hoja de sombra (331) -> Mantle / ShadowBlade
    '盾': 14,                  # escudo (267) -> Shield
    '杖': 8,                   # baston (386) -> Staff Hit
    '鐵鍬': 22,                # pala -> Dig
    '釣竿': 21,                # cana de pescar -> Fishing
}
_CAT_ITEM = None


def skill_de_item(item_id: int):
    """El numero de habilidad que entrena ese item equipado, o None.

    Primero mira 技能限制1 de item.xml, que en el escudo Freshman vale 14;
    si no lo trae, traduce su 物品類別. Antes se comparaba el item contra
    ARMA_POR_SKILL, que solo conoce las armas Freshman, y ademas se miraba
    una sola ranura: por eso un Protector con hacha y escudo no subia Shield.
    """
    global _CAT_ITEM
    if _CAT_ITEM is None:
        import sqlite3
        _CAT_ITEM = {}
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            try:
                con = sqlite3.connect(db)
                for tabla in ('item', 'item2', 'item3', 'item4', 'item5', 'item6', 'item7', 'item8', 'item9'):
                    try:
                        for iid, cat, lim in con.execute(
                                f'select id, 物品類別, 技能限制1 from {tabla}'):
                            try:
                                _CAT_ITEM[int(iid)] = (cat or '', lim or '')
                            except (TypeError, ValueError):
                                continue
                    except Exception:
                        pass
                con.close()
            except Exception:
                pass
    cat, lim = _CAT_ITEM.get(int(item_id or 0), ('', ''))
    try:
        if lim and 1 <= int(float(lim)) <= 36:
            return int(float(lim))
    except (TypeError, ValueError):
        pass
    return SKILL_POR_CATEGORIA.get(cat)


# Habilidades que corresponden a un arma de MANO. El escudo (14) no cuenta:
# llevar espada y escudo no es pelear con dos armas.
SKILLS_ARMA_MANO = {9, 10, 11, 17, 30, 8}


# Las dos ranuras de mano. La 3 es la principal y la 4 la secundaria: en
# cuentas.json un Protector tiene el arma en la 3 y el escudo en la 4.
RANURA_MANO_DER = 3
RANURA_MANO_IZQ = 4


def es_dos_manos(item_id) -> bool:
    """True si el arma ocupa las dos manos.

    En item.xml las de una mano traen 左手裝備="是" (se pueden empunar con la
    izquierda); las de dos manos NO. La lanza Freshman, por ejemplo, tiene
    右手裝備="是" y el campo izquierdo vacio. Un arma asi nunca es dual, por
    mas que el personaje tenga las dos manos ocupadas con ella.
    """
    global _MANOS_ITEM
    try:
        _MANOS_ITEM
    except NameError:
        _MANOS_ITEM = None
    if _MANOS_ITEM is None:
        import sqlite3
        _MANOS_ITEM = {}
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            try:
                con = sqlite3.connect(db)
                for tabla in ('item', 'item2', 'item3', 'item4', 'item5', 'item6', 'item7', 'item8', 'item9'):
                    try:
                        for iid, izq in con.execute(f'select id, 左手裝備 from {tabla}'):
                            try:
                                _MANOS_ITEM[int(iid)] = (izq == '是')
                            except (TypeError, ValueError):
                                continue
                    except Exception:
                        pass
                con.close()
            except Exception:
                pass
    if not item_id:
        return False
    if skill_de_item(item_id) == 32:      # 影刃: una mano, solo en la derecha
        return False
    return not _MANOS_ITEM.get(int(item_id), True)


_MANOS_ITEM = None


def lleva_duales(inventario) -> bool:
    """True solo si hay un ARMA DE MANO en cada mano.

    Se cuentan ARMAS, no habilidades. Contando habilidades fallaba por los
    dos lados: dos dagas iguales dan las dos la habilidad 9 y el conjunto las
    colapsaba en una (no detectaba duales), mientras que sable + stick da 9 y
    10 y las contaba como duales aunque una fuera un escudo o un objeto que
    no se empuna. Tampoco vale mirar solo si hay dos armas en el equipo: el
    escudo (盾) va en la mano izquierda y no es pelear con dos armas.
    """
    inv = inventario or {}
    manos = 0
    for ranura in (RANURA_MANO_DER, RANURA_MANO_IZQ):
        item_id = inv.get(ranura) or inv.get(str(ranura))
        if not item_id:
            continue
        if es_dos_manos(item_id):
            return False      # un arma a dos manos nunca es dual
        if skill_de_item(item_id) in SKILLS_ARMA_MANO:
            manos += 1
    return manos > 1


def skills_de_equipo(inventario):
    """Las habilidades de arma que entrena TODO lo equipado (ambas manos)."""
    salida = set()
    for ranura, item_id in (inventario or {}).items():
        if not isinstance(ranura, int) or ranura > 12:
            continue
        sid = skill_de_item(item_id)
        if sid:
            salida.add(sid)
    return salida


def skills_que_suben(accion: str, skills_arma=()):
    """Las habilidades que ganan experiencia con esa accion.

    `skills_arma` son las de lo equipado (puede haber varias: hacha y escudo).
    Se les suma lo que arrastre cada arma, por ejemplo Shield con espada o
    hacha, y Snipe con arco.
    """
    salida = set(PASIVAS_POR_ACCION.get(accion, []))
    salida |= {sid for sid, a in ACCION_POR_SKILL.items() if a == accion}
    for sid in (skills_arma or ()):
        salida.add(sid)
        salida.update(EXTRA_POR_ARMA.get(sid, []))
    return salida


EXP_POR_NIVEL_SKILL = [3, 6, 8, 12, 16, 30, 40, 55, 70, 85]


def exp_requerida_skill(nivel: int, sid: int = 1) -> int:
    import combate as _cb
    return _cb.exp_para_skill(nivel, sid)


# Las tres que el cliente trata aparte: Alchemy, Avatar y Assault.
RAMAS_AL_FINAL = (30, 35, 36)


def _fila_del_cliente(sids, i, llevadas):
    """Lo que devuelve sub_654F90 para el registro i, mas i.

    Copia literal de 0x654F90. `sids` son los ids de los nueve primeros
    registros del arbol y `llevadas` las ramas que tiene el personaje.
    """
    v9 = sids[i] if i < len(sids) else 0
    tope = len(sids)
    if not 0 < tope < 9:
        tope = 9
    if v9 == 30:
        for i2 in range(min(tope, len(sids))):
            if sids[i2] > 11:
                return i2
    elif v9 == 35:
        for j in range(min(tope, len(sids))):
            if sids[j] >= 20:
                return j + (1 if 30 in llevadas else 0)
    elif v9 == 36:
        for k in range(min(tope, len(sids))):
            if sids[k] >= 20:
                return (k + (1 if 30 in llevadas else 0)
                        + (1 if 35 in llevadas else 0))
    else:
        d = 0
        if v9 > 11:
            if v9 < 30 and 30 in llevadas:
                d = 1
            if 20 <= v9 < 35 and 35 in llevadas:
                d += 1
            if 20 <= v9 < 35 and 36 in llevadas:
                d += 1
        return i + d
    return i


def _filas_limpias(sids, llevadas, cuantas):
    """True si las `cuantas` elegidas caen en filas 0..cuantas-1 sin repetir."""
    filas = [_fila_del_cliente(sids, i, llevadas) for i in range(cuantas)]
    return sorted(filas) == list(range(cuantas)), filas


def ordenar_para_el_panel(elegidas, resto):
    """El orden que el cliente espera: por id, con 30, 35 y 36 al final.

    Devuelve (elegidas_ordenadas, filas) donde filas[k] es la fila de
    pantalla en la que el cliente va a dibujar la elegida k. Si el orden
    canonico no cuadra se prueban otros, porque una fila repetida deja a
    otra en blanco y eso es justo el bug que se quiere evitar.
    """
    llevadas = set(elegidas)
    normales = sorted(s for s in elegidas if s not in RAMAS_AL_FINAL)
    aparte = sorted(s for s in elegidas if s in RAMAS_AL_FINAL)
    n = len(elegidas)

    candidatos = [normales + aparte]
    if n != len(candidatos[0]):
        candidatos = [list(elegidas)]
    candidatos.append(sorted(elegidas))
    candidatos.append(list(elegidas))

    for cand in candidatos:
        sids = (cand + list(resto))[:9]
        ok, filas = _filas_limpias(sids, llevadas, n)
        if ok:
            return cand, filas

    # Ninguno de los de siempre sirve: se buscan a lo bruto. Son nueve como
    # mucho, y el resultado se queda en cache por combinacion de ramas.
    import itertools
    for cand in itertools.permutations(normales + aparte):
        sids = (list(cand) + list(resto))[:9]
        ok, filas = _filas_limpias(sids, llevadas, n)
        if ok:
            return list(cand), filas
    # Nada cuadra: se manda el canonico igual, que es el menos malo.
    cand = normales + aparte
    return cand, [_fila_del_cliente((cand + list(resto))[:9], i, llevadas)
                  for i in range(n)]


_CACHE_ORDEN = {}


def arbol(ids, banco=None) -> bytes:
    """Sub-mensaje 0x001C con las 36 habilidades, su nivel y su experiencia.

    Soporta banco de habilidades para recordar niveles entrenados en ramas no equipadas.
    """
    a = _arbol()
    niveles = {}
    lista_ids = []
    exps = {}

    if banco:
        for k, v in banco.items():
            sid_b = int(k)
            if isinstance(v, (tuple, list)):
                niveles[sid_b] = v[0]
                exps[sid_b] = v[1] if len(v) > 1 else 0
            else:
                niveles[sid_b] = int(v)
                exps[sid_b] = 0

    for item in ids:
        if isinstance(item, (tuple, list)):
            sid = item[0]
            niveles[sid] = item[1] if len(item) > 1 else 1
            exps[sid] = item[2] if len(item) > 2 else 0
            lista_ids.append(sid)
        else:
            niveles.setdefault(item, 1)
            lista_ids.append(item)
    elegidas = [i for i in lista_ids if i in a['regs']][:9]
    resto = [i for i in sorted(a['regs']) if i not in elegidas]

    # El orden que el cliente sabe leer, y la fila en la que va a dibujar
    # cada una. El campo de orden lleva LA FILA, no el puesto en la lista:
    # asi el candado de las filas 7, 8 y 9 (que solo se quita si el orden
    # llega a 6) nunca tapa a una rama que si esta puesta.
    clave = tuple(elegidas)
    if clave in _CACHE_ORDEN:
        elegidas, filas = _CACHE_ORDEN[clave]
    else:
        elegidas, filas = ordenar_para_el_panel(elegidas, resto)
        _CACHE_ORDEN[clave] = (elegidas, filas)

    salida = bytearray(a['cabecera'])
    for puesto, sid in enumerate(elegidas + resto):
        r = bytearray(a['regs'][sid])
        nv = max(1, min(500, niveles.get(sid, 1)))
        req = max(1, exp_requerida_skill(nv, sid))
        sexp = max(0, min(req, int(exps.get(sid, 0) or 0)))
        struct.pack_into('<H', r, 1, nv)
        struct.pack_into('<H', r, 3, nv)
        struct.pack_into('<I', r, 5, sexp & 0xFFFFFFFF)
        struct.pack_into('<I', r, 9, req & 0xFFFFFFFF)
        r[13] = (filas[puesto] + 1) if puesto < len(elegidas) else 0
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
