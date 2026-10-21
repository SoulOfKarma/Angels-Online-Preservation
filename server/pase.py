"""Angel Pass (battle pass, WND_BATTLE_PASS).

Sacado con REA del cliente (play_angel_unpacked.exe) el 21/10/2026; no hay
capturas del oficial.

LA TEMPORADA LA ELIGE EL CLIENTE con el reloj del PC: FUN_006f6d50 se queda
con la primera fila de su setting/battlepass.xml con inicio <= ahora <= fin
(FUN_006f50e0). Las tres del pak acababan en 2025, asi que la ventana salia
"Null" y 0/0. cliente_local.py alarga la temporada TEMPORADA en el pak del
cliente (con permiso del usuario, 21/10/2026) y aqui se usa la misma fila.

Estado en el cliente (gestor de FUN_0049ed60): +0 temporada, +4 exp dentro
del nivel, +8 nivel, +0xC ultimo nivel reclamado gratis, +0x10 el de pago,
+0x14 pase de pago comprado, +0x9c 2 = abierta, +0xa0 tareas cerradas. La
barra es exp / 經驗值 del nivel siguiente (FUN_0049d700).

s2c (tabla de FUN_005e5350, hueco = this + 0x7b0 + op*16):
  0x018D estado completo (FUN_005f4420): [u32 temporada][u32 nivel][u32 exp]
         [u32 gratis][u32 pago][u8 pase][u8 cerrado] + 4 listas x 10 x
         [u32 tarea][u32 progreso]. Listas 1-2 diarias, 3-4 semanales (la
         pagina de tareas FUN_0049e2a0 pinta 1+2 o 3+4).
  0x018E [u32 1|2] + 2 x 10 x [tarea, progreso]: tareas nuevas del dia / semana.
  0x018F [u32 lista][u32 tarea][u32 progreso]: una tarea.
  0x0190 [u32 1|2][u32 nivel]: reclamado gratis / de pago.
  0x0191 [u32 nivel][u32 exp].
  0x0194 [u8 pase][u32 pago]: pase comprado.
c2s 0x0016 accion 74 (OnBattlePassaActionOK / FUN_0049ed60):
  2 = comprar un nivel (gasta 升級道具ID), 3 = reclamar todo lo pendiente,
  4 = comprar el pase de pago (gasta 開通道具ID).

Tareas (battlepasstask.xml): se cumplen al llegar a 動態參數1 y dan su
經驗值 solas, sin boton. 打怪類 cuenta los monstruos del 系別 動態參數2
(1 人型 ... 6 惡魔, monster.xml); 蒐集道具類 el objeto 動態參數2;
完成通行證任務類 la exp de pase ganada en el mismo periodo (70 al dia /
800 a la semana: justo lo que dan las demas tareas).
"""
import datetime
import functools
import logging
import pathlib
import random
import re
import struct

log = logging.getLogger('pase')

TEMPORADA = 4                       # fila de battlepass.xml que se alarga en el cliente
INICIO_TEMPORADA = '2601010000'     # AAMMDDhhmm, lo que se pone en el pak
FIN_TEMPORADA = '2912312359'

ACCION = 74
ACC_NIVEL, ACC_RECLAMAR, ACC_PASE = 2, 3, 4
S2C_ESTADO, S2C_REINICIO, S2C_TAREA = 0x018D, 0x018E, 0x018F
S2C_RECLAMADO, S2C_NIVEL, S2C_PASE = 0x0190, 0x0191, 0x0194
MAX_TAREAS = 10

_RAIZ = pathlib.Path(__file__).resolve().parent.parent


def _ultimo(nombre, eng=False):
    mejor = None
    for carpeta in (_RAIZ / 'extracted_paks').iterdir():
        m = re.fullmatch(r'update(\d*)', carpeta.name.lower())
        if not m:
            continue
        p = carpeta / 'setting' / ('eng' if eng else '') / nombre
        if p.is_file():
            n = int(m.group(1) or 0)
            if mejor is None or n > mejor[0]:
                mejor = (n, p)
    return mejor[1] if mejor else None


def _filas(nombre, etiqueta, eng=False):
    f = _ultimo(nombre, eng)
    if not f:
        return []
    texto = f.read_text(encoding='utf-8')
    return [dict(re.findall(r'(\S+)="([^"]*)"', a))
            for a in re.findall(r'<%s ([^/>]+)/>' % etiqueta, texto)]


def _n(v, defecto=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return defecto


@functools.lru_cache(maxsize=1)
def temporada():
    for f in _filas('battlepass.xml', 'battlepass'):
        if _n(f.get('編號')) == TEMPORADA:
            return f
    return {}


@functools.lru_cache(maxsize=1)
def premios():
    """{nivel: fila} del grupo de premios de la temporada."""
    g = _n(temporada().get('獎勵群組ID'))
    return {_n(f.get('等級')): f for f in _filas('battlepassprize.xml', 'battlepassprize')
            if _n(f.get('群組編號')) == g}


def nivel_max():
    return max(premios() or [0])


@functools.lru_cache(maxsize=1)
def tareas():
    """{id: fila} de battlepasstask.xml."""
    return {_n(f.get('編號')): f for f in _filas('battlepasstask.xml', 'battlepasstask')}


def _grupo(g):
    return sorted(t for t, f in tareas().items() if _n(f.get('群組編號')) == _n(g))


@functools.lru_cache(maxsize=1)
def razas():
    """{tipo de monstruo: 系別 1..6} de monster.xml."""
    valores = {'人型': 1, '動物': 2, '植物': 3, '能量': 4, '不死': 5, '惡魔': 6}
    res = {}
    for f in _filas('monster.xml', 'npc', eng=True):
        k = f.get('系別')
        res[_n(f.get('編號'))] = valores.get(k, _n(k))
    return res


def items_de_tareas():
    return {_n(f.get('動態參數2')) for f in tareas().values() if f.get('規則') == '蒐集道具類'}


def _periodos(ahora=None):
    """(clave del dia, clave de la semana) segun 每日/每週任務重置時間."""
    ahora = ahora or datetime.datetime.now()
    t = temporada()
    dr = _n(t.get('每日任務重置時間'))
    dia = (ahora - datetime.timedelta(hours=dr // 100, minutes=dr % 100)).date()
    wr = _n(t.get('每週任務重置時間'))
    wd, h, mi = wr // 10000, (wr % 10000) // 100, wr % 100      # wd: 0 = domingo (tm_wday de C)
    corte = ahora.replace(hour=h, minute=mi, second=0, microsecond=0)
    atras = (corte.isoweekday() % 7 - wd) % 7
    corte -= datetime.timedelta(days=atras)
    if corte > ahora:
        corte -= datetime.timedelta(days=7)
    return dia.isoformat(), corte.date().isoformat()


def _sorteo(semilla, grupo, cuantas):
    ids = _grupo(grupo)
    rnd = random.Random(semilla)
    return sorted(rnd.sample(ids, min(cuantas, len(ids))))


class Estado:
    def __init__(self, char_id, d=None):
        d = d or {}
        self.char_id = int(char_id)
        self.temporada = _n(d.get('temporada'), TEMPORADA)
        if self.temporada != TEMPORADA:
            d = {}
        self.nivel = _n(d.get('nivel'))
        self.exp = _n(d.get('exp'))
        self.gratis = _n(d.get('gratis'))
        self.pago = _n(d.get('pago'))
        self.pase = bool(d.get('pase'))
        self.dia = str(d.get('dia') or '')
        self.semana = str(d.get('semana') or '')
        self.listas = {int(k): [[_n(a), _n(b)] for a, b in v] for k, v in (d.get('listas') or {}).items()}
        self.temporada = TEMPORADA

    def datos(self):
        return {'temporada': self.temporada, 'nivel': self.nivel, 'exp': self.exp,
                'gratis': self.gratis, 'pago': self.pago, 'pase': self.pase,
                'dia': self.dia, 'semana': self.semana,
                'listas': {str(k): v for k, v in self.listas.items()}}

    def al_dia(self, ahora=None):
        """Sortea las tareas del dia / semana nuevos. Devuelve [1] / [2] / [1, 2]."""
        t = temporada()
        dia, semana = _periodos(ahora)
        cambios = []
        if dia != self.dia:
            self.dia = dia
            self.listas[1] = [[i, 0] for i in _grupo(t.get('每日固定任務群組ID'))][:MAX_TAREAS]
            self.listas[2] = [[i, 0] for i in _sorteo('%d:%s:d' % (self.char_id, dia),
                                                       t.get('每日隨機任務群組ID'),
                                                       _n(t.get('每日隨機任務數量')))][:MAX_TAREAS]
            cambios.append(1)
        if semana != self.semana:
            self.semana = semana
            self.listas[3] = [[i, 0] for i in _grupo(t.get('每週固定任務群組ID'))][:MAX_TAREAS]
            self.listas[4] = [[i, 0] for i in _sorteo('%d:%s:w' % (self.char_id, semana),
                                                       t.get('每週隨機任務群組ID'),
                                                       _n(t.get('每週隨機任務數量')))][:MAX_TAREAS]
            cambios.append(2)
        return cambios

    def sumar_exp(self, n):
        """Suma exp de pase y sube de nivel. True si subio."""
        antes = self.nivel
        self.exp += int(n)
        while self.nivel < nivel_max():
            falta = _n(premios()[self.nivel + 1].get('經驗值'))
            if falta <= 0 or self.exp < falta:
                break
            self.exp -= falta
            self.nivel += 1
        if self.nivel >= nivel_max():
            self.exp = 0
        return self.nivel != antes

    def contar(self, regla, n=1, param=None):
        """Avanza las tareas de esa regla. Devuelve ([(lista, tarea, progreso)], exp ganada)."""
        tocadas, exp = [], 0
        for lista in (1, 2, 3, 4):
            for par in self.listas.get(lista, []):
                f = tareas().get(par[0]) or {}
                if f.get('規則') != regla:
                    continue
                if regla in ('打怪類', '蒐集道具類') and _n(f.get('動態參數2')) not in (0, _n(param)):
                    continue
                meta = max(1, _n(f.get('動態參數1'), 1))
                if par[1] >= meta:
                    continue
                par[1] = min(meta, par[1] + int(n))
                tocadas.append((lista, par[0], par[1]))
                if par[1] >= meta:
                    exp += _n(f.get('經驗值'))
        return tocadas, exp


# ------------------------------------------------------------------ paquetes

def _listas(est, cuales):
    out = b''
    for lista in cuales:
        filas = (est.listas.get(lista) or [])[:MAX_TAREAS]
        for i in range(MAX_TAREAS):
            t, p = filas[i] if i < len(filas) else (0, 0)
            out += struct.pack('<II', t, p)
    return out


def paquete_estado(est):
    return (struct.pack('<HIIIIIBB', S2C_ESTADO, est.temporada, est.nivel, est.exp,
                        est.gratis, est.pago, 1 if est.pase else 0, 0)
            + _listas(est, (1, 2, 3, 4)))


def paquete_reinicio(est, cual):
    return struct.pack('<HI', S2C_REINICIO, cual) + _listas(est, (1, 2) if cual == 1 else (3, 4))


def paquete_tarea(lista, tarea, progreso):
    return struct.pack('<HIII', S2C_TAREA, lista, tarea, progreso)


def paquete_nivel(est):
    return struct.pack('<HII', S2C_NIVEL, est.nivel, est.exp)


def paquete_reclamado(cual, nivel):
    return struct.pack('<HII', S2C_RECLAMADO, cual, nivel)


def paquete_pase(est):
    return struct.pack('<HBI', S2C_PASE, 1 if est.pase else 0, est.pago)


def premios_pendientes(est):
    """[(item, cantidad)] de lo que se puede reclamar ya, y los niveles nuevos."""
    items = []
    for nv in range(est.gratis + 1, est.nivel + 1):
        f = premios().get(nv) or {}
        for i in (1, 2):
            it, c = _n(f.get('免費獎勵%d道具ID' % i)), _n(f.get('免費獎勵%d道具數量' % i))
            if it > 0 and c > 0:
                items.append((it, c))
    if est.pase:
        for nv in range(est.pago + 1, est.nivel + 1):
            f = premios().get(nv) or {}
            for i in (1, 2):
                it, c = _n(f.get('付費獎勵%d道具ID' % i)), _n(f.get('付費獎勵%d道具數量' % i))
                if it > 0 and c > 0:
                    items.append((it, c))
    return items
