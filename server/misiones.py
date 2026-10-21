"""
Motor de misiones (Quest System) para Angels Online.
Carga datos desde server/plantillas/misiones_completas.json y coordina
la aceptacion, avance, cacerias, recolecciones, conversaciones,
guardado y entrega de recompensas para las 1,489 misiones del juego.
"""
import json
import logging
import pathlib
import re
import time
import struct

import clases as _cl
import cuentas
import combate as _cb

log = logging.getLogger('misiones')

RUTA_MISIONES_COMPLETAS = pathlib.Path(__file__).parent / 'plantillas' / 'misiones_completas.json'
RUTA_MISIONES_JSON = pathlib.Path(__file__).parent / 'plantillas' / 'misiones.json'

_DB = None
_MISIONES = None
_CACERIAS = None
_RECOLECCIONES = None
_NPC_INICIO = None
_NPC_PASOS = None
_REPETIBLES = None

# Mapeo de misiones clave de las 4 ciudades
QUEST_REGISTRO = {
    3: 127,    # Aurora City
    26: 128,   # Dark City
    38: 129,   # Iron Castle
    29: 130,   # Breeze Woods
}

QUEST_CONOCER = {
    3: 133,    # Knowing Aurora City (Explorer Lim)
    26: 134,   # Knowing Dark City (Risker Zalfer)
    38: 135,   # Knowing Iron Castle (Pioneer Ocadon)
    29: 136,   # Knowing Breeze Woods (Explorer Gulin)
}

QUEST_NIVEL = {
    3: 137,    # Reaching higher level (Aurora)
    26: 138,   # Reaching higher level (Dark City)
    38: 139,   # Reaching higher level (Iron Castle)
    29: 140,   # Reaching higher level (Breeze Woods)
}

# NPCs guias de ciudad (entity_id exacto en los mapas 3, 26, 38, 29)
GUIAS_CIUDAD = {
    121633: (3,  133, 'Explorer Lim',    20010),
    121914: (26, 134, 'Risker Zalfer',   30010),
    122110: (38, 135, 'Pioneer Ocadon',  40010),
    121967: (29, 136, 'Explorer Gulin',  50010),
}

# Paradise Angels en las 4 ciudades (dan inicio a la cadena de Eden, Quest 142)
PARADISE_ANGELS = {
    121671: 3,   # Aurora City
    121905: 26,  # Dark City
    122154: 38,  # Iron Castle
    121990: 29,  # Breeze Woods
}

QUEST_EDEN_NEEDS_HELP = 142
QUEST_FINAL_LINE = 143

# Mapeo de misiones con objetivos de caceria clasicos (compatibilidad)
OBJETIVOS_CACERIA = {
    (142, 2): {
        'monstruos': (7007, 7008),  # Young Witch, Crystal Envoy
        'cantidad': 100,
        'siguiente_paso': 3,
        'nombre_objetivo': 'Young Witch / Crystal Envoy',
        'aviso_fin': 'Quest [Eden Needs Help]: Report to Blocks Envoy in Mushroom Village.',
    },
    (143, 1): {
        'monstruos': (7016, 7017),  # Fire Ball Baby, Flower Thorn Baby
        'cantidad': 100,
        'siguiente_paso': 2,
        'nombre_objetivo': 'Fire Ball Baby / Flower Thorn Baby',
        'aviso_fin': 'Quest [The Final Line]: Report to Guerrilla Leader Mola.',
    },
    (143, 3): {
        'monstruos': (7020,),        # Dog Fighter
        'cantidad': 100,
        'siguiente_paso': 4,
        'nombre_objetivo': 'Dog Fighter',
        'aviso_fin': 'Quest [The Final Line]: Report to Guerrilla Leader Mola.',
    },
    (115, 1): {
        'monstruos': ('slarm',),
        'monstruo_ids': (19,),
        'cantidad': 10,
        'token_id': 1400,
        'siguiente_paso': 2,
        'nombre_objetivo': 'Slarm',
        'aviso_fin': 'Quest [Junior Lesson]: Report to Battle Professor.',
    },
    (116, 1): {
        'monstruos': ('water elf',),
        'monstruo_ids': (3,),
        'cantidad': 15,
        'token_id': 1401,
        'siguiente_paso': 2,
        'nombre_objetivo': 'Water Elf',
        'aviso_fin': 'Quest [Mid-Level Lesson]: Report to Battle Professor.',
    },
    (117, 1): {
        'monstruos': ('earth elf',),
        'monstruo_ids': (4,),
        'cantidad': 15,
        'token_id': 1402,
        'siguiente_paso': 2,
        'nombre_objetivo': 'Earth Elf',
        'aviso_fin': 'Quest [High-level Lesson]: Report to Battle Professor.',
    },
    (118, 1): {
        'monstruos': ('lily',),
        'monstruo_ids': (7,),
        'cantidad': 10,
        'token_id': 1403,
        'siguiente_paso': 2,
        'nombre_objetivo': 'Lily',
        'aviso_fin': 'Quest [Junior Lesson]: Report to Magic Professor.',
    },
    (119, 1): {
        'monstruos': ('wind elf',),
        'monstruo_ids': (1,),
        'cantidad': 15,
        'token_id': 1404,
        'siguiente_paso': 2,
        'nombre_objetivo': 'Wind Elf',
        'aviso_fin': 'Quest [Mid-Level Lesson]: Report to Magic Professor.',
    },
    (120, 1): {
        'monstruos': ('fire elf',),
        'monstruo_ids': (2,),
        'cantidad': 15,
        'token_id': 1405,
        'siguiente_paso': 2,
        'nombre_objetivo': 'Fire Elf',
        'aviso_fin': 'Quest [High-level Lesson]: Report to Magic Professor.',
    },
}

# Creditos otorgados por cada curso del Angel Lyceum (acumulan en token 1394)
CREDIT_HOURS_PER_QUEST = {
    106: 1, 107: 1, 108: 1, 109: 1,
    110: 2, 111: 2, 112: 2, 113: 2, 114: 2,
    115: 1, 116: 2, 117: 3,
    118: 1, 119: 2, 120: 3,
}

# Mapas de instancia/quest especiales conocidos
QUEST_MAPAS_INSTANCIA = {
    (123, 1): 244,  # Training Palace
    (124, 1): 244,  # Training Palace
    (125, 1): 244,  # Training Palace
    (126, 1): 244,  # Training Palace
    (162, 1): 158,  # Poker Castle
    (163, 1): 158,  # Poker Castle
}

# Alias y sinonimos conocidos de nombres de monstruos entre textos de quests y tablas de cliente
MONSTER_NAME_ALIASES = {
    'trainee witch': ['young witch', 'junior witch'],
    'young witch': ['trainee witch', 'junior witch'],
    'trainee witches': ['young witch', 'young witches'],
    'young witches': ['trainee witch', 'trainee witches'],
    'junior witch': ['young witch', 'trainee witch'],
    'hardworking pig': ['duty pig'],
    'duty pig': ['hardworking pig'],
    'transport worker': ['transporter'],
    'transporter': ['transport worker'],
    'riddle bishop': ['riddle city bishop', 'riddle city bishops', 'riddle bishops'],
    'riddle bishops': ['riddle bishop', 'riddle city bishop', 'riddle city bishops'],
    'riddle city bishop': ['riddle bishop', 'riddle bishops', 'riddle city bishops'],
    'riddle city bishops': ['riddle bishop', 'riddle bishops', 'riddle city bishop'],
}

# Cadenas de misiones de comandantes de ciudad (orden canonico de Angel Online)
_CADENAS_CIUDAD = {
    'militia chief': [542, 543, 544, 545, 546, 547, 548, 549, 550, 551, 552, 553, 554, 555, 556],  # Breeze Woods (29)
    'guard captain': [240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 253, 254, 255],  # Aurora City (3)
    'executive puyi': [343, 344, 345, 346, 347, 348, 349, 350, 351, 352, 353, 354, 355, 356, 357],  # Dark City (26)
    'chief assistant': [443, 444, 445, 446, 447, 448, 449, 450, 451, 452, 453, 454, 456, 457, 458],  # Iron Castle (38)
}

# Mapeo exacto de los 5 BOSSes y sus 5 piezas correspondientes para Quest 976 Paso 8
BOSSES_976_8 = {
    1220: 12605,  # Sword Jellyfish -> Life Diamond Shard
    3587: 12606,  # Leech Mrs. Dorsa -> Life Diamond Chunk
    3596: 12607,  # Hermit Hezon -> Life Diamond Fragment
    4483: 12608,  # Purple Scorpion Issac -> Life Diamond Chip
    4491: 12609,  # Destroyer Wesley -> Life Diamond Core
}

BOSS_NAMES_976_8 = {
    'sword jellyfish': 12605,
    'leech mrs. dorsa': 12606,
    'leech mrs dorsa': 12606,
    'hermit hezon': 12607,
    'purple scorpion issac': 12608,
    'destroyer wesley': 12609,
}


def normalizar_nombre_npc(nom: str) -> str:
    """Normaliza el nombre de un NPC para comparar el del mapa con el de la mision.

    EL ORDEN IMPORTA. Los NPC de las plantillas llevan el nombre como viaja en
    el mensaje, CORTADO A 16 caracteres, y las misiones lo llevan entero y a
    veces con prefijos. Para que los dos lados se corten en el mismo sitio:

      1. se quita el prefijo de nivel/rango, que nunca va en el nombre del NPC
         ("Level 90 - ", "Lvl 20, Rank 2 - ");
      2. se corta a 16, como en el mensaje;
      3. y SOLO ENTONCES se quita el titulo (Mr., Dr., Master...).

    Al reves no casaban: el mapa trae "Master Hunter Do" (cortado antes de
    quitar el titulo) y quitando el titulo primero la mision daba "hunter
    domma" contra "hunter do". Y sin cortar, Camp Leader Messi (en el mapa
    "Camp Leader Mess") no casaba con su mision 902 y no la ofrecia.
    """
    import re
    n = (nom or '').strip().lower()
    # tambien las variantes que trae quest.xml: "Leve 85 - Bandor", "Level 80 Phobe"
    n = re.sub(r'^(?:level|leve|lvl)\s*\d+(?:\s*,\s*rank\s*\d+)?\s*[-–:]?\s*', '', n).strip()
    n = n[:16].strip()
    for prefix in ('mr. ', 'mr ', 'dr. ', 'dr ', 'mrs. ', 'ms. ', 'sage ', 'elder ', 'master '):
        if n.startswith(prefix):
            n = n[len(prefix):].strip()
            break
    if n in ("angel tutor", "angels tutor", "angels' tutor"):
        return "angels' tutor"
    return n

_NPC_STAGE_MAP = None
_ITEM_NAMES_CACHE = None


def stage_de_entidad(ent_id: int) -> int:
    """Devuelve el stage_id exacto donde se encuentra este NPC segun las plantillas."""
    global _NPC_STAGE_MAP
    if _NPC_STAGE_MAP is None:
        _NPC_STAGE_MAP = {}
        plantillas_dir = pathlib.Path(__file__).parent / 'plantillas'
        for f in plantillas_dir.glob('*.json'):
            try:
                d = json.loads(f.read_text(encoding='utf-8'))
                if isinstance(d, dict) and 'stage' in d:
                    st = int(d['stage'])
                    for s in d.get('spawns', []):
                        if isinstance(s, dict) and not s.get('monstruo') and 'entity_id' in s:
                            _NPC_STAGE_MAP[int(s['entity_id'])] = st
            except Exception:
                pass
    return _NPC_STAGE_MAP.get(int(ent_id or 0), 0)


def nombre_item(item_id: int) -> str:
    """Nombre del item desde corpus/content.db con cache."""
    global _ITEM_NAMES_CACHE
    if _ITEM_NAMES_CACHE is None:
        _ITEM_NAMES_CACHE = {
            10: "FreshmanSabre",
            83266: "Rank Promotion Medal",
            78179: "Work ID",
            78180: "Microcoin",
        }
    if item_id in _ITEM_NAMES_CACHE:
        return _ITEM_NAMES_CACHE[item_id]
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if db.exists():
        try:
            import sqlite3
            con = sqlite3.connect(db)
            import inventario as _iv
            r = _iv.fila_item(con, '"基本名稱"', item_id)
            con.close()
            if r and r[0]:
                _ITEM_NAMES_CACHE[item_id] = r[0]
                return r[0]
        except Exception:
            pass
    return f"Item{item_id}"


def _cargar_db():
    global _DB, _MISIONES, _CACERIAS, _RECOLECCIONES, _NPC_INICIO, _NPC_PASOS, _REPETIBLES
    if _DB is not None:
        return
    _MISIONES = {}
    _CACERIAS = {}
    _RECOLECCIONES = {}
    _NPC_INICIO = {}
    _NPC_PASOS = {}
    _REPETIBLES = set()

    if RUTA_MISIONES_COMPLETAS.exists():
        try:
            _DB = json.loads(RUTA_MISIONES_COMPLETAS.read_text(encoding='utf-8'))
            for k, m in _DB.get('misiones', {}).items():
                _MISIONES[int(k)] = m
            _CACERIAS = _DB.get('cacerias', {})
            _RECOLECCIONES = _DB.get('recolecciones', {})
            _NPC_INICIO = _DB.get('npc_inicio', {})
            _NPC_PASOS = _DB.get('npc_pasos', {})
            _REPETIBLES = set(_DB.get('repetibles', []))

            # Integrar pasos de caceria que requieren items visibles reales a _RECOLECCIONES
            import inventario as _iv_rec
            for k_c, v_c in list(_CACERIAS.items()):
                tid = v_c.get('token_id')
                if tid and not _iv_rec.es_item_oculto(tid):
                    if k_c not in _RECOLECCIONES:
                        _RECOLECCIONES[k_c] = {
                            'qid': v_c.get('qid'),
                            'paso': v_c.get('paso'),
                            'siguiente_paso': v_c.get('siguiente_paso'),
                            'cantidad': v_c.get('cantidad', 1),
                            'items': [{'item_id': int(tid), 'cantidad': int(v_c.get('cantidad', 1))}],
                            'monstruo_ids': list(v_c.get('monstruo_ids', [])),
                            'monstruos': list(v_c.get('monstruos', [])),
                            'npc_entrega': v_c.get('npc_entrega'),
                            'mapa': v_c.get('mapa'),
                        }

            # Asegurar mapeo directo de Riddle Bishop (npc_type 911) para Black Crystals (12602) en Quest 976 paso 4
            if '976_4' in _RECOLECCIONES:
                r_976_4 = _RECOLECCIONES['976_4']
                if 911 not in r_976_4.get('monstruo_ids', []):
                    r_976_4.setdefault('monstruo_ids', []).append(911)
                for _alias in ('riddle bishop', 'riddle city bishop', 'riddle city bishops', 'riddle bishops'):
                    if _alias not in r_976_4.get('monstruos', []):
                        r_976_4.setdefault('monstruos', []).append(_alias)
            if '976_4' in _CACERIAS:
                c_976_4 = _CACERIAS['976_4']
                if 911 not in c_976_4.get('monstruo_ids', []):
                    c_976_4.setdefault('monstruo_ids', []).append(911)
                for _alias in ('riddle bishop', 'riddle city bishop', 'riddle city bishops', 'riddle bishops'):
                    if _alias not in c_976_4.get('monstruos', []):
                        c_976_4.setdefault('monstruos', []).append(_alias)

            # Quest 976 Paso 8: Los 5 BOSSes y sus 5 piezas correspondientes
            _CACERIAS.pop('976_8', None)
            _RECOLECCIONES['976_8'] = {
                'qid': 976,
                'paso': 8,
                'siguiente_paso': 9,
                'cantidad': 1,
                'items': [
                    {'item_id': 12605, 'cantidad': 1},
                    {'item_id': 12606, 'cantidad': 1},
                    {'item_id': 12607, 'cantidad': 1},
                    {'item_id': 12608, 'cantidad': 1},
                    {'item_id': 12609, 'cantidad': 1},
                ],
                'monstruo_ids': [1220, 3587, 3596, 4483, 4491],
                'monstruos': [
                    'sword jellyfish',
                    'leech mrs. dorsa',
                    'hermit hezon',
                    'purple scorpion issac',
                    'destroyer wesley',
                ],
                'npc_entrega': 'Villiersas',
                'mapa': 'Palm Base',
            }
            if 976 in _MISIONES and len(_MISIONES[976].get('pasos', [])) >= 8:
                _MISIONES[976]['pasos'][7]['tipo'] = 'recolectar'
                _MISIONES[976]['pasos'][7]['items'] = [
                    {'item_id': 12605, 'cantidad': 1},
                    {'item_id': 12606, 'cantidad': 1},
                    {'item_id': 12607, 'cantidad': 1},
                    {'item_id': 12608, 'cantidad': 1},
                    {'item_id': 12609, 'cantidad': 1},
                ]

            log.info(f"Cargadas {len(_MISIONES)} misiones completas desde misiones_completas.json (recolecciones: {len(_RECOLECCIONES)})")
            return
        except Exception as e:
            log.warning(f"Error cargando {RUTA_MISIONES_COMPLETAS}: {e}")

    # Fallback al archivo basico si no existe el completo
    if RUTA_MISIONES_JSON.exists():
        try:
            raw = json.loads(RUTA_MISIONES_JSON.read_text(encoding='utf-8'))
            for f in raw.get('filas', []):
                qid = f.get('id')
                if qid is not None:
                    _MISIONES[int(qid)] = f
        except Exception as e:
            log.warning(f"Error cargando {RUTA_MISIONES_JSON}: {e}")


def _cargar_misiones() -> dict:
    _cargar_db()
    return _MISIONES or {}


def info_mision(qid: int) -> dict:
    return _cargar_misiones().get(int(qid), {})


def nombre_mision(qid: int) -> str:
    m = info_mision(qid)
    return m.get('nombre') or _cl.nombre_de_quest(qid)


def es_repetible(qid: int) -> bool:
    _cargar_db()
    if qid in _REPETIBLES:
        return True
    m = info_mision(qid)
    return bool(m.get('repetible', False))


def estado_mision(p, qid: int):
    """Devuelve (activo: bool, paso: int, completada: bool)"""
    if not p or not getattr(p, 'quests', None):
        return (False, 0, False)
    for q, pa in p.quests:
        if q == qid:
            m = info_mision(qid)
            pasos = m.get('pasos', [])
            total_pasos = len(pasos) if pasos else 1
            completada = (pa > total_pasos) or (pa == 999)
            return (True, pa, completada)
    return (False, 0, False)


def total_pasos_mision(qid: int) -> int:
    m = info_mision(qid)
    pasos = m.get('pasos', [])
    return len(pasos) if pasos else 1


def mision_completada_raw(qid: int, pa: int) -> bool:
    tot = total_pasos_mision(qid)
    return (pa > tot) or (pa == 999)


def tiene_mision(p, qid: int) -> bool:
    if not p or not getattr(p, 'quests', None):
        return False
    return any(q == qid for q, _ in p.quests)


def mision_completada(p, qid: int) -> bool:
    if not p or not getattr(p, 'quests', None):
        return False
    for q, pa in p.quests:
        if q == qid:
            m = info_mision(qid)
            pasos = m.get('pasos', [])
            total_pasos = len(pasos) if pasos else 1
            return (pa > total_pasos) or (pa == 999)
    return False


def misiones_activas(p) -> list:
    """Devuelve lista de (qid, paso) que estan en progreso actualmente."""
    if not p or not getattr(p, 'quests', None):
        return []
    res = []
    for q, pa in p.quests:
        if not mision_completada(p, q):
            res.append((q, pa))
    return res


def obtener_paso_actual(p, qid: int) -> int:
    if not p or not getattr(p, 'quests', None):
        return 0
    for q, pa in p.quests:
        if q == qid:
            return pa
    return 0


_REQUISITOS = None


def requisitos_de(qid):
    """Lo que pide la mision para ofrecerse: caminos de misiones previas
    (basta cumplir uno) y si la faccion es libre. Sale de
    tools/requisitos_misiones.py, que lo lee de los mapas y de quest.xml."""
    global _REQUISITOS
    if _REQUISITOS is None:
        f = pathlib.Path(__file__).parent / 'plantillas' / 'requisitos_misiones.json'
        try:
            _REQUISITOS = json.loads(f.read_text(encoding='utf-8')).get('misiones', {})
        except Exception:
            _REQUISITOS = {}
    return _REQUISITOS.get(str(int(qid)))


def nivel_y_rango_requeridos(qid):
    """(nivel, rango) que pide la mision, sacados del prefijo que quest.xml
    pone en el NPC de inicio: "Lvl 20, Rank 2 - BreezeWood Angel" -> (20, 2).
    0 donde no pide nada."""
    ini = (info_mision(qid).get('npc_inicio') or '').strip().lower()
    m = re.match(r'^(?:level|leve|lvl)\s*(\d+)(?:\s*,\s*rank\s*(\d+))?', ini)
    if not m:
        return 0, 0
    return int(m.group(1)), int(m.group(2) or 0)


def misiones_disponibles_npc(p, npc_nombre: str, stage: int = 0, entidad: int = 0) -> list:
    """Devuelve la lista de IDs de misiones que este NPC puede ofrecer al personaje."""
    _cargar_db()
    if not npc_nombre:
        return []
    nom_l = npc_nombre.strip().lower()
    norm_l = normalizar_nombre_npc(nom_l)

    # Si se proporcionó entidad, obtener su mapa exacto
    if entidad:
        st_ent = stage_de_entidad(entidad)
        if st_ent:
            stage = st_ent

    # Si stage es 0 o desconocido y es un comandante de ciudad, inferir su stage principal
    if not stage:
        if nom_l == 'militia chief': stage = 29
        elif nom_l == 'guard captain': stage = 3
        elif nom_l == 'executive puyi': stage = 26
        elif nom_l == 'chief assistant': stage = 38

    qids = list(_NPC_INICIO.get(nom_l, []))
    if not qids and norm_l != nom_l:
        qids = list(_NPC_INICIO.get(norm_l, []))
    # Todas las claves que se quedan en el mismo NPC, no solo la primera:
    # quest.xml pone "BreezeWood Angel" en unas y "Lvl 20, Rank 2 -
    # BreezeWood Angel" en otras (la 558, la del Spy Angel), y con el nombre
    # exacto encontrado ya no se miraban las del prefijo.
    for k_npc, v_qids in _NPC_INICIO.items():
        if normalizar_nombre_npc(k_npc) == norm_l:
            qids += [q for q in v_qids if q not in qids]
    # Ultimo intento: el NPC es el FINAL del nombre de la mision ("Explorer
    # Nel" en la mision, "Nel" en el mapa). Solo con misiones de ESTE mapa,
    # para no ofrecer las de un NPC del mismo nombre en otro sitio.
    if not qids and stage and len(norm_l) >= 3:
        for k_npc, v_qids in _NPC_INICIO.items():
            if normalizar_nombre_npc(k_npc).endswith(' ' + norm_l):
                qids += [q for q in v_qids if info_mision(q).get('stage_id') == stage]

    # Angels' Tutor gestiona sus dialogos y misiones por su propio arbol dedicado
    if nom_l in ("angels' tutor", "angel tutor") or norm_l in ("angels' tutor", "angel tutor"):
        return []

    disponibles = []

    # Si el personaje ya tiene UNA misión activa de este NPC, no se ofrece otra
    for q_act, pa_act in list(getattr(p, 'quests', []) or []):
        if not mision_completada(p, q_act):
            q_info = info_mision(q_act)
            ini_raw = (q_info.get('npc_inicio') or '').strip().lower()
            if ini_raw in (nom_l, norm_l) or normalizar_nombre_npc(ini_raw) == norm_l:
                return []
            pasos = q_info.get('pasos', [])
            idx_p = pa_act - 1 if 0 < pa_act <= len(pasos) else 0
            if idx_p < len(pasos):
                p_npc_raw = (pasos[idx_p].get('npc_entrega') or pasos[idx_p].get('npc') or '').strip().lower()
                if p_npc_raw in (nom_l, norm_l) or normalizar_nombre_npc(p_npc_raw) == norm_l:
                    return []

    # Faccion del personaje normalizada
    p_fac = getattr(p, 'faction', 'Heaven') or 'Heaven'
    p_fac_l = p_fac.strip().lower()
    p_norm = 'aurora' if 'aurora' in p_fac_l else ('shadow' if ('shadow' in p_fac_l or 'dark' in p_fac_l) else ('steel' if ('steel' in p_fac_l or 'iron' in p_fac_l) else ('beasts' if ('beast' in p_fac_l or 'breeze' in p_fac_l) else 'heaven')))

    # Orden especial para jefes de milicia / ciudad en las 4 capitales
    if nom_l in _CADENAS_CIUDAD and (not stage or stage in (29, 3, 26, 38)):
        cadena_orden = _CADENAS_CIUDAD[nom_l]
        qids = [q for q in cadena_orden if q in qids] + [q for q in qids if q not in cadena_orden]

    for qid in qids:
        info = info_mision(qid)
        # 0. Descartar misiones de prueba internas
        if qid in (1, 2) or info.get('tipo') == 'Test':
            continue
        # 1. Filtro por mapa / stage
        q_stage = info.get('stage_id')
        if q_stage and stage and q_stage != stage:
            if stage in (3, 26, 29, 38) and normalizar_nombre_npc(info.get('npc_inicio')) == norm_l:
                pass
            elif stage in (41, 141, 241) and q_stage in (41, 141, 241):
                pass
            elif stage in (42, 142, 242) and q_stage in (42, 142, 242):
                pass
            elif stage in (43, 143, 243) and q_stage in (43, 143, 243):
                pass
            else:
                continue

        # 2. Si ya la tiene activa, no se ofrece de nuevo
        st, pa, comp = estado_mision(p, qid)
        if st and not comp:
            continue
        # 3. Si ya la completo: solo se ofrece si es repetible
        if comp and not es_repetible(qid):
            continue

        # 3b. REQUISITO PREVIO, de los datos del cliente (requisitos_misiones
        # .json). Sin esto no habia orden: Camp Leader Messi ofrecia la 905 y
        # la 910 a quien acababa de terminar la 901. El dialogo de Messi en el
        # mapa dice que la 902 se ofrece al que termino la 901, la 905 al que
        # termino la 904 y la 910 al que termino la 908 (o, en otro mapa, la
        # 909): con cumplir UN camino basta.
        _rq = requisitos_de(qid)
        if _rq and _rq.get('caminos'):
            if not any(all(mision_completada(p, int(pr)) for pr in cam)
                       for cam in _rq['caminos']):
                continue

        # 3c. NIVEL Y RANGO del prefijo de npc_inicio ("Lvl 20, Rank 2 -").
        _niv_rq, _rk_rq = nivel_y_rango_requeridos(qid)
        if _niv_rq and int(getattr(p, 'nivel', 1) or 1) < _niv_rq:
            continue
        if _rk_rq and int(getattr(p, 'rango', 1) or 1) < _rk_rq:
            continue

        # 4. Comprobar faccion de la mision
        q_fac = info.get('faccion')
        # La faccion de misiones_completas.json la puso el compilador, porque
        # quest.xml no la trae. Cuando la oferta esta en el dialogo de un mapa
        # y ese dialogo NO pide faccion, la mision es para todas: asi la 902
        # "The Return Plan", que salio como solo-Beasts y la hace cualquiera.
        if _rq and _rq.get('faccion_libre'):
            q_fac = None
        if q_fac:
            q_fac_l = q_fac.strip().lower()
            q_norm = 'aurora' if 'aurora' in q_fac_l else ('shadow' if ('shadow' in q_fac_l or 'dark' in q_fac_l) else ('steel' if ('steel' in q_fac_l or 'iron' in q_fac_l) else ('beasts' if ('beast' in q_fac_l or 'breeze' in q_fac_l) else '')))
            if q_norm and p_norm != 'heaven' and p_norm != q_norm:
                continue

        disponibles.append(qid)

    # Si hay misiones sin completar, darles prioridad sobre repetibles ya hechas
    sin_completar = [q for q in disponibles if not mision_completada(p, q)]
    if sin_completar:
        return sin_completar

    return disponibles


# Las misiones de ALUMNO del Angel Lyceum: registro, firmas, notas y cursos.
# Un graduado no las puede volver a hacer (un personaje de faccion Beasts que
# hablo con el Angels' Tutor recibio 100 -> 101 -> 102, 21/10/2026). La 123
# (Training top student) tampoco se puede EMPEZAR graduado, pero si se acepto
# antes se puede terminar despues (wiki: Top Student Training, Notes).
MISIONES_ALUMNO = frozenset({100, 101, 102} | set(range(106, 121)))
MISION_TOP_STUDENT = 123


def es_graduado(p) -> bool:
    """Facción de ciudad, o la graduacion (102) / la eleccion de pais (103) hechas."""
    if not p:
        return False
    fac = getattr(p, 'faction', 'Heaven') or 'Heaven'
    if fac not in ('Heaven', 'Neutral', 'Neutrally'):
        return True
    return mision_completada(p, 102) or tiene_mision(p, 103) or mision_completada(p, 103)


def cerrar_misiones_de_alumno(p) -> list:
    """A un graduado le quita las misiones de alumno que tenga ACTIVAS por
    error (las da por hechas). Devuelve las que toco."""
    if not es_graduado(p):
        return []
    tocadas = []
    nueva = []
    for q, pa in (p.quests or []):
        if q in MISIONES_ALUMNO and not mision_completada(p, q):
            nueva.append((q, 999))
            tocadas.append(q)
        else:
            nueva.append((q, pa))
    if tocadas:
        p.quests = nueva
    return tocadas


def aceptar_mision(ses, qid: int) -> bool:
    """Otorga la mision al jugador y la sincroniza con el cliente."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return False
    
    st, pa, comp = estado_mision(p, qid)
    if st and not comp:
        return False  # Ya activa
    if es_graduado(p) and (qid in MISIONES_ALUMNO or (qid == MISION_TOP_STUDENT and not st)):
        log.info(f"[{getattr(ses, 'addr', '')}] mision {qid} de alumno rechazada: ya esta graduado")
        return False
    if st and comp and not es_repetible(qid):
        # Una mision no repetible no se vuelve a dar: con Training top student
        # (123) se podia aceptar y completar sin fin hablando con Michael.
        log.info(f"[{getattr(ses, 'addr', '')}] mision {qid} ya completada y no repetible")
        return False

    char_id = p.char_id
    nom = nombre_mision(qid)
    info = info_mision(qid)
    pasos = info.get('pasos', [])
    paso_inicial = 1

    # Actualizar lista de quests del personaje (1-based internamente)
    nueva_lista = [item for item in (p.quests or []) if item[0] != qid]
    nueva_lista.append((qid, paso_inicial))
    p.quests = nueva_lista

    # 0x0022: alta de mision en cliente (paso de red 0 = primer paso activo)
    pkg_m = _cl.mision(char_id, qid, 0, 0)
    # 0x000D: cartel amarillo "You accept the quest [X]"
    pkg_av = _cl.aviso(nom, tipo=0, msg_id=_cl.MSG_QUEST)

    # Limpiar contadores y tokens si la mision tiene token de caceria (ej. cursos del Lyceum)
    c_token = OBJETIVOS_CACERIA.get((qid, 1), {}).get('token_id')
    if c_token:
        fijar_token_mision(ses, c_token, 0)
    for k in (f"{qid}_{paso_inicial}", f"{qid}_1", (qid, paso_inicial), (qid, 1)):
        if hasattr(ses, 'quest_kills') and isinstance(ses.quest_kills, dict):
            ses.quest_kills.pop(k, None)
        if hasattr(p, 'quest_kills') and isinstance(p.quest_kills, dict):
            p.quest_kills.pop(k, None)

    ses.enviar(pkg_m, pkg_av)
    if getattr(ses, 'usuario', None):
        cuentas.guardar_quests(ses.usuario, char_id, p.quests)

    log.info(f"[{getattr(ses, 'addr', '')}] {p.nombre} acepto mision {qid} '{nom}' (paso {paso_inicial})")
    return True


def avanzar_paso(ses, qid: int, nuevo_paso: int) -> bool:
    """Actualiza el paso de la mision y lo sincroniza con el cliente."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return False

    nueva_lista = []
    encontrada = False
    for q, pa in (p.quests or []):
        if q == qid:
            nueva_lista.append((q, nuevo_paso))
            encontrada = True
        else:
            nueva_lista.append((q, pa))

    if not encontrada:
        nueva_lista.append((qid, nuevo_paso))

    p.quests = nueva_lista
    char_id = p.char_id
    nom = nombre_mision(qid)

    # Actualizar tokens de firmas en Quest 101
    if qid == 101:
        if nuevo_paso == 2:
            fijar_token_mision(ses, 1391, 1)  # Battle Professor signature
        elif nuevo_paso == 3:
            fijar_token_mision(ses, 1392, 1)  # Magic Professor signature
        elif nuevo_paso == 4:
            fijar_token_mision(ses, 1393, 1)  # Mine Professor signature

    # En red el paso activo es 0-indexed: paso 1 = 0, paso 2 = 1, etc.
    paso_red = max(0, nuevo_paso - 1)
    pkg_m = _cl.mision(char_id, qid, paso_red, 0)
    pkg_av = _cl.aviso(f"{nom} ({nuevo_paso})", tipo=0, msg_id=_cl.MSG_TEXTO)

    ses.enviar(pkg_m, pkg_av)
    if getattr(ses, 'usuario', None):
        cuentas.guardar_quests(ses.usuario, char_id, p.quests)

    log.info(f"[{getattr(ses, 'addr', '')}] {p.nombre} avanzo mision {qid} '{nom}' al paso {nuevo_paso}")
    return True


def completar_mision(ses, qid: int, exp: int = 0, oro: int = 0,
                     items: list = None, creditos_honor: int = 0) -> bool:
    """Marca la mision como completada, retira items requeridos, entrega recompensas y persiste."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return False

    import combate as _cb
    info = info_mision(qid)
    if mision_completada(p, qid) and not info.get('repetible', False):
        return False
    pasos = info.get('pasos', [])
    total_pasos = len(pasos) if pasos else 1
    paso_completado = total_pasos + 1

    sello = int(time.time())
    nueva_lista = []
    encontrada = False
    for q, pa in (p.quests or []):
        if q == qid:
            nueva_lista.append((q, paso_completado))
            encontrada = True
        else:
            nueva_lista.append((q, pa))

    if not encontrada:
        nueva_lista.append((qid, paso_completado))

    p.quests = nueva_lista
    char_id = p.char_id
    nom = nombre_mision(qid)

    # 1. Paquete de mision completada (0x0022 con total_pasos y sello de tiempo)
    pkg_m = _cl.mision(char_id, qid, total_pasos, sello)

    # 2. Cartel de aviso
    pkg_av = _cl.aviso(f"Quest [{nom}] Completed!", tipo=0, msg_id=492)
    envios = [pkg_m, pkg_av]

    # 3. Eliminar items de quest segun borrar_items
    borrar_items = info.get('borrar_items', [])
    if borrar_items:
        import inventario as _inv
        inv = getattr(ses, 'inventario', {}) or {}
        cants = getattr(ses, 'cantidades', {}) or {}
        toco_inv = False
        dueno = getattr(ses, 'entity_id', char_id)
        for ranura, iid in list(inv.items()):
            if iid in borrar_items:
                r_int = int(ranura)
                inv.pop(r_int, None)
                inv.pop(str(r_int), None)
                cants.pop(r_int, None)
                cants.pop(str(r_int), None)
                envios.append(_inv.vaciar_ranura(dueno, r_int))
                toco_inv = True
                log.info(f"Item de quest consumido: ID {iid} en ranura {r_int}")
        if toco_inv:
            ses.inventario = inv
            ses.cantidades = cants
            if getattr(ses, 'usuario', None):
                cuentas.guardar_inventario(ses.usuario, char_id, inv, cants)

    # Limpiar cualquier residuo en memoria de slots de mision
    slot_oc = 497 + (qid % 60)
    if hasattr(ses, 'inventario') and isinstance(ses.inventario, dict):
        ses.inventario.pop(slot_oc, None)
        ses.inventario.pop(str(slot_oc), None)
    if hasattr(ses, 'cantidades') and isinstance(ses.cantidades, dict):
        ses.cantidades.pop(slot_oc, None)
        ses.cantidades.pop(str(slot_oc), None)

    # 4. Recompensas por defecto si no vienen fijadas
    recomp = info.get('recompensa', {})
    if qid == 976:
        # Recompensa oficial de Quest 976 ("Nature is Crying for Help"):
        # EXP dependiente del nivel (Lv<90: 36M, Lv 90-94: 48M, Lv>=95: 72M)
        # 1x Weekly Quest Mark (item 12611), sin costo de oro, 50 creditos.
        lvl = getattr(p, 'nivel', 1) or 1
        if lvl >= 95:
            exp = 72000000
        elif lvl >= 90:
            exp = 48000000
        else:
            exp = 36000000
        oro = 0
        creditos_honor = 50
        if not items and not recomp.get('items'):
            items = [{'item_id': 12611, 'cantidad': 1}]

    if exp <= 0:
        exp = recomp.get('exp', 0)
    # Quest 976 declara explicitamente cero oro. No volver a rellenarlo desde
    # una recompensa importada antigua (esa era la ruta que resucitaba el
    # mensaje nativo "Pay 29480" aun despues de poner oro = 0 arriba).
    if oro <= 0 and qid != 976:
        oro = recomp.get('oro', 0)
    if creditos_honor <= 0:
        creditos_honor = recomp.get('creditos', 0)
    if creditos_honor <= 0:
        creditos_honor = max(10, min(200, int((exp or 1000) // 1000) * 5))

    # 5. Oro de recompensa
    if oro > 0:
        import inventario as _inv_oro
        ses.oro = getattr(ses, 'oro', 0) + oro
        p.oro = ses.oro
        dueno = getattr(ses, 'entity_id', char_id)
        envios.append(_inv_oro.actualizar_ranura(char_id, _inv_oro.RANURA_ORO, _inv_oro.ITEM_ORO, ses.oro, dueno=dueno))
        envios.append(_cl.aviso(f"{oro} Gold", tipo=0, msg_id=_cl.MSG_ITEM))
        if getattr(ses, 'usuario', None):
            cuentas.guardar_oro(ses.usuario, char_id, ses.oro)

    # 6. Experiencia de recompensa
    if exp > 0:
        p.exp = getattr(p, 'exp', 0) + exp
        exp_actual_ui, _ = _cb.exp_para_barra(getattr(p, 'nivel', 1), p.exp)
        eid = getattr(p, 'entity_id', char_id)
        _u64 = lambda v: max(0, min(int(v or 0), 0xFFFFFFFFFFFFFFFF))
        envios.append(struct.pack('<HIBBQ', 0x001D, eid, 1, 32, _u64(exp_actual_ui)))
        envios.append(_cl.aviso(str(exp), tipo=0, msg_id=_cl.MSG_EXP))
        if getattr(ses, 'usuario', None):
            cuentas.guardar_progreso(ses.usuario, char_id, p.nivel, p.exp)

    # 7. Creditos de Rango / Honor
    if creditos_honor > 0:
        nuevos_cred = getattr(p, 'creditos', 0) + creditos_honor
        p.creditos = nuevos_cred
        eid = getattr(p, 'entity_id', char_id)
        # 0x0013 kind 49 (KIND_CREDITO) actualiza los creditos en la ficha
        envios.append(_cb.atributo(eid, nuevos_cred, _cb.KIND_CREDITO))
        # 0x000D msg 642 ("Obtain %s Credit.") muestra el aviso nativo en pantalla/chat
        envios.append(_cl.aviso(str(creditos_honor), tipo=0, msg_id=642))
        nuevo_rango = _cb.rango_de_creditos(nuevos_cred)
        rango_act = getattr(p, 'rango', 1) or 1
        if nuevo_rango > rango_act:
            p.rango = nuevo_rango
            envios.append(_cb.atributo(eid, nuevo_rango, _cb.KIND_RANGO))
            nom_rk = _cb.NOMBRES_RANGO.get(nuevo_rango, f"Rank {nuevo_rango}")
            envios.append(_cl.aviso(p.nombre, tipo=0, msg_id=675))
            envios.append(_cl.aviso(f"Rank Promoted to [{nom_rk}]!", tipo=0, msg_id=_cl.MSG_TEXTO))
        if getattr(ses, 'usuario', None):
            cuentas.guardar_rango(ses.usuario, char_id, getattr(p, 'rango', 1), nuevos_cred)

    # 8. Items de recompensa
    if not items:
        items = recomp.get('items', [])
    if items:
        import inventario as _inv
        inv = getattr(ses, 'inventario', {}) or {}
        cants = getattr(ses, 'cantidades', {}) or {}
        for it in items:
            if isinstance(it, int):
                item_id, cant = it, 1
            elif isinstance(it, dict):
                item_id = int(it.get('item_id') or it.get('id') or 0)
                cant = int(it.get('cantidad') or it.get('count') or 1)
            elif isinstance(it, (list, tuple)):
                item_id = it[1] if len(it) > 1 else it[0]
                cant = it[2] if len(it) > 2 else 1
            else:
                continue
            ranura_libre = None
            for r in range(20, 60):
                if r not in inv or inv[r] == 0:
                    ranura_libre = r
                    break
            if ranura_libre is not None:
                inv[ranura_libre] = item_id
                cants[ranura_libre] = cant
                ses.inventario = inv
                ses.cantidades = cants
                if p is not None:
                    p.inventario = inv
                    p.cantidades = cants
                envios.append(_inv.actualizar_ranura(char_id, ranura_libre, item_id, cant))
                nom_it = nombre_item(item_id)
                envios.append(_cl.aviso(nom_it, tipo=0, msg_id=_cl.MSG_ITEM))
                log.info(f"Entregado item de recompensa {item_id} en casilla {ranura_libre}")
        if getattr(ses, 'usuario', None):
            cuentas.guardar_inventario(ses.usuario, char_id, ses.inventario, ses.cantidades)

    # Limpieza de tokens de caceria de cursos del Lyceum
    c_token = OBJETIVOS_CACERIA.get((qid, 1), {}).get('token_id')
    if c_token:
        fijar_token_mision(ses, c_token, 0)
    for k in (f"{qid}_{total_pasos}", f"{qid}_1", (qid, total_pasos), (qid, 1)):
        if hasattr(ses, 'quest_kills') and isinstance(ses.quest_kills, dict):
            ses.quest_kills.pop(k, None)
        if hasattr(p, 'quest_kills') and isinstance(p.quest_kills, dict):
            p.quest_kills.pop(k, None)

    # Otorgar horas de credito si la mision es un curso del Lyceum
    credito = CREDIT_HOURS_PER_QUEST.get(qid, 0)
    if credito > 0:
        tot_cred = incrementar_token_mision(ses, 1394, credito)
        envios.append(_cl.aviso(f"Lyceum Credit Hours +{credito} (Total: {tot_cred})", tipo=0, msg_id=_cl.MSG_TEXTO))

    # Casos especiales de la cadena troncal del Lyceum
    if qid == 100:
        # Completar registro ofrece inmediatamente Quest 101
        aceptar_mision(ses, 101)
    elif qid == 101:
        # Retirar las 3 firmas de los profesores
        fijar_token_mision(ses, 1391, 0)
        fijar_token_mision(ses, 1392, 0)
        fijar_token_mision(ses, 1393, 0)
        # Iniciar registro de notas (Quest 102) con 0 horas de credito
        fijar_token_mision(ses, 1394, 0)
        aceptar_mision(ses, 102)
    elif qid == 102:
        # Limpiar token de notas y pasar a eleccion de faccion (Quest 103)
        fijar_token_mision(ses, 1394, 0)
        aceptar_mision(ses, 103)

    ses.enviar(*envios)

    if getattr(ses, 'usuario', None):
        cuentas.guardar_quests(ses.usuario, char_id, p.quests)

    log.info(f"[{getattr(ses, 'addr', '')}] {p.nombre} completo mision {qid} '{nom}'! (Exp +{exp}, Oro +{oro})")
    return True


def abandonar_mision(ses, qid: int) -> bool:
    """Elimina una mision activa del registro del jugador y sincroniza con el cliente."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return False

    # Proteger tutorial del Guide Palace (101, 102) y etapas 1..9
    if qid in (101, 102) or qid in range(1, 10):
        log.warning(f"Intento de abandonar mision protegida {qid}")
        return False

    tiene = False
    nueva_lista = []
    for q, pa in (p.quests or []):
        if q == qid:
            tiene = True
        else:
            nueva_lista.append((q, pa))

    if not tiene:
        return False

    p.quests = nueva_lista

    # Limpiar contadores de caceria de esta mision
    if hasattr(ses, 'quest_kills'):
        for k in list(ses.quest_kills.keys()):
            if isinstance(k, tuple) and k[0] == qid:
                del ses.quest_kills[k]
            elif isinstance(k, str) and k.startswith(f"{qid}_"):
                del ses.quest_kills[k]

    if getattr(p, 'quest_kills', None):
        for k in list(p.quest_kills.keys()):
            if isinstance(k, tuple) and k[0] == qid:
                del p.quest_kills[k]
            elif isinstance(k, str) and k.startswith(f"{qid}_"):
                del p.quest_kills[k]

    # Guardar en base de datos
    if getattr(ses, 'usuario', None):
        cuentas.guardar_quests(ses.usuario, p.char_id, p.quests)
        if hasattr(p, 'quest_kills'):
            cuentas.guardar_quest_kills(ses.usuario, p.char_id, p.quest_kills)

    # Sincronizar con el cliente exactamente como el servidor oficial (mundo_180305_971213_orden.jsonl):
    # Enviar UNICAMENTE el paquete 0x0022 con modo 2 (borrado puntual).
    # NUNCA enviar 0x0021 aqui porque 0x0021 (sub_5FBD30) limpia y reconstruye la lista en Angel.exe;
    # si la mision ya no esta en la lista, el posterior 0x0022 (sub_602BD0) llama a std::map::erase
    # con un iterador invalido y la CRT de MSVC crashea el cliente con _invalid_parameter_noinfo.
    pkg_del = _cl.borrar_mision(p.char_id, qid)
    ses.enviar(pkg_del)

    # Limpiar cualquier resto en memoria de slots de mision
    slot_oc = 497 + (qid % 60)
    if hasattr(ses, 'inventario') and isinstance(ses.inventario, dict):
        ses.inventario.pop(slot_oc, None)
        ses.inventario.pop(str(slot_oc), None)
    if hasattr(ses, 'cantidades') and isinstance(ses.cantidades, dict):
        ses.cantidades.pop(slot_oc, None)
        ses.cantidades.pop(str(slot_oc), None)

    nom = nombre_mision(qid)
    ses.enviar(_cl.aviso(f"Quest [{nom}] abandoned.", tipo=0, msg_id=_cl.MSG_TEXTO))
    log.info(f"[{getattr(ses, 'addr', '')}] {p.nombre} abandono la mision {qid} '{nom}'")
    return True


def registrar_baja_monstruo(ses, npc_type: int, monster_name: str = None, en_combate_real: bool = False) -> bool:
    """Verifica si el monstruo derrotado suma para alguna mision activa del jugador."""
    _cargar_db()
    p = getattr(ses, 'personaje', None)
    if not p or not getattr(p, 'quests', None):
        return False

    if not hasattr(p, 'quest_kills') or p.quest_kills is None:
        p.quest_kills = {}
    if not hasattr(ses, 'quest_kills') or ses.quest_kills is None:
        ses.quest_kills = p.quest_kills

    m_nom_clean = monster_name.lower().strip() if monster_name else ''
    actualizado = False

    # Revisar cada mision activa una sola vez (evita duplicar conteos)
    for q, pa in list(p.quests):
        k_cac = f"{q}_{pa}"
        clave_tupla = (q, pa)

        paso_c = max(0, int(pa) - 1)
        if en_combate_real:
            try:
                import eventos as _ev_chk
                if _ev_chk.paso_definido_por_muertes(q, paso_c):
                    continue
            except Exception:
                pass

        c_data = None
        if clave_tupla in OBJETIVOS_CACERIA:
            c_data = OBJETIVOS_CACERIA[clave_tupla]
        elif k_cac in _CACERIAS:
            # Las entradas COMPILADAS se apartan cuando el mapa del cliente ya
            # define este paso: alli esta exacto que bicho da que token y
            # cuando se avanza, y lo ejecuta server/eventos.py. El compilador
            # rompia justo estos casos -- en la 901 tomo "the following
            # monsters away" por nombre de monstruo y sumaba las cuatro
            # cacerias en un solo contador, con ese texto en el chat. Las de
            # OBJETIVOS_CACERIA, puestas a mano, no se tocan.
            #
            # Y solo las ROTAS, las que el compilador dejo sin ids de
            # monstruo (481 de 880): las que si tienen ids ya contaban y se
            # dejan como estaban, para no cambiar misiones que funcionan.
            try:
                import eventos as _ev_m
                if (not _CACERIAS[k_cac].get('monstruo_ids')
                        and _ev_m.paso_definido_por_muertes(q, max(0, int(pa) - 1))):
                    continue
            except Exception:
                pass
            c_data = _CACERIAS[k_cac]

        if not c_data:
            continue

        req = c_data.get('cantidad', 1)
        token = c_data.get('token_id')
        m_ids = (c_data.get('monstruos', ()) if ('monstruos' in c_data and isinstance(c_data['monstruos'], (list, tuple))
                 and (not c_data['monstruos'] or isinstance(c_data['monstruos'][0], int)))
                 else c_data.get('monstruo_ids', []))
        m_noms = (c_data.get('monstruos', []) if ('monstruos' in c_data and isinstance(c_data['monstruos'], (list, tuple))
                  and c_data['monstruos'] and isinstance(c_data['monstruos'][0], str))
                  else [])

        nom_obj = c_data.get('nombre_objetivo') or 'Target'
        if 'defeat trainee witch' in nom_obj.lower():
            nom_obj = 'Young Witch / Crystal Envoy'

        coincide = False
        if npc_type in m_ids or (token and npc_type == token):
            coincide = True
        elif m_nom_clean:
            cand_noms = [m_nom_clean] + MONSTER_NAME_ALIASES.get(m_nom_clean, [])
            for cn in cand_noms:
                if any(mn in cn or cn in mn for mn in m_noms):
                    coincide = True
                    break
                for mn in m_noms:
                    if any(al in cn or cn in al for al in MONSTER_NAME_ALIASES.get(mn, [])):
                        coincide = True
                        break
                if coincide:
                    break

        if not coincide and m_nom_clean:
            # Fallback robusto: comprobar si el nombre del monstruo aparece directamente en el texto del paso
            q_info = info_mision(q)
            pasos = q_info.get('pasos', [])
            idx_p = pa - 1 if 0 < pa <= len(pasos) else 0
            if idx_p < len(pasos):
                import re as _re_reg
                raw_txt = pasos[idx_p].get('texto', '')
                txt_clean = _re_reg.sub(r'\\n|[\r\n\t]+', ' ', raw_txt.lower())
                txt_clean = _re_reg.sub(r'\s+', ' ', txt_clean)
                cand_noms = [m_nom_clean] + MONSTER_NAME_ALIASES.get(m_nom_clean, [])
                if any(cn in txt_clean for cn in cand_noms):
                    coincide = True
                else:
                    words = [w for w in _re_reg.findall(r'[a-z]+', m_nom_clean) if len(w) > 3 and w not in ('kill', 'defeat', 'city', 'great', 'little', 'young')]
                    if words and all(w in txt_clean for w in words):
                        coincide = True

        if coincide and not (npc_type in m_ids or (token and npc_type == token)):
            # Por nombre o por texto solo en el mapa del paso, si lo dice: un
            # monstruo de nombre parecido en otro mapa no cuenta (21/10/2026).
            _st_k = mapa_del_paso(q, pa)
            if _st_k and int(getattr(p, 'stage', 0) or 0) != int(_st_k):
                coincide = False

        if coincide:
            cnt = int(p.quest_kills.get(k_cac, 0)) + 1
            p.quest_kills[k_cac] = cnt
            ses.quest_kills[k_cac] = cnt
            ses.quest_kills[clave_tupla] = cnt
            actualizado = True

            # Si la mision tiene un token de seguimiento (ej. 1400..1405), actualizarlo en el cliente
            if token:
                fijar_token_mision(ses, token, cnt)

            # 1. Notificar en pantalla/chat EN CADA BAJA para que el jugador sepa de inmediato que cuenta
            ses.enviar(_cl.aviso(f"Defeated {nom_obj} ({cnt}/{req})", tipo=0, msg_id=_cl.MSG_TEXTO))

            # 2. Guardar conteo en base de datos inmediatamente
            if getattr(ses, 'usuario', None):
                cuentas.guardar_quest_kills(ses.usuario, p.char_id, p.quest_kills)

            # 4. Al completar el total requerido
            if cnt >= req:
                p.quest_kills[k_cac] = req
                ses.quest_kills[k_cac] = req
                ses.quest_kills[clave_tupla] = req

                # Avanzar al siguiente paso (cambia el objetivo de caceria a entrega/hablar en el HUD del cliente)
                sig_paso = c_data.get('siguiente_paso') or (pa + 1)
                avanzar_paso(ses, q, sig_paso)

                nom_q = nombre_mision(q)
                npc_ent = c_data.get('npc_entrega') or ('Blocks Envoy' if q == 142 else '')
                mapa_ent = c_data.get('mapa') or ('Mushroom Village' if q == 142 else '')
                aviso_fin = c_data.get('aviso_fin')
                if not aviso_fin:
                    aviso_fin = f"Quest [{nom_q}]: Defeated {nom_obj} ({req}/{req})!"
                    if npc_ent:
                        aviso_fin += f" Report to {npc_ent}"
                    if mapa_ent:
                        aviso_fin += f" ({mapa_ent})"
                ses.enviar(_cl.aviso(aviso_fin, tipo=0, msg_id=_cl.MSG_TEXTO))
                log.info(f"[{getattr(ses, 'addr', '')}] {p.nombre} completo caceria de {nom_obj} ({req}/{req}) para mision {q}")

    return actualizado


def slot_oculto_para_item(ses, item_id: int, qid: int = 0) -> int:
    """Busca o asigna una ranura libre en el rango 497..556 para un item de mision oculto."""
    inv = getattr(ses, 'inventario', {}) or {}
    iid = int(item_id)
    # 1. Si el item ya esta en alguna ranura oculta, reutilizar esa
    for r, it in inv.items():
        try:
            r_int = int(r)
            if 497 <= r_int <= 556 and int(it) == iid:
                return r_int
        except (ValueError, TypeError):
            continue
    # 2. Preferir ranura basada en qid si se conoce o se puede deducir
    target_qid = qid
    if not target_qid:
        p = getattr(ses, 'personaje', None)
        if p and getattr(p, 'quests', None):
            _cargar_db()
            for q, pa in list(p.quests):
                k_rec = f"{q}_{pa}"
                if k_rec in _RECOLECCIONES:
                    reqs = _RECOLECCIONES[k_rec].get('items', [])
                    if any(req.get('item_id') == iid for req in reqs):
                        target_qid = q
                        break
    if target_qid > 0:
        pref = 497 + (target_qid % 60)
        if pref not in inv and str(pref) not in inv:
            return pref
    # 3. Buscar la primera ranura libre en 497..556
    for r in range(497, 557):
        if r not in inv and str(r) not in inv:
            return r
    return 497


def obtener_token_mision(ses, token_id: int) -> int:
    """Devuelve la cantidad del token de mision alojado en el rango 497..556."""
    inv = getattr(ses, 'inventario', {}) or {}
    cants = getattr(ses, 'cantidades', {}) or {}
    for r in range(497, 557):
        if inv.get(r) == token_id or inv.get(str(r)) == token_id:
            return int(cants.get(r, cants.get(str(r), 1)) or 0)
    return 0


def fijar_token_mision(ses, token_id: int, cant: int = 1):
    """Establece o retira un token de mision en las ranuras ocultas 497..556 y sincroniza con cliente."""
    import inventario as _inv
    inv = getattr(ses, 'inventario', {}) or {}
    cants = getattr(ses, 'cantidades', {}) or {}
    p = getattr(ses, 'personaje', None)
    char_id = getattr(p, 'char_id', 0)
    dueno = getattr(ses, 'entity_id', char_id)

    target_slot = None
    for r in range(497, 557):
        if inv.get(r) == token_id or inv.get(str(r)) == token_id:
            target_slot = r
            break

    if cant <= 0:
        if target_slot is not None:
            inv.pop(target_slot, None)
            inv.pop(str(target_slot), None)
            cants.pop(target_slot, None)
            cants.pop(str(target_slot), None)
            ses.inventario = inv
            ses.cantidades = cants
            if p:
                p.inventario = inv
                p.cantidades = cants
            ses.enviar(_inv.vaciar_ranura(dueno, target_slot))
            if getattr(ses, 'usuario', None):
                cuentas.guardar_inventario(ses.usuario, char_id, inv, cants)
        return

    if target_slot is None:
        target_slot = slot_oculto_para_item(ses, token_id)

    inv[target_slot] = token_id
    inv.pop(str(target_slot), None)
    cants[target_slot] = cant
    cants.pop(str(target_slot), None)
    ses.inventario = inv
    ses.cantidades = cants
    if p:
        p.inventario = inv
        p.cantidades = cants
    ses.enviar(_inv.actualizar_ranura(char_id, target_slot, token_id, cant, dueno=dueno))
    if getattr(ses, 'usuario', None):
        cuentas.guardar_inventario(ses.usuario, char_id, inv, cants)


def incrementar_token_mision(ses, token_id: int, delta: int = 1) -> int:
    """Incrementa la cantidad de un token de mision y devuelve el nuevo total."""
    actual = obtener_token_mision(ses, token_id)
    nuevo = max(0, actual + delta)
    fijar_token_mision(ses, token_id, nuevo)
    return nuevo


_RE_ETIQUETA = None


def _etiquetas_del_paso(texto):
    """{item_id: etiqueta} de las lineas "Etiqueta: %item%" del texto del paso.

    En "Withered Maneaters: %30751% / 25 Red Magatama" la etiqueta es el
    MONSTRUO que suelta ese objeto; en "Aspen Wood: %49%" es el propio objeto.
    """
    global _RE_ETIQUETA
    import re as _re_e
    if _RE_ETIQUETA is None:
        _RE_ETIQUETA = _re_e.compile(r"([A-Za-z][A-Za-z'\.\- ]{1,40}?)\s*[:：]\s*(?:/c\$\d)?%(\d+)%")
    limpio = _re_e.sub(r'\\n|[\r\n\t]+', '\n', texto or '')
    return {int(i): e.strip() for e, i in _RE_ETIQUETA.findall(limpio)}


def _singular(nombre):
    n = (nombre or '').lower().strip()
    for suf in ('ies', 'es', 's'):
        if n.endswith(suf) and len(n) > len(suf) + 2:
            return n[:-len(suf)] + ('y' if suf == 'ies' else '')
    return n


def _mismo_nombre(a, b):
    a, b = _singular(a), _singular(b)
    return bool(a and b) and (a == b or a in b or b in a)


_MAPA_FIABLE = {}


def _nombres_en_mapa(stage):
    """Nombres (minusculas) de los monstruos de la plantilla de ese mapa."""
    import json
    import sys
    import login as _lg_m
    mapas = dict(_lg_m.PLANTILLAS_POR_STAGE)
    app_mod = sys.modules.get('app')
    if app_mod is not None:
        mapas.update(getattr(app_mod, 'MAPAS_APARTE', {}) or {})
    nombre = mapas.get(int(stage))
    if not nombre:
        return set()
    f = pathlib.Path(__file__).parent / 'plantillas' / nombre
    if not f.exists():
        return set()
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        return set()
    return {(e.get('nombre') or '').lower() for e in d.get('spawns', []) if e.get('monstruo')}


def mapa_del_paso(qid, paso):
    """El stage del paso SOLO si es fiable: si en ese mapa salen de verdad los
    monstruos que nombra el paso. Un tercio de los pasos traen un stage que no
    cuadra (la 154 paso 2 dice Building Blocks City y trae el de County), y
    exigirlo rompia esas misiones. None = no se mira el mapa."""
    clave = (int(qid), int(paso))
    if clave in _MAPA_FIABLE:
        return _MAPA_FIABLE[clave]
    pasos = info_mision(qid).get('pasos', [])
    p = pasos[paso - 1] if 0 < paso <= len(pasos) else {}
    st = p.get('stage_id')
    fiable = None
    if st:
        en_mapa = _nombres_en_mapa(st)
        cands = [x for x in p.get('monstruos', []) if isinstance(x, str)]
        cands += list(_etiquetas_del_paso(p.get('texto', '')).values())
        if en_mapa and any(_mismo_nombre(c, n) for c in cands for n in en_mapa if n):
            fiable = int(st)
    _MAPA_FIABLE[clave] = fiable
    return fiable


def verificar_botin_mision(ses, npc_type: int, monster_name: str = None) -> list:
    """
    Comprueba si el monstruo derrotado debe soltar un objeto para una misión
    de recolección activa del jugador, y devuelve [(item_id, cantidad)].
    """
    p = getattr(ses, 'personaje', None)
    if not p or not getattr(p, 'quests', None):
        return []

    _cargar_db()
    m_nom = (monster_name or '').lower().strip()
    drops_mision = []

    inv = getattr(ses, 'inventario', {}) or {}
    cants = getattr(ses, 'cantidades', {}) or {}

    for q, pa in list(p.quests or []):
        if mision_completada(p, q):
            continue

        # Manejo especial para Quest 976 Paso 8: cada BOSS suelta su propia pieza específica al 100%
        if q == 976 and pa == 8:
            target_item = None
            if npc_type in BOSSES_976_8:
                target_item = BOSSES_976_8[npc_type]
            elif m_nom:
                for b_name, b_item in BOSS_NAMES_976_8.items():
                    if b_name in m_nom or m_nom in b_name:
                        target_item = b_item
                        break
            if target_item:
                actual = sum(cants.get(r, 1) for r, it in inv.items() if it == target_item)
                if actual < 1:
                    drops_mision.append((target_item, 1))
            continue

        k_rec = f"{q}_{pa}"
        r_data = _RECOLECCIONES.get(k_rec)
        if not r_data and k_rec in _CACERIAS:
            c_data = _CACERIAS[k_rec]
            tid = c_data.get('token_id')
            import inventario as _iv_drop
            if tid and not _iv_drop.es_item_oculto(tid):
                r_data = {
                    'qid': q,
                    'paso': pa,
                    'cantidad': c_data.get('cantidad', 1),
                    'items': [{'item_id': int(tid), 'cantidad': int(c_data.get('cantidad', 1))}],
                    'monstruo_ids': list(c_data.get('monstruo_ids', [])),
                    'monstruos': list(c_data.get('monstruos', [])),
                }
        if not r_data:
            continue

        req_items = r_data.get('items', [])
        m_ids = r_data.get('monstruo_ids', [])
        m_noms = [mn.lower().strip() for mn in r_data.get('monstruos', []) if isinstance(mn, str)]

        # Que objeto va con que criatura y en que mapa (texto y stage del
        # paso). Matar un monstruo de Hidden Grove subia las cinco magatamas
        # de Angelic Help (1163, Samara Woods) a la vez (21/10/2026).
        _q_inf = info_mision(q)
        _pasos_q = _q_inf.get('pasos', [])
        _paso_q = _pasos_q[pa - 1] if 0 < pa <= len(_pasos_q) else {}
        etiquetas = _etiquetas_del_paso(_paso_q.get('texto', ''))
        _st_paso = mapa_del_paso(q, pa)
        en_su_mapa = not _st_paso or int(getattr(p, 'stage', 0) or 0) == int(_st_paso)

        for req in req_items:
            iid = req.get('item_id')
            req_cnt = req.get('cantidad', 1)
            if not iid:
                continue
            # Contar cuántos tiene ya el jugador
            actual = sum(cants.get(r, 1) for r, it in inv.items() if it == iid)
            if actual >= req_cnt:
                continue

            # Comprobar si el monstruo coincide con el item o la misión
            coincide = False
            etiqueta = etiquetas.get(int(iid))
            etiqueta_es_objeto = bool(etiqueta) and _mismo_nombre(etiqueta, nombre_item(iid))
            if npc_type and m_ids and npc_type in m_ids:
                coincide = True
            elif npc_type and iid == npc_type:
                coincide = True
            elif etiqueta and not etiqueta_es_objeto:
                # La linea dice que criatura lo suelta: solo esa, y en su mapa.
                if en_su_mapa and m_nom:
                    m_base_e = m_nom[2:].strip() if m_nom.startswith('e-') else m_nom
                    coincide = any(_mismo_nombre(etiqueta, cn) for cn in
                                   [m_nom, m_base_e] + MONSTER_NAME_ALIASES.get(m_nom, []))
                if not coincide:
                    continue
            elif not en_su_mapa:
                continue
            else:
                item_nom = nombre_item(iid).lower()
                if m_nom and (m_nom in item_nom or item_nom in m_nom):
                    coincide = True
                elif m_nom and m_noms:
                    cand_noms = [m_nom] + MONSTER_NAME_ALIASES.get(m_nom, [])
                    if any(any(mn in cn or cn in mn for mn in m_noms) for cn in cand_noms):
                        coincide = True

            if not coincide:
                # Comprobar si la descripción del paso menciona a este monstruo
                q_info = info_mision(q)
                pasos = q_info.get('pasos', [])
                idx_p = pa - 1 if 0 < pa <= len(pasos) else 0
                if idx_p < len(pasos):
                    import re as _re_txt
                    raw_txt = pasos[idx_p].get('texto', '')
                    txt_clean = _re_txt.sub(r'\\n|[\r\n\t]+', ' ', raw_txt.lower())
                    txt_clean = _re_txt.sub(r'\s+', ' ', txt_clean)
                    m_base = m_nom[2:].strip() if m_nom.startswith('e-') else m_nom
                    cand_noms = [m_nom, m_base] + MONSTER_NAME_ALIASES.get(m_nom, []) + MONSTER_NAME_ALIASES.get(m_base, [])
                    if any(cn and cn in txt_clean for cn in cand_noms):
                        coincide = True
                    else:
                        words = [w for w in _re_txt.findall(r'[a-z]+', m_nom) if len(w) > 3 and w not in ('kill', 'defeat', 'city', 'great', 'little', 'young')]
                        if words and all(w in txt_clean for w in words):
                            coincide = True

            if coincide:
                drops_mision.append((iid, 1))

    return drops_mision


def verificar_progreso_recoleccion(ses, items_tocados: list) -> list:
    """Comprueba si alguno de los items añadidos al inventario forma parte de una
    misión de recolección activa. Devuelve una lista de paquetes a enviar (avisos y 0x0021 QUEST_LOG)."""
    p = getattr(ses, 'personaje', None)
    if not p or not getattr(p, 'quests', None) or not items_tocados:
        return []

    _cargar_db()
    inv = getattr(ses, 'inventario', {}) or {}
    cants = getattr(ses, 'cantidades', {}) or {}
    items_set = {int(x) for x in items_tocados if x and int(x) > 0}

    paquetes = []
    hubo_mision = False

    for q, pa in list(p.quests or []):
        if mision_completada(p, q):
            continue
        k_rec = f"{q}_{pa}"
        if k_rec not in _RECOLECCIONES:
            continue
        r_data = _RECOLECCIONES[k_rec]
        req_items = r_data.get('items', [])
        for req in req_items:
            iid = req.get('item_id')
            req_cnt = req.get('cantidad', 1)
            if iid in items_set:
                hubo_mision = True
                actual = sum(cants.get(r, 1) for r, it in inv.items() if it == iid)
                nom = nombre_item(iid)
                paquetes.append(_cl.aviso(f"Collected {nom} ({actual}/{req_cnt})", tipo=0, msg_id=_cl.MSG_TEXTO))

    if hubo_mision:
        paquetes.append(_cl.paquete_quest_log(p.char_id, p.quests))

    return paquetes


def verificar_entrega_items(ses, qid: int, paso: int) -> bool:
    """Comprueba si el jugador tiene los items requeridos para el paso y los consume si es así."""
    _cargar_db()
    k_rec = f"{qid}_{paso}"
    if k_rec not in _RECOLECCIONES:
        return True

    r_data = _RECOLECCIONES[k_rec]
    req_items = r_data.get('items', [])
    if not req_items:
        return True

    inv = getattr(ses, 'inventario', {}) or {}
    cants = getattr(ses, 'cantidades', {}) or {}

    # 1. Verificar si cumple todos los requisitos
    for req in req_items:
        req_id = req.get('item_id')
        req_cnt = req.get('cantidad', 1)
        total_tenido = 0
        for r, iid in inv.items():
            if iid == req_id:
                total_tenido += cants.get(r, 1)
        if total_tenido < req_cnt:
            nom_q = nombre_mision(qid)
            ses.enviar(_cl.aviso(f"Quest [{nom_q}]: Missing items ({total_tenido}/{req_cnt})", tipo=0, msg_id=_cl.MSG_TEXTO))
            return False

    # 2. Consumir los items
    import inventario as _inv
    char_id = getattr(ses.personaje, 'char_id', 0)
    dueno = getattr(ses, 'entity_id', char_id)
    for req in req_items:
        req_id = req.get('item_id')
        falta_quitar = req.get('cantidad', 1)
        for r in list(inv.keys()):
            r_int = int(r)
            if inv.get(r_int) == req_id and falta_quitar > 0:
                act = cants.get(r_int, 1)
                if act <= falta_quitar:
                    falta_quitar -= act
                    inv.pop(r_int, None)
                    inv.pop(str(r_int), None)
                    cants.pop(r_int, None)
                    cants.pop(str(r_int), None)
                    ses.enviar(_inv.vaciar_ranura(dueno, r_int))
                else:
                    cants[r_int] = act - falta_quitar
                    ses.enviar(_inv.actualizar_ranura(char_id, r_int, req_id, cants[r_int], dueno=dueno))
                    falta_quitar = 0

    ses.inventario = inv
    ses.cantidades = cants
    if getattr(ses, 'usuario', None):
        cuentas.guardar_inventario(ses.usuario, ses.personaje.char_id, inv, cants)

    return True


# Palabras que no distinguen a un NPC de otro: cargos, lugares, oficios.
_PALABRAS_COMUNES = {
    'the', 'camp', 'leader', 'angel', 'chief', 'captain', 'elder', 'master',
    'sage', 'guard', 'guardian', 'city', 'village', 'director', 'seller',
    'salesman', 'expert', 'clerk', 'bank', 'banker', 'little', 'young', 'old',
    'great', 'lady', 'lord', 'king', 'queen', 'general', 'soldier', 'militia',
    'officer', 'priest', 'doctor', 'level', 'from', 'with', 'town', 'forest',
    'green', 'scholar', 'admin', 'guild', 'staff', 'head', 'lyceum', 'mage',
    'professor', 'lecturer', 'teacher'}
_NOMBRES_NPC = None


def _palabras(nombre):
    import re as _re
    return [w for w in _re.findall(r"[a-z][a-z'-]+", (nombre or '').lower())]


def npc_segun_texto(texto, npc_clicado):
    """Si el texto del paso apunta al NPC que se ha clicado.

    True  el texto lo nombra
    False el texto nombra a OTRO NPC
    None  el texto no nombra a ninguno: que decida el NPC compilado

    POR QUE. El compilador asigno mal el NPC de 236 pasos de "hablar con": la
    902 dice "1. Talk to Sharker in the Breeze Woods" y le puso Camp Leader
    Messi, y la 152 dice "dale los caramelos a Lloyd" y le puso Item Angel.
    Clicando a Sharker salia su dialogo de siempre y la mision no avanzaba.
    El texto es del cliente y es el que dice a quien ir.

    Se compara por palabras DISTINTIVAS del NPC clicado, no por el nombre
    entero, porque los textos usan nombres cortos ("Talk to Messi in the
    Waterfall Camp") y el NPC llega cortado a 16 ("Camp Leader Mess"): basta
    con que una palabra suya sin cargo ni lugar empiece una palabra del texto.
    """
    import re as _re
    global _NOMBRES_NPC
    t = _re.sub(r'/c[$#][0-9a-fA-F]*|/c\*|\n', ' ', texto or '').lower()
    pal_t = set(_re.findall(r"[a-z][a-z'-]+", t))
    if not pal_t:
        return None
    mias = [w for w in _palabras(npc_clicado) if len(w) >= 4 and w not in _PALABRAS_COMUNES]
    if any(any(x.startswith(w) for x in pal_t) for w in mias):
        return True
    # No me nombra a mi: nombra a algun otro NPC conocido?
    if _NOMBRES_NPC is None:
        _NOMBRES_NPC = set()
        try:
            import sqlite3
            db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
            con = sqlite3.connect(str(db))
            for (n,) in con.execute('select name from npc'):
                for w in _palabras(n):
                    if len(w) >= 4 and w not in _PALABRAS_COMUNES:
                        _NOMBRES_NPC.add(w)
            con.close()
        except Exception:
            pass
    # Solo cuenta si el nombre va DETRAS de "to / with / ask / tell / visit"
    # ("Talk to Sharker", "hand it to Lloyd", "talk to the Leader Alonso"),
    # saltando articulos y cargos. Una palabra suelta no basta: "find a Wind
    # Pinecone" no manda a ningun NPC, pero "wind" es de Wind Elf y Wind Gate.
    for m in _re.finditer(r"\b(?:to|with|ask|tell|visit)\s+((?:[a-z'-]+\s+){0,3}[a-z'-]+)", t):
        for w in m.group(1).split():
            if w in ('the', 'a', 'an') or w in _PALABRAS_COMUNES:
                continue
            if w in _NOMBRES_NPC:
                return False
            break
    return None


def interactuar_npc(ses, npc_nombre: str, entidad: int = 0) -> tuple:
    """
    Gestiona la conversacion o entrega de misiones con un NPC.
    Devuelve (procesado: bool, tipo: str, datos: dict)
    """
    _cargar_db()
    p = getattr(ses, 'personaje', None)
    if not p:
        return (False, 'sin_personaje', {})

    nom_clean = npc_nombre.strip().lower()

    # 0. Proteger tutorial de Guide Palace (51), Fighting Palace (57) y eleccion de faccion
    stage = getattr(p, 'stage', 0)
    if stage in (51, 57) or nom_clean in (
        'angel raphael', 'director wolay',
        'angel of aurora', 'angel of beast', 'angel of iron', 'angel of shadow',
        'guardian angel',
        'aurora angel', 'dark city angel', 'ironcastle angel', 'breezewood angel',
    ):
        return (False, 'tutorial', {})

    # 1. Comprobar si el jugador tiene una misión activa que requiera hablar con este NPC
    for q, pa in list(p.quests or []):
        if mision_completada(p, q):
            continue
        # Quest 102 (Accumulation schedule of students' grades) se completa unicamente
        # mediante graduacion con Angel Tutor cuando los creditos son >= 5.
        # Quest 103 (Choosing country) se completa al elegir faccion en Graduation Palace.
        if q in (102, 103):
            continue
        if q in MISIONES_ALUMNO and es_graduado(p):
            continue
        info = info_mision(q)
        pasos = info.get('pasos', [])
        idx_paso = pa - 1 if 0 < pa <= len(pasos) else 0
        paso_actual = pasos[idx_paso] if idx_paso < len(pasos) else None

        if paso_actual:
            npc_target = (paso_actual.get('npc_entrega') or paso_actual.get('npc') or '').strip().lower()
            if not npc_target:
                npc_target = (info.get('npc_inicio') or '').strip().lower()

            target_norm = normalizar_nombre_npc(npc_target)
            nom_norm = normalizar_nombre_npc(nom_clean)

            _coincide_compilado = bool(npc_target) and (
                npc_target == nom_clean or nom_clean in npc_target or npc_target in nom_clean
                or target_norm == nom_norm or (target_norm and target_norm in nom_norm)
                or (nom_norm and nom_norm in target_norm))
            # El texto del paso manda sobre el NPC compilado (ver
            # npc_segun_texto): None si el texto no nombra a nadie.
            _por_texto = npc_segun_texto(paso_actual.get('texto'), nom_clean)
            if (_por_texto is True) or (_por_texto is None and _coincide_compilado):
                tipo_obj = paso_actual.get('tipo', 'hablar')
                k_rec = f"{q}_{pa}"

                # Objetivo de recoleccion (o paso con items requeridos)
                if tipo_obj == 'recolectar' or k_rec in _RECOLECCIONES:
                    if not verificar_entrega_items(ses, q, pa):
                        return (True, 'recoleccion_incompleta', {'qid': q, 'paso': pa, 'nom_npc': npc_nombre})

                # Objetivo de caceria
                elif tipo_obj == 'matar':
                    req = paso_actual.get('cantidad', 1)
                    kills = (getattr(ses, 'quest_kills', {}) or {}).get((q, pa), 0)
                    if kills < req:
                        ses.enviar(_cl.aviso(f"Defeat targets first! ({kills}/{req})", tipo=0, msg_id=_cl.MSG_TEXTO))
                        return (True, 'caceria_incompleta', {'qid': q, 'paso': pa, 'nom_npc': npc_nombre})
                    if hasattr(ses, 'quest_kills') and (q, pa) in ses.quest_kills:
                        del ses.quest_kills[(q, pa)]

                # Avanzar o completar (encadenando pasos consecutivos de 'hablar' con este mismo NPC)
                cur_pa = pa
                while True:
                    idx_cur = cur_pa - 1
                    if idx_cur >= len(pasos):
                        completar_mision(ses, q)
                        return (True, 'completada', {'qid': q, 'paso': cur_pa, 'nom_npc': npc_nombre})
                    p_cur = pasos[idx_cur]
                    es_ult = p_cur.get('es_ultimo', False) or (cur_pa >= len(pasos))
                    if es_ult:
                        completar_mision(ses, q)
                        return (True, 'completada', {'qid': q, 'paso': cur_pa, 'nom_npc': npc_nombre})

                    sig = p_cur.get('siguiente_paso', cur_pa + 1)
                    sig_idx = sig - 1
                    if sig_idx < len(pasos):
                        sig_p = pasos[sig_idx]
                        sig_npc = (sig_p.get('npc_entrega') or sig_p.get('npc') or '').strip().lower()
                        sig_norm = normalizar_nombre_npc(sig_npc)
                        sig_tipo = sig_p.get('tipo', 'hablar')
                        if sig_tipo == 'hablar' and (not sig_npc or sig_npc == nom_clean or nom_clean in sig_npc or sig_npc in nom_clean or sig_norm == nom_norm or (sig_norm and sig_norm in nom_norm)):
                            # El paso siguiente es hablar con este mismo NPC: avanzamos internamente y seguimos la cadena
                            avanzar_paso(ses, q, sig)
                            cur_pa = sig
                            continue

                    avanzar_paso(ses, q, sig)
                    return (True, 'avanzada', {'qid': q, 'paso': cur_pa, 'nuevo_paso': sig, 'nom_npc': npc_nombre})

    return (False, 'sin_accion', {})


def obtener_mapa_instancia(qid: int, paso: int = 1) -> int:
    """Devuelve el stage_id si la mision requiere entrar a una instancia o mapa especial."""
    if (qid, paso) in QUEST_MAPAS_INSTANCIA:
        return QUEST_MAPAS_INSTANCIA[(qid, paso)]
    return None
