"""Verified House System core state and packet builders.

Mechanics whose formulas have not been measured (pet training, balls,
hammers, and similar systems) are intentionally not described as complete.
"""
import json
import logging
import math
import os
import pathlib
import random
import struct
import time

log = logging.getLogger(__name__)

# Ranuras de inventario
SLOT_DEED = 376
SLOT_FURN_INI = 377
SLOT_FURN_FIN = 476
SLOT_PET_INI = 477
SLOT_PET_FIN = 486
SLOT_MOB_INI = 487
SLOT_MOB_FIN = 496

# Mapas de exhibicion autorizados: Area de Casas de Angeles, ciudades de facciones y Palm Base
MAPAS_EXHIBICION = frozenset((370, 3, 26, 29, 38, 88))
STAGE_HOUSE = 500

# Valores de los propios item*.xml del cliente IGG (dinamica1/descripcion).
# Cuanto limpia cada jabon: el 動態資料1 de item.xml (formula de uso 18).
# El Super Liquid Soap (10626) da 2500, no 500 como estaba.
SOAP_CLEAN = {10627: 10, 10603: 500, 10626: 2500, 15163: 500, 20077: 500}
# Tope del indice de limpieza. Era 1000 y con eso el Super Liquid Soap se
# quedaba en nada; el campo del 0x0149 es un u16.
MAX_LIMPIEZA = 5000
BALL_TICKETS = {
    9953: {'type': 1, 'fast': False}, 20078: {'type': 1, 'fast': False},
    15235: {'type': 1, 'fast': True}, 15236: {'type': 2, 'fast': True},
    16598: {'type': 2, 'fast': False}, 28867: {'type': 2, 'fast': False},
}

# Limites de colocacion segun tamano (0..6)
CAPACIDAD_MUEBLES = [35, 60, 100, 120, 140, 160, 180]

# Umbrales de Magia para Nivel de Casa 1..15
UMBRALES_NIVEL = [
    0, 500, 900, 1500, 2700, 4500, 9000, 15000, 27000,
    40000, 48000, 56000, 64000, 72000, 84000
]

# Modos de slots por nivel
def ranuras_mascotas_validas(nivel: int) -> int:
    if nivel >= 14: return 6
    if nivel >= 12: return 5
    if nivel >= 9: return 4
    if nivel >= 7: return 3
    if nivel >= 4: return 2
    return 1

def ranuras_mobgen_validas(nivel: int) -> int:
    if nivel >= 13: return 3
    if nivel >= 8: return 2
    return 1

_DATOS = None
_MUEBLES_POR_ID = None

def _cargar_datos():
    global _DATOS, _MUEBLES_POR_ID
    if _DATOS is None:
        p = pathlib.Path(__file__).parent / 'plantillas' / 'casas.json'
        try:
            _DATOS = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            _DATOS = {'muebles': [], 'item_to_furn': {}, 'furn_to_item': {}}
        _MUEBLES_POR_ID = {
            int(m['id']): m for m in _DATOS.get('muebles', [])
            if isinstance(m, dict) and m.get('id') is not None
        }
    return _DATOS

def tabla() -> list:
    return _cargar_datos().get('muebles', [])

DEED_ITEMS = frozenset((10115, 10116, 10117, 17934, 17935, 17936, 17937, 20076))

def es_deed_item(item_id: int) -> bool:
    return int(item_id or 0) in DEED_ITEMS

def mueble(mid: int):
    _cargar_datos()
    return _MUEBLES_POR_ID.get(int(mid))

def item_a_mueble(item_id: int) -> int:
    if int(item_id or 0) in DEED_ITEMS:
        return None
    d = _cargar_datos().get('item_to_furn', {})
    return d.get(str(item_id)) or d.get(int(item_id))

def mueble_a_item(furn_id: int) -> int:
    d = _cargar_datos().get('furn_to_item', {})
    return d.get(str(furn_id)) or d.get(int(furn_id))

def mueble_a_modelo(furn_id: int) -> int:
    d = _cargar_datos().get('furn_to_model', {})
    return d.get(str(furn_id)) or d.get(int(furn_id)) or 7807


def ficha_por_item(item_id: int):
    """Return the furniture.xml row referenced by an inventory item."""
    fid = item_a_mueble(item_id)
    return mueble(fid) if fid is not None else None


def es_escena_item(item_id: int) -> bool:
    ficha = ficha_por_item(item_id)
    param = str((ficha or {}).get('param1') or '').replace('/', '\\').lower()
    return param.startswith('map\\') and param.endswith('.mpc')


def es_estilo_exterior_item(item_id: int) -> bool:
    fid = item_a_mueble(item_id)
    if fid is None:
        return False
    modelos = _cargar_datos().get('furn_to_model', {})
    return str(fid) in modelos or fid in modelos


def normalizar_entrada_mueble(entry: dict) -> dict:
    """Normalize the exact 24-byte furniture record to JSON-safe values."""
    return {
        'item_id': max(0, int(entry.get('item_id', 0))),
        'item_uid': max(0, int(entry.get('item_uid', 0))),
        'dir': max(0, min(255, int(entry.get('dir', 0)))),
        'x': max(0, min(65535, int(entry.get('x', 0)))),
        'y': max(0, min(65535, int(entry.get('y', 0)))),
        'state': max(0, min(255, int(entry.get('state', 0)))),
        'extra': max(0, min(65535, int(entry.get('extra', 0)))),
        'expire': max(0, min(0xffffffff, int(entry.get('expire', 0)))),
    }


_FURNITURE_RECORD = struct.Struct('<IQBHHBHI')


def parse_save_layout(body: bytes):
    """Decode C2S 0x013B.

    The live Global capture uses a 37-byte header: ``u32 count`` followed by
    a 33-byte house-name/options area.  Older IGG client analysis described a
    21-byte variant.  Accept both layouts, but only when the packet length is
    exact, so malformed data can never shift furniture records silently.
    """
    if len(body) < 4:
        raise ValueError('savefurniture body too short')
    count = struct.unpack_from('<I', body, 0)[0]
    header = next((n for n in (37, 21)
                   if len(body) == n + count * _FURNITURE_RECORD.size), None)
    if header is None:
        raise ValueError(
            f'invalid savefurniture length: count={count} body={len(body)}')
    name = body[4:header].split(b'\x00', 1)[0].decode(
        'latin-1', 'replace').strip()
    entries = []
    off = header
    for _ in range(count):
        iid, uid, direction, x, y, state, extra, expire = (
            _FURNITURE_RECORD.unpack_from(body, off))
        entries.append(normalizar_entrada_mueble({
            'item_id': iid,
            'item_uid': uid,
            'dir': direction,
            'x': x,
            'y': y,
            'state': state,
            'extra': extra,
            'expire': expire,
        }))
        off += _FURNITURE_RECORD.size
    return name, entries

def nivel_de_magia(magia: int) -> int:
    lv = 1
    for i, req in enumerate(UMBRALES_NIVEL):
        if magia >= req:
            lv = i + 1
        else:
            break
    return min(15, lv)

def info_nivel(magia: int):
    lv = nivel_de_magia(magia)
    prev_req = UMBRALES_NIVEL[lv - 1] if lv - 1 < len(UMBRALES_NIVEL) else 0
    next_req = UMBRALES_NIVEL[lv] if lv < len(UMBRALES_NIVEL) else UMBRALES_NIVEL[-1]
    return lv, prev_req, next_req

def puntos_de(puestos) -> int:
    total = 0
    for mid in (puestos or []):
        m = mueble(mid)
        if m:
            try:
                total += int(m.get('puntos') or 0)
            except (TypeError, ValueError):
                pass
    return total

def por_categoria() -> dict:
    out = {}
    for m in tabla():
        out.setdefault(m.get('categoria') or '?', []).append(m)
    return out

def pkt_cambiar_mapa_house(stage_id: int, house_table_id: int = 0, house_size_level: int = 0) -> bytes:
    # Desensamblado en sub_649C70 / sub_5BB7B0:
    # +2:  DWORD stage_id
    # +24: DWORD house_table_id (sub_4DC070 id de furniture.xml con categoria 10 para mapa exterior)
    # +28: BYTE house_size_level (0..6 tamano de casa, activa constructor de paredes/suelo en tag 101)
    body = struct.pack('<HI18sIBB', 0x000C, int(stage_id), bytes(18), int(house_table_id), int(house_size_level), 0)
    return body

def pkt_open_close_state(is_open: bool) -> bytes:
    return struct.pack('<HB', 0x0142, 1 if is_open else 0)

def pkt_outdoor_house(entity_id: int, model_id: int, px_x: int, px_y: int,
                      house_name: str, owner_name: str,
                      dir_rot: int = 0, house_size_level: int = 0,
                      flags: int = 0, marca: int = 0, house_level: int = 1) -> bytes:
    nom_bytes = house_name.encode('latin-1', 'replace')[:16].ljust(16, b'\x00')
    owner_bytes = owner_name.encode('latin-1', 'replace')[:17].ljust(17, b'\x00')
    body = struct.pack('<HIIii16sBBIHHBB17sBB',
                       0x0140,
                       int(entity_id),
                       int(flags),
                       int(px_x),
                       int(px_y),
                       nom_bytes,
                       int(marca),
                       int(dir_rot),
                       int(model_id),
                       0, 0, 0,
                       0,
                       owner_bytes,
                       max(1, min(15, int(house_level))),
                       max(0, min(6, int(house_size_level))))
    return body

def pkt_indoor_furniture_obj(entity_id: int, model_id: int, px_x: int, px_y: int,
                             name: str = '', dir_rot: int = 0, flags: int = 0) -> bytes:
    nom_bytes = name.encode('latin-1', 'replace')[:16].ljust(16, b'\x00')
    body = struct.pack('<HIIii16sBBIHHBI',
                       0x0143,
                       int(entity_id),
                       int(flags),
                       int(px_x),
                       int(px_y),
                       nom_bytes,
                       0,
                       int(dir_rot),
                       int(model_id),
                       0, 0, 0,
                       0)
    return body

def pkt_enter_furnish_mode(house_name: str, furniture_list: list) -> bytes:
    # S2C 0x013E: offset +7 es la cadena de 17 bytes con la que sub_5F9150
    # inicializa la caja de texto editable 27084 (House Name).
    nom_bytes = str(house_name or '').encode('latin-1', 'replace')[:17].ljust(17, b'\x00')
    count = len(furniture_list)
    hdr = struct.pack('<HBI17s', 0x013E, 1, count, nom_bytes)
    entries = []
    for f in furniture_list:
        entries.append(struct.pack('<IQBHHBHI',
                                   int(f.get('item_id', 0)),
                                   int(f.get('item_uid', 0)),
                                   int(f.get('dir', 0)),
                                   int(f.get('x', 0)),
                                   int(f.get('y', 0)),
                                   int(f.get('state', 0)),
                                   int(f.get('extra', 0)),
                                   int(f.get('expire', 0))))
    return hdr + b''.join(entries)

def pkt_leave_furnish_mode() -> bytes:
    return struct.pack('<HB', 0x013E, 0)

def pkt_visit_furniture_sync(furniture_list: list) -> bytes:
    count = len(furniture_list)
    hdr = struct.pack('<HI', 0x013F, count)
    entries = []
    for f in furniture_list:
        entries.append(struct.pack('<IQBHHBHI',
                                   int(f.get('item_id', 0)),
                                   int(f.get('item_uid', 0)),
                                   int(f.get('dir', 0)),
                                   int(f.get('x', 0)),
                                   int(f.get('y', 0)),
                                   int(f.get('state', 0)),
                                   int(f.get('extra', 0)),
                                   int(f.get('expire', 0))))
    return hdr + b''.join(entries)

def pkt_pet_slot_wnd(is_open: bool, valid_slots: int, radio_bitfield: int) -> bytes:
    return struct.pack('<HBBI', 0x0144, 1 if is_open else 0, min(10, max(0, valid_slots)), int(radio_bitfield))

def pkt_mobgen_slot_wnd(is_open: bool, valid_slots: int) -> bytes:
    return struct.pack('<HBB', 0x0145, 1 if is_open else 0, min(10, max(0, valid_slots)))

def pkt_open_cast_vote(owner_name: str) -> bytes:
    nom_bytes = owner_name.encode('latin-1', 'replace')[:17].ljust(17, b'\x00')
    return struct.pack('<H17s', 0x0146, nom_bytes)

def pkt_view_vote_notes(page: int, total_notes: int, notes_list: list) -> bytes:
    entry_count = len(notes_list)
    hdr = struct.pack('<HHIB', 0x0147, int(page), int(total_notes), int(entry_count))
    entries = []
    for n in notes_list:
        s_name = n.get('sender_name', '').encode('latin-1', 'replace')[:20].ljust(20, b'\x00')
        txt = n.get('text', '').encode('latin-1', 'replace')[:132].ljust(132, b'\x00')
        entries.append(struct.pack('<I20sI132s',
                                   int(n.get('sender_id', 0)),
                                   s_name,
                                   int(n.get('timestamp', 0)),
                                   txt))
    return hdr + b''.join(entries)

def pkt_request_password(target_obj_id: int) -> bytes:
    return struct.pack('<HI', 0x0148, int(target_obj_id))

def pkt_house_info(house_level: int, magic_cur: int, magic_next: int, magic_prev: int,
                   bonus_pct: int, cleanliness: int, votes_total: int, votes_today: int,
                   visitors: int, votes_remaining: int, rank: int, ui_state: int = 1) -> bytes:
    """S2C 0x0149 (38 bytes). Offset +37 controla el estado de botones de WND_HOUSEINFO:
    10 = Casa colocada en mapa exterior (activa Decorate 27627 y Take Back 27628)
    1  = Casa guardada / modo muestra (activa Show 27626)
    0  = Deshabilita los 3 botones
    """
    return struct.pack('<HIIIIHHIIIBHB',
                       0x0149,
                       int(house_level),
                       int(magic_cur),
                       int(magic_next),
                       int(magic_prev),
                       int(bonus_pct),
                       int(cleanliness),
                       int(votes_total),
                       int(votes_today),
                       int(visitors),
                       int(votes_remaining),
                       int(rank),
                       int(ui_state))

def pkt_house_name(house_name: str) -> bytes:
    # IGG sub_5EFE80 copies exactly 16 bytes from packet offset +2.
    nom_bytes = house_name.encode('latin-1', 'replace')[:16].ljust(16, b'\x00')
    return struct.pack('<H16s', 0x014A, nom_bytes)

def pkt_hitparade_data(rtype: int, page: int, count: int, entries: list) -> bytes:
    hdr = struct.pack('<HBIH', 0x014B, int(rtype), int(page), int(count))
    body = []
    for e in entries:
        nom = e.get('name', '').encode('latin-1', 'replace')[:16].ljust(17, b'\x00')
        body.append(struct.pack('<II17sQ',
                                int(e.get('val1', 0)),
                                int(e.get('val2', 0)),
                                nom,
                                int(e.get('score', 0))))
    return hdr + b''.join(body)

def pkt_billboard_data(btype: int, count: int, entries: list) -> bytes:
    hdr = struct.pack('<HBH', 0x014C, int(btype), int(count))
    body = []
    for e in entries:
        nom = e.get('owner_name', '').encode('latin-1', 'replace')[:20].ljust(20, b'\x00')
        body.append(struct.pack('<I20sII',
                                int(e.get('owner_id', 0)),
                                nom,
                                int(e.get('col1', 0)),
                                int(e.get('col2', 0))))
    return hdr + b''.join(body)

def pkt_remove_furniture(item_uid: int) -> bytes:
    return struct.pack('<HQ', 0x014D, int(item_uid))

# Gestor de Casas en Memoria y Mundo
class CasaData:
    def __init__(self, owner_id: int, owner_name: str, deed_id: int = 10115):
        self.owner_id = int(owner_id)
        self.owner_name = owner_name
        self.deed_id = int(deed_id)
        self.house_name = f"{owner_name}'s House"
        self.password_md5 = ""
        self.cleanliness = 0
        self.clean_online_remainder = 0.0
        self._bonus_pct = 0
        self.votes_total = 0
        self.votes_today = 0
        self.visitors_total = 0
        self.options = 0
        self.ball_active = False
        self.ball_start_time = 0
        self.ball_end_time = 0
        self.ball_cooldown_until = 0
        self.ball_type = 0 # 1=EXP, 2=Skill EXP
        self.ball_mult = 1.0
        self.pet_radio = 0
        self.care_pets = {} # dict of slot str -> {'item_id': id, 'slot': slot, 'start_time': t, 'exp': exp}
        self.placed_furniture = [] # list of dicts: item_id, item_uid, dir, x, y, state, extra, expire
        self.vote_notes = [] # list of dicts: sender_id, sender_name, timestamp, text
        self.voted_users_today = set()
        self.last_clean_day = time.strftime('%Y-%m-%d')
        self.last_blessing_day = ''
        self.last_vote_day = time.strftime('%Y-%m-%d')
        self.outdoor_obj_id = 0
        self.outdoor_stage = 0
        self.outdoor_px = (0, 0)
        self.outdoor_dir = 0
        self.is_open = False

    @property
    def bonus_pct(self) -> int:
        from house_services import clean_bonus
        return clean_bonus(self.cleanliness)

    @bonus_pct.setter
    def bonus_pct(self, val: int):
        self._bonus_pct = int(val)

    def check_daily_reset(self):
        hoy = time.strftime('%Y-%m-%d')
        if self.last_vote_day != hoy:
            self.last_vote_day = hoy
            self.votes_today = 0
            self.voted_users_today.clear()
        if self.last_clean_day != hoy:
            self.last_clean_day = hoy
        if self.ball_active and self.ball_end_time <= int(time.time()):
            self.ball_active = False
            self.ball_end_time = 0
            self.ball_type = 0
            self.ball_mult = 1.0

    def avanzar_tiempo_conectado(self, seconds):
        """Consume only this owner's online time, preserving partial intervals."""
        from house_services import CLEAN_SECONDS_PER_POINT
        self.clean_online_remainder += max(0.0, float(seconds))
        points, self.clean_online_remainder = divmod(
            self.clean_online_remainder, CLEAN_SECONDS_PER_POINT)
        old = self.cleanliness
        self.cleanliness = max(0, old - int(points))
        return self.cleanliness != old

    def iniciar_baile(self, ticket_id: int, now: int = None):
        """Activa una fiesta usando los tiempos publicados por el item IGG o configurados."""
        cfg = BALL_TICKETS.get(int(ticket_id))
        now = int(time.time() if now is None else now)
        if not cfg or self.level < 1 or self.ball_active or now < self.ball_cooldown_until:
            return False
        import configuracion as _cfg_b
        cd_custom = getattr(_cfg_b, 'COOLDOWN_BAILE_SEGUNDOS', None)
        if cd_custom is not None:
            self.ball_cooldown_until = now + int(cd_custom)
        else:
            cooldown_days = 3.0 if self.level >= 8 else 3.5
            if cfg.get('fast'):
                cooldown_days /= 2.0
            self.ball_cooldown_until = now + int(cooldown_days * 86400)
        prep_s = int(getattr(_cfg_b, 'TIEMPO_PREPARACION_BAILE_SEGUNDOS', 180))
        self.ball_active = True
        self.ball_start_time = now + prep_s
        self.ball_end_time = self.ball_start_time + 3600
        self.ball_type = int(cfg['type'])
        self.ball_mult = 1.5 if cfg.get('fast') else 2.0
        return True

    @property
    def size_level(self) -> int:
        d_map = {10115: 0, 10116: 1, 10117: 2, 17934: 3, 17935: 4, 17936: 5, 17937: 6, 20076: 0}
        if self.deed_id in d_map:
            return d_map[self.deed_id]
        d = item_a_mueble(self.deed_id)
        if d is not None:
            return max(0, min(6, int(d)))
        return 0

    @property
    def _legacy_exterior_table_id(self) -> int:
        for f in self.placed_furniture:
            mid = f.get('item_id', 0)
            m = mueble(mid)
            if m and m.get('categoria') == '屋外景觀':
                return mid
        return 0

    @property
    def _legacy_model_id(self) -> int:
        for f in self.placed_furniture:
            mid = f.get('item_id', 0)
            m = mueble(mid)
            if m and m.get('categoria') == '小屋外觀':
                mod = mueble_a_modelo(mid)
                if mod:
                    return mod
        d_map = {10115: 7807, 10116: 7806, 10117: 7805, 17934: 7848, 17935: 7849, 17936: 7850, 17937: 7851, 20076: 7807}
        return d_map.get(self.deed_id, 7807)

    def _legacy_calcular_magia(self) -> int:
        total = 0
        for f in self.placed_furniture:
            mid = f.get('item_id', 0)
            m = mueble(mid)
            if m:
                total += int(m.get('puntos', 0) or 0)
        return total

    @property
    def level(self) -> int:
        return nivel_de_magia(self.calcular_magia())

    # These definitions intentionally supersede the mojibake category checks
    # above.  The stable XML fields are the item->furniture relation, param1,
    # and the explicit furniture->model table.
    @property
    def exterior_table_id(self) -> int:
        for f in self.placed_furniture:
            item_id = int(f.get('item_id', 0))
            if es_escena_item(item_id):
                return int(item_a_mueble(item_id) or 0)
        # Sin decoracion de exterior colocada, el mapa de fondo es 0 (vacio)
        return 0

    @property
    def capacidad_maxima(self) -> int:
        sz = self.size_level
        if 0 <= sz < len(CAPACIDAD_MUEBLES):
            return CAPACIDAD_MUEBLES[sz]
        return 35

    @property
    def model_id(self) -> int:
        for f in self.placed_furniture:
            item_id = int(f.get('item_id', 0))
            if es_estilo_exterior_item(item_id):
                return int(mueble_a_modelo(item_a_mueble(item_id)))
        d_map = {10115: 7807, 10116: 7806, 10117: 7805, 17934: 7848,
                 17935: 7849, 17936: 7850, 17937: 7851, 20076: 7807}
        return d_map.get(self.deed_id, 7807)

    def calcular_magia(self) -> int:
        total = 0
        for f in self.placed_furniture:
            ficha = ficha_por_item(f.get('item_id', 0))
            if ficha:
                total += int(ficha.get('puntos', 0) or 0)
        return total

    def serializar(self) -> dict:
        return {
            'owner_id': self.owner_id,
            'owner_name': self.owner_name,
            'deed_id': self.deed_id,
            'house_name': self.house_name,
            'password_md5': self.password_md5,
            'cleanliness': self.cleanliness,
            'clean_online_remainder': self.clean_online_remainder,
            'bonus_pct': self.bonus_pct,
            'votes_total': self.votes_total,
            'votes_today': self.votes_today,
            'visitors_total': self.visitors_total,
            'options': self.options,
            'pet_radio': self.pet_radio,
            'care_pets': dict(self.care_pets),
            'placed_furniture': [normalizar_entrada_mueble(x)
                                 for x in self.placed_furniture],
            'vote_notes': list(self.vote_notes),
            'voted_users_today': list(self.voted_users_today),
            'last_clean_day': self.last_clean_day,
            'last_blessing_day': self.last_blessing_day,
            'last_vote_day': self.last_vote_day,
            'ball_active': self.ball_active,
            'ball_start_time': self.ball_start_time,
            'ball_end_time': self.ball_end_time,
            'ball_cooldown_until': self.ball_cooldown_until,
            'ball_type': self.ball_type,
            'ball_mult': self.ball_mult,
            'is_open': self.is_open,
            'outdoor_stage': self.outdoor_stage,
            'outdoor_px': list(self.outdoor_px),
            'outdoor_dir': self.outdoor_dir
        }

    @classmethod
    def deserializar(cls, data: dict):
        if not data:
            return None
        c = cls(data.get('owner_id', 0), data.get('owner_name', ''), data.get('deed_id', 10115))
        c.house_name = data.get('house_name', c.house_name)
        c.password_md5 = data.get('password_md5', '')
        c.cleanliness = int(data.get('cleanliness', 0))
        c.clean_online_remainder = max(0.0, float(data.get('clean_online_remainder', 0)))
        c.bonus_pct = int(data.get('bonus_pct', 0))
        c.votes_total = int(data.get('votes_total', 0))
        c.votes_today = int(data.get('votes_today', 0))
        c.visitors_total = int(data.get('visitors_total', 0))
        c.options = int(data.get('options', 0))
        c.pet_radio = int(data.get('pet_radio', 0))
        c.care_pets = dict(data.get('care_pets') or {})
        c.placed_furniture = [normalizar_entrada_mueble(x)
                              for x in data.get('placed_furniture', [])
                              if isinstance(x, dict) and item_a_mueble(x.get('item_id', 0))]
        c.vote_notes = list(data.get('vote_notes', []))
        c.voted_users_today = set(data.get('voted_users_today', []))
        c.last_clean_day = data.get('last_clean_day', c.last_clean_day)
        c.last_blessing_day = data.get('last_blessing_day', '')
        c.last_vote_day = data.get('last_vote_day', c.last_vote_day)
        c.ball_active = bool(data.get('ball_active', False))
        c.ball_start_time = int(data.get('ball_start_time', 0))
        c.ball_end_time = int(data.get('ball_end_time', 0))
        c.ball_cooldown_until = int(data.get('ball_cooldown_until', 0))
        c.ball_type = int(data.get('ball_type', 0))
        c.ball_mult = float(data.get('ball_mult', 1.0))
        c.is_open = bool(data.get('is_open', False))
        c.outdoor_stage = int(data.get('outdoor_stage', 0))
        c.outdoor_px = tuple(data.get('outdoor_px', (0, 0)))
        c.outdoor_dir = int(data.get('outdoor_dir', 0))
        return c

    to_dict = serializar
    from_dict = deserializar

_CASAS_ACTIVAS = {}
_OBJ_A_CASA = {}
_OUTDOOR_ID_GEN = 600000


def _vincular_propietario(casa, owner_id, owner_name):
    """The character row/cache key owns the house, including legacy saves."""
    old_name = casa.owner_name or ''
    placeholder = f'Owner_{int(owner_id)}'
    name = str(owner_name or old_name)
    # Visitor/ranking lookups sometimes know only the ID. They must not
    # replace the real owner's name with a generated display placeholder.
    if name == placeholder and old_name:
        name = old_name
    if not casa.house_name or casa.house_name in (
            "'s House", f"{old_name}'s House", f"{placeholder}'s House"):
        casa.house_name = f"{name}'s House"
    casa.owner_id = int(owner_id)
    casa.owner_name = name


def obtener_o_crear_casa(owner_id: int, owner_name: str, deed_id: int = 10115, raw_data: dict = None) -> CasaData:
    cid = int(owner_id)
    if cid in _CASAS_ACTIVAS:
        c = _CASAS_ACTIVAS[cid]
        _vincular_propietario(c, cid, owner_name)
        c.check_daily_reset()
        return c
    if raw_data:
        c = CasaData.deserializar(raw_data)
        if c:
            _vincular_propietario(c, cid, owner_name)
            # Migration from the original minimal schema: it stored only
            # furniture.xml ids and no placement metadata.
            if not c.placed_furniture and raw_data.get('muebles'):
                for fid in raw_data.get('muebles', []):
                    item_id = mueble_a_item(int(fid))
                    if item_id:
                        c.placed_furniture.append(normalizar_entrada_mueble({
                            'item_id': item_id, 'item_uid': 0,
                        }))
            c.check_daily_reset()
            _CASAS_ACTIVAS[cid] = c
            return c
    c = CasaData(cid, owner_name, deed_id)
    c.check_daily_reset()
    _CASAS_ACTIVAS[cid] = c
    return c

def casa_por_obj(obj_id: int) -> CasaData:
    return _OBJ_A_CASA.get(int(obj_id))

TORNADOS_EXHIBICION = {
    370: [(22, 5)],
    3: [(346, 20), (39, 186)],
    26: [(7, 9), (211, 111)],
    29: [(323, 182), (4, 18)],
    38: [(34, 2), (336, 170)],
    88: [(154, 39), (9, 117), (296, 92), (223, 83)],
}

_NPCS_EXHIBICION = None

def _cargar_npcs_exhibicion():
    global _NPCS_EXHIBICION
    if _NPCS_EXHIBICION is not None:
        return _NPCS_EXHIBICION
    _NPCS_EXHIBICION = {}
    plantillas_archivos = {
        370: 'angel_house_area.json',
        3: 'aurora_city.json',
        26: 'dark_city.json',
        29: 'breeze_woods.json',
        38: 'iron_castle.json',
        88: 'palm_base.json',
    }
    pdir = pathlib.Path(__file__).parent / 'plantillas'
    for st, fname in plantillas_archivos.items():
        coords = set()
        fpath = pdir / fname
        if fpath.exists():
            try:
                d = json.loads(fpath.read_text(encoding='utf-8'))
                for s in d.get('spawns', []):
                    if not s.get('monstruo') and s.get('tile'):
                        coords.add((int(s['tile'][0]), int(s['tile'][1])))
            except Exception:
                pass
        _NPCS_EXHIBICION[st] = coords
    return _NPCS_EXHIBICION


# Zonas amplias exteriores permitidas para exhibicion de casas en ciudades y bases.
# Fuera de estas cajas delimitadoras estan los edificios/domos, pasillos estrechos,
# puentes y periferias que no admiten casas.
ZONAS_OUTDOOR_PERMITIDAS = {
    # Angel House Area: Toda el area residencial es apta (excepto portal y bordes)
    370: [(6, 6, 103, 58)],
    # Aurora City: Gran plaza central abierta de adoquines amarillos (excluye aceras, cafes y edificios)
    3: [(130, 75, 195, 135)],
    # Dark City: Gran plaza y bulevar central
    26: [(135, 65, 255, 135)],
    # Breeze Woods: Gran isla verde central
    29: [(160, 90, 265, 145)],
    # Iron Castle: Patio central de acero
    38: [(135, 60, 265, 130)],
    # Palm Base: Gran zona de dunas centrales y playas abiertas
    88: [(90, 65, 220, 125), (125, 120, 175, 145), (15, 15, 50, 45)],
}

# Estructuras cerradas o interiores que deben excluirse explicitamente
ZONAS_OUTDOOR_EXCLUIDAS = {
    # Dark City: Monumento central de agua y plataforma
    26: [(175, 80, 205, 102)],
    # Iron Castle: Carpas cerradas del banco
    38: [(135, 140, 165, 155)],
    # Palm Base: Domo del Ocean Scholar (278, 138) y domo de Bankclerk Clair
    88: [(260, 115, 300, 160), (170, 125, 210, 160)],
}


def validar_posicion_outdoor(stage: int, tile_x: int, tile_y: int,
                             exclude_cid: int = 0) -> tuple[bool, str]:
    """Valida si una casa exterior se puede colocar en esa coordenada del mapa."""
    st = int(stage)
    tx = int(tile_x)
    ty = int(tile_y)

    # 1. Solo mapas de exhibicion autorizados (bloquea interiores, casa stage 500, etc.)
    if st not in MAPAS_EXHIBICION:
        return False, "Houses can only be placed in Angel House Area, faction cities, or Palm Base."

    # 2. Margen de bordes del mapa (minimo 6 casillas hacia adentro)
    try:
        import transitable as _tr
        m = _tr._cargar().get(st)
        if m:
            w, h, _ = m
            if tx < 6 or tx > w - 7 or ty < 6 or ty > h - 7:
                return False, "Cannot place house too close to map borders."
    except Exception:
        pass

    # 3. Delimitacion de zonas exteriores abiertas (prohibe colocar dentro de casas, domos o edificios)
    zonas = ZONAS_OUTDOOR_PERMITIDAS.get(st)
    if zonas:
        en_zona = any(x1 <= tx <= x2 and y1 <= ty <= y2 for x1, y1, x2, y2 in zonas)
        en_excl = any(x1 <= tx <= x2 and y1 <= ty <= y2 for x1, y1, x2, y2 in ZONAS_OUTDOOR_EXCLUIDAS.get(st, []))
        if not en_zona or en_excl:
            return False, "Houses require a wide open area (cannot be placed inside buildings, on bridges, stairs, or narrow paths)."

    # 4. Distancia a portales / tornados (minimo 7 casillas)
    for px, py in TORNADOS_EXHIBICION.get(st, []):
        if max(abs(tx - px), abs(ty - py)) < 7:
            return False, "Cannot place house too close to a portal or entrance."

    # 5. Espacio amplio despejado: huella de 5x5 casillas totalmente transitable
    # (descarta puentes estrechos, escaleras, arboles densos, pasillos y esquinas)
    try:
        import transitable as _tr
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if not _tr.se_pisa(st, tx + dx, ty + dy):
                    return False, "Houses require a wide open area (cannot be placed on bridges, stairs, near trees, or narrow paths)."
    except Exception:
        pass

    # 5. Distancia a NPCs interactivos / tiendas / tablones (minimo 5 casillas)
    npcs = _cargar_npcs_exhibicion().get(st, set())
    for nx, ny in npcs:
        if max(abs(tx - nx), abs(ty - ny)) < 5:
            return False, "Cannot place house too close to NPCs."

    # 6. Distancia a otras casas exteriores ya colocadas (minimo 4 casillas)
    for c in casas_en_stage(st):
        if c.owner_id == exclude_cid:
            continue
        ox = c.outdoor_px[0] // 32
        oy = c.outdoor_px[1] // 32
        if max(abs(tx - ox), abs(ty - oy)) < 4:
            return False, "Cannot place house: location is too close to another house."

    return True, ""


def registrar_casa_outdoor(casa: CasaData, stage: int, px_x: int, px_y: int, dir_rot: int = 0):
    global _OUTDOOR_ID_GEN
    if casa.outdoor_obj_id in _OBJ_A_CASA:
        del _OBJ_A_CASA[casa.outdoor_obj_id]
    _OUTDOOR_ID_GEN += 1
    casa.outdoor_obj_id = _OUTDOOR_ID_GEN
    casa.outdoor_stage = int(stage)
    casa.outdoor_px = (int(px_x), int(px_y))
    casa.outdoor_dir = int(dir_rot)
    casa.is_open = True
    _OBJ_A_CASA[casa.outdoor_obj_id] = casa
    _CASAS_ACTIVAS[casa.owner_id] = casa

def retirar_casa_outdoor(casa: CasaData):
    casa.is_open = False
    if casa.outdoor_obj_id in _OBJ_A_CASA:
        del _OBJ_A_CASA[casa.outdoor_obj_id]
    casa.outdoor_obj_id = 0
    _CASAS_ACTIVAS.pop(casa.owner_id, None)

def cargar_casas_persistentes():
    # Las casas exteriores estan ligadas a la sesion del personaje:
    # no se colocan en el mapa exterior si el dueno esta desconectado.
    pass

def casas_en_stage(stage: int) -> list:
    st = int(stage)
    return [c for c in _CASAS_ACTIVAS.values() if c.is_open and c.outdoor_stage == st]

# Rankings / Billboard / HitParade
def ranking_hitparade(rtype: int, page: int = 0) -> list:
    # rtype: 31=Popularity, 32=Visits, 33=Cleanliness, 34=Magic Score
    casas = list(_CASAS_ACTIVAS.values())
    if rtype == 31: # Popularity / votes
        casas.sort(key=lambda c: c.votes_total, reverse=True)
        key_fn = lambda c: c.votes_total
    elif rtype == 32: # Visits
        casas.sort(key=lambda c: c.visitors_total, reverse=True)
        key_fn = lambda c: c.visitors_total
    elif rtype == 33: # Cleanliness
        casas.sort(key=lambda c: c.cleanliness, reverse=True)
        key_fn = lambda c: c.cleanliness
    else: # 34 Magic score
        casas.sort(key=lambda c: c.calcular_magia(), reverse=True)
        key_fn = lambda c: c.calcular_magia()

    start = page * 10
    subset = casas[start:start + 10]
    out = []
    for rank_idx, c in enumerate(subset, start=start + 1):
        out.append({
            'val1': rank_idx,
            'val2': c.owner_id,
            'name': c.house_name,
            'score': key_fn(c)
        })
    return out

def ranking_billboard(btype: int) -> list:
    # btype: 0=Magic, 1=Popularity
    casas = list(_CASAS_ACTIVAS.values())
    if btype == 1:
        casas.sort(key=lambda c: c.votes_total, reverse=True)
    else:
        casas.sort(key=lambda c: c.calcular_magia(), reverse=True)
    out = []
    for c in casas[:10]:
        out.append({
            'owner_id': c.owner_id,
            'owner_name': c.owner_name,
            'col1': c.calcular_magia(),
            'col2': c.votes_total
        })
    return out

def rango_casa(casa: CasaData) -> int:
    casas = sorted(_CASAS_ACTIVAS.values(), key=lambda c: c.calcular_magia(), reverse=True)
    for idx, c in enumerate(casas, 1):
        if c.owner_id == casa.owner_id:
            return idx
    return 1

# Reciclaje de muebles (Maquina de Huevos 11184)
def reciclar_muebles(furniture_ids: list) -> int:
    total_pts = sum(mueble(fid).get('puntos', 0) if mueble(fid) else 0 for fid in furniture_ids)
    target_pts = max(10, int(total_pts * 0.25))
    cands = [m['id'] for m in tabla() if abs(m.get('puntos', 0) - target_pts) <= 150 and m.get('puntos', 0) > 0]
    if not cands:
        cands = [m['id'] for m in tabla() if m.get('puntos', 0) > 0]
    return random.choice(cands) if cands else 1

# Martillo Magico (11114..11121)
MARTILLOS = {
    11114: (1, 2),
    11115: (6, 4),
    11116: (20, 10),
    11117: (60, 20),
    11118: (160, 40),
    11119: (400, 80),
    11120: (1000, 160),
    11121: (2400, 320),
}

def aplicar_martillo(item_martillo: int, mueble_id: int) -> int:
    m = mueble(mueble_id)
    if not m or item_martillo not in MARTILLOS:
        return 0
    min_magic, bonus_range = MARTILLOS[item_martillo]
    pts = m.get('puntos', 0)
    if pts < min_magic:
        return 0
    delta = random.randint(1, bonus_range)
    # 50% positive roll, 50% re-roll
    nuevo = max(1, pts + delta if random.random() < 0.7 else pts - (delta // 2))
    return nuevo
