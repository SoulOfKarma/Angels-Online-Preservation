"""Online Bonus y Login Bonus de la ventana Event Overview (WND_ACTBOARD).

Sacado con REA del cliente (play_angel_unpacked.exe) el 21/10/2026; no hay
capturas del oficial:

- Al arrancar, el cliente crea un objeto por tipo de actividad (FUN_005afde0
  -> FUN_006e4960): 2 = Login Bonus, 3, 4, 5 y 6 = Online Bonus. Viven en un
  mapa en +0x151ec del juego; FUN_004936b0(tipo) los busca.
- Los dos objetos guardan lo mismo: +8 el contador (dias del mes en el de
  Login, minutos conectado en el de Online) y +0xC la mascara de filas ya
  reclamadas (bit id-1). Una fila sale reclamable si su minimo (登入天數 /
  在線分鐘) <= contador y su bit esta a 0 (FUN_006e4570 / FUN_006e7330);
  con eso el boton pone "Receive" y la ventana el "!" rojo.
- Los rellena el s2c del tipo, con el mismo lector (FUN_0053c220: lee desde
  el byte 6 y el u32 de +2 dice si hay campo fijo). La tabla de manejadores
  de FUN_005e5350 va de 16 en 16 desde this+0x7b0 (el 0x0155 cae en 0x1d00):
      0x016F Login  (hueco 0x1ea0, FUN_005f86f0 -> FUN_006e4410)
      0x018A Online (hueco 0x2050, FUN_005f8730 -> FUN_006e7210)
      [u16 op][u32 tam][fijo][u32 n] n x ([u32 clave][u8 _] y si clave == 1:
      [u32 m] y si m >= 1 [u32 mascara])
  El fijo es u8 dias en el de Login y u32 minutos en el de Online, y "tam"
  vale 4 + lo que mide el fijo. Es justo lo que mando el servidor real al
  entrar (plantillas/mundo_real init_00_018A / init_01_016F: 0 minutos,
  1 dia, nada reclamado).
- Reclamar: actboard.l OnClickABLoginRaward -> game.netcommand(54, id) y
  OnClickABOnlineRaward -> game.netcommand(72, id): c2s 0x0016 [accion][id].
  onlinereward.l (la ventana suelta de antes) manda netcommand(53, 0).

Las filas son setting/eng/logingift.xml (2, 5, 7, 14 y 28 dias; la ventana
pone "Total Days Logged: %d / %d days" y el mes en curso, asi que va por mes)
y setting/eng/onlinegift.xml (0, 10, 20, 30, 40 y 60 minutos, "Total Log In
Duration: %d mins"; se reinicia cada dia).
"""
import datetime
import functools
import logging
import pathlib
import re
import struct

log = logging.getLogger('bonos')

S2C_LOGIN = 0x016F
S2C_ONLINE = 0x018A
ACCION_LOGIN = 54
ACCION_ONLINE = 72
ACCION_ONLINE_VIEJA = 53
MAX_FILAS = 10

_RAIZ = pathlib.Path(__file__).resolve().parent.parent


def _ultimo(nombre):
    """El archivo de setting/eng/ del update mas reciente que lo trae."""
    mejor = None
    for carpeta in (_RAIZ / 'extracted_paks').iterdir():
        m = re.fullmatch(r'update(\d*)', carpeta.name.lower())
        if not m:
            continue
        p = carpeta / 'setting' / 'eng' / nombre
        if p.is_file():
            n = int(m.group(1) or 0)
            if mejor is None or n > mejor[0]:
                mejor = (n, p)
    return mejor[1] if mejor else None


def _filas(nombre, etiqueta, campo):
    """{id: (minimo, [(item, cantidad)])} de logingift / onlinegift."""
    res = {}
    f = _ultimo(nombre)
    if not f:
        return res
    for attrs in re.findall(r'<%s ([^/>]+)/>' % etiqueta, f.read_text(encoding='utf-8')):
        d = dict(re.findall(r'(\S+)="([^"]*)"', attrs))
        try:
            fid = int(d.get('編號') or 0)
        except ValueError:
            continue
        if not 0 < fid <= MAX_FILAS:
            continue
        items = []
        for i in (1, 2, 3):
            try:
                it, n = int(d.get('道具%d' % i) or 0), int(d.get('數量%d' % i) or 0)
            except ValueError:
                continue
            if it > 0 and n > 0:
                items.append((it, n))
        res[fid] = (int(d.get(campo) or 0), items)
    return res


@functools.lru_cache(maxsize=1)
def filas_login():
    return _filas('logingift.xml', '登入獎勵', '登入天數')


@functools.lru_cache(maxsize=1)
def filas_online():
    return _filas('onlinegift.xml', '在線獎勵', '在線分鐘')


def _paquete(op, fijo, mascara):
    return (struct.pack('<HI', op, 4 + len(fijo)) + fijo
            + struct.pack('<IIBII', 1, 1, 0, 1, int(mascara) & 0xFFFFFFFF))


def paquete_login(dias, mascara):
    return _paquete(S2C_LOGIN, struct.pack('<B', max(0, min(255, int(dias)))), mascara)


def paquete_online(minutos, mascara):
    return _paquete(S2C_ONLINE, struct.pack('<I', max(0, int(minutos))), mascara)


class Estado:
    """Lo que guarda el personaje (clave 'bonos' de su ficha)."""

    def __init__(self, d=None):
        d = d or {}
        self.dia = str(d.get('dia') or '')
        self.segundos = float(d.get('segundos') or 0)
        self.online = int(d.get('online') or 0)
        self.mes = str(d.get('mes') or '')
        self.login = int(d.get('login') or 0)
        self.al_dia()

    def al_dia(self, hoy=None):
        """Reinicia lo diario (Online) y lo mensual (Login) si toca."""
        hoy = hoy or datetime.date.today()
        if self.dia != hoy.isoformat():
            self.dia, self.segundos, self.online = hoy.isoformat(), 0.0, 0
        if self.mes != hoy.strftime('%Y-%m'):
            self.mes, self.login = hoy.strftime('%Y-%m'), 0

    def datos(self):
        return {'dia': self.dia, 'segundos': round(self.segundos, 1), 'online': self.online,
                'mes': self.mes, 'login': self.login}

    @property
    def minutos(self):
        return int(self.segundos // 60)


def dias_del_mes(dias_conectado, hoy=None):
    """Dias distintos de este mes en la lista de fechas ISO de los logros."""
    hoy = hoy or datetime.date.today()
    pref = hoy.strftime('%Y-%m-')
    return len({d for d in (dias_conectado or []) if str(d).startswith(pref)})


def reclamable(filas, fid, contador, mascara):
    """None si se puede reclamar la fila; si no, el motivo."""
    fila = filas.get(int(fid))
    if not fila:
        return 'no existe'
    if mascara & (1 << (int(fid) - 1)):
        return 'ya reclamada'
    if contador < fila[0]:
        return 'aun no'
    return None


def siguiente_online(est):
    """La primera fila de Online Bonus que se puede reclamar ya, o None."""
    for fid in sorted(filas_online()):
        if reclamable(filas_online(), fid, est.minutos, est.online) is None:
            return fid
    return None
