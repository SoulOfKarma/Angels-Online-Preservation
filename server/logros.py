"""Logros, titulos y puntos (achievement.xml).

4.351 logros en 74 tipos de regla. Cada fila dice su categoria, el texto,
cuantos puntos da, si anuncia al servidor y, 543 de ellas, que titulo
desbloquea.

Las reglas son el campo 規法 de la tabla. Aqui se implementan las que se
pueden comprobar con lo que el servidor ya sabe; las demas quedan
registradas y se dan por un aviso externo (`otorgar`), para que la tabla
este entera aunque la condicion todavia no se vigile.

Reglas que SI se comprueban solas:

    達指定等級        llegar a nivel N
    技能到達指定等級    una habilidad a nivel N
    殺指定編號怪物      matar un npc_type
    角色素質          un stat por encima de N
    成就積分          acumular N puntos de logro
    達成成就          tener otros logros (param1 y param2)

Las que NO, y por que:

    任務完成 (850)    hace falta el sistema de misiones
    融合相關 (361)    la fusion de mascotas
    NPC觸發 (297)     que el servidor avise al hablar con el NPC
    房屋系統 (79)     el sistema de casas
"""
import json
import pathlib

_TABLA = None
_POR_REGLA = None


def tabla() -> list:
    global _TABLA
    if _TABLA is None:
        f = pathlib.Path(__file__).parent / 'plantillas' / 'logros.json'
        try:
            _TABLA = json.loads(f.read_text(encoding='utf-8'))['filas']
        except Exception:
            _TABLA = []
    return _TABLA


def por_regla(regla: str) -> list:
    global _POR_REGLA
    if _POR_REGLA is None:
        _POR_REGLA = {}
        for f in tabla():
            _POR_REGLA.setdefault(f.get('regla'), []).append(f)
    return _POR_REGLA.get(regla, [])


def de_id(lid: int):
    for f in tabla():
        if f.get('id') == lid:
            return f
    return None


def puntos_de(conseguidos) -> int:
    """La suma de puntos de los logros que ya tiene."""
    ids = set(int(x) for x in (conseguidos or []))
    return sum(int(f.get('puntos') or 0) for f in tabla() if f.get('id') in ids)


def titulos_de(conseguidos) -> list:
    """Los titulos que desbloquean esos logros."""
    ids = set(int(x) for x in (conseguidos or []))
    return sorted({int(f['titulo']) for f in tabla()
                   if f.get('id') in ids and f.get('titulo')})


# --------------------------------------------------------------- reglas
def _num(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


STATS = {
    'HP最大值': 'hp_max', 'MP最大值': 'mp_max', '攻擊': 'atk',
    '防禦': 'dfs', '魔攻': 'matk', '魔防': 'mdef',
    '精準': 'rigor', '靈敏': 'agilidad',
}


def comprobar(personaje, conseguidos, *, muertos=None, stats=None) -> list:
    """Los logros que el personaje cumple y todavia no tiene.

    `muertos` es {npc_type: cuantos} y `stats` un dict de atributos ya
    calculados, por si el llamador los tiene a mano.
    """
    ya = set(int(x) for x in (conseguidos or []))
    muertos = muertos or {}
    stats = stats or {}
    nuevos = []
    nivel = _num(getattr(personaje, 'nivel', 0))
    habs = {int(h[0]): _num(h[1], 1)
            for h in (getattr(personaje, 'habilidades', None) or [])
            if isinstance(h, (list, tuple))}
    pts = puntos_de(ya)

    for f in por_regla('達指定等級'):
        if f['id'] not in ya and nivel >= _num(f.get('param1')):
            nuevos.append(f['id'])
    for f in por_regla('技能到達指定等級'):
        if f['id'] in ya:
            continue
        pide = _num(f.get('param1'))
        if pide and any(v >= pide for v in habs.values()):
            nuevos.append(f['id'])
    for f in por_regla('殺指定編號怪物'):
        if f['id'] in ya:
            continue
        tipo = _num(f.get('param1'))
        if tipo and muertos.get(tipo, 0) >= max(1, _num(f.get('param2'), 1)):
            nuevos.append(f['id'])
    for f in por_regla('角色素質'):
        if f['id'] in ya:
            continue
        clave = STATS.get(str(f.get('param1') or ''))
        if clave and _num(stats.get(clave)) >= _num(f.get('param2')):
            nuevos.append(f['id'])
    for f in por_regla('成就積分'):
        if f['id'] not in ya and pts >= _num(f.get('param1')):
            nuevos.append(f['id'])
    for f in por_regla('達成成就'):
        if f['id'] in ya:
            continue
        pide = [_num(f.get('param1')), _num(f.get('param2'))]
        pide = [x for x in pide if x]
        if pide and all(x in ya for x in pide):
            nuevos.append(f['id'])
    return sorted(set(nuevos))


def otorgar(conseguidos, lid: int) -> bool:
    """Da un logro a mano. Para las reglas que el servidor no vigila."""
    lid = int(lid)
    if de_id(lid) is None or lid in set(int(x) for x in (conseguidos or [])):
        return False
    conseguidos.append(lid)
    return True


# ===================================================================
# Lo que ve el cliente (REA, play_angel_unpacked.exe, 20/10/2026)
# ===================================================================
#
# s2c 0x0155 (FUN_005f4b10), el estado de TODOS los logros, 7.204 bytes:
#   800 bytes   un bit por logro (id i -> bit i%8 del byte i//8); el cliente
#               lo copia a +0x14b0 y la ventana (FUN_006ca6c0) mira el bit
#               de cada id para "Completed".
#   6400 bytes  el % de progreso de cada logro (0..100), a +0x17d0.
#   u32         la puntuacion (+0x49d0, el "Score" de la ventana).
# Igual que el que manda Celestia al entrar (mundo_202739_136382: 267
# completados con 100 y 16 a medias). Sin el, la ventana salia toda a 0%.
#
# Los TITULOS (crown.xml, 1..1023) que tiene el personaje van en el 0x0002:
# 128 bytes de bits en el +0x6d0 del paquete y el titulo puesto en el +0x750
# (FUN_005e9c90 -> FUN_005eb0b0 / FUN_004cfd80). Solo llegan al entrar.
# Ponerse uno: c2s 0x0016 accion 49 (game.equipcrown -> FUN_00614da0(0x31,
# id)); el servidor confirma con 0x001D codigo 57 (FUN_005f4e40, hueco
# 0x4798): a = titulo, b = 1 si es el propio jugador.
import struct as _struct

S2C_LOGROS = 0x0155
MAX_LOGROS = 6400
CODIGO_TITULO = 57
ACCION_TITULO = 49


def _pct(personaje, f, ya, pts, habs, muertos, stats):
    """% de un logro todavia no conseguido (0..99), para las reglas medibles."""
    regla = f.get('regla')
    def frac(v, n):
        n = _num(n)
        return 0 if n <= 0 else int(100 * max(0, min(v, n)) / n)
    if regla == '達指定等級':
        return frac(_num(getattr(personaje, 'nivel', 0)), f.get('param1'))
    if regla == '技能到達指定等級':
        return frac(max(habs.values() or [0]), f.get('param1'))
    if regla == '殺指定編號怪物':
        return frac(muertos.get(_num(f.get('param1')), 0), max(1, _num(f.get('param2'), 1)))
    if regla == '角色素質':
        clave = STATS.get(str(f.get('param1') or ''))
        return frac(_num(stats.get(clave)), f.get('param2')) if clave else 0
    if regla == '成就積分':
        return frac(pts, f.get('param1'))
    return 0


def paquete(personaje, muertos=None, stats=None, ctx=None) -> bytes:
    """El s2c 0x0155 con los logros del personaje."""
    ya = set(int(x) for x in (getattr(personaje, 'logros', None) or []))
    bits = bytearray(MAX_LOGROS // 8)
    prog = bytearray(MAX_LOGROS)
    pts = puntos_de(ya)
    habs = {int(h[0]): _num(h[1], 1) for h in (getattr(personaje, 'habilidades', None) or [])
            if isinstance(h, (list, tuple))}
    muertos = muertos or {}
    stats = stats or {}
    for f in tabla():
        lid = int(f.get('id') or 0)
        if not 0 < lid < MAX_LOGROS:
            continue
        if lid in ya:
            bits[lid // 8] |= 1 << (lid % 8)
            prog[lid] = 100
        else:
            pct = _pct(personaje, f, ya, pts, habs, muertos, stats)
            if not pct and ctx is not None:
                try:
                    r = medir(f, personaje, ctx)
                except Exception:
                    r = None
                if r and r[1] > 0:
                    pct = int(100 * max(0, min(r[0], r[1])) / r[1])
            prog[lid] = min(99, pct)
    return _struct.pack('<H', S2C_LOGROS) + bytes(bits) + bytes(prog) + _struct.pack('<I', pts)


def bits_titulos(personaje) -> bytes:
    """Los 128 bytes de titulos del 0x0002 (bit i = titulo i de crown.xml)."""
    b = bytearray(128)
    for t in titulos_de(getattr(personaje, 'logros', None) or []):
        if 0 < t < 1024:
            b[t // 8] |= 1 << (t % 8)
    return bytes(b)


CODIGO_TITULO_NUEVO = 56


def paquete_titulo_nuevo(entidad, titulo, anadir=True) -> bytes:
    """s2c 0x001D codigo 56: da (o quita) UN titulo sin tocar nada mas.

    FUN_005f4d80 (hueco 0x4788 de la tabla de FUN_005fbdd0) llama a
    FUN_004cfc00(titulo, b == 1), que enciende o apaga solo ese bit, y
    refresca las paginas de titulos y de reputacion. El 0x0002 no vale para
    esto: su manejador destruye y rehace el personaje del cliente y la
    mochila y el equipo se quedaban en blanco (21/10/2026)."""
    return _struct.pack('<HIBBII', 0x001D, int(entidad), 1, CODIGO_TITULO_NUEVO,
                        int(titulo), 1 if anadir else 0)


def paquete_titulo(entidad, titulo, es_yo) -> bytes:
    """s2c 0x001D codigo 57: el titulo que lleva puesto `entidad`."""
    return _struct.pack('<HIBBII', 0x001D, int(entidad), 1, CODIGO_TITULO,
                        int(titulo or 0), 1 if es_yo else 0)


@__import__('functools').lru_cache(maxsize=1)
def tipos_con_logro() -> frozenset:
    """Los npc_type que cuenta algun logro de "matar N de este monstruo"."""
    return frozenset(_num(f.get('param1')) for f in por_regla('殺指定編號怪物') if _num(f.get('param1')))


# ---- Logros de RANKING (排行榜相關, 52): estar entre los N primeros ----
# param1 es la lista y param2 el puesto (1, 10, 50, 100). Se miran contra las
# mismas listas que enseña el Rank List (ranking.lista). Una vez conseguido
# se queda, como el resto de logros.
LISTA_DE_RANKING = {
    '個人等級': 0,        # Exp / nivel
    '個人功勳': 1,        # creditos
    '個人擊殺': 2,        # bajas
    '個人死亡': 3,        # muertes
    '武器技能': 11, '防具技能': 12, '裁縫技能': 13, '工藝技能': 14, '烹飪技能': 15,
    '卡片收集數量': 17,
    '社團名聲': 4,        # reputacion de la liga
}


def puestos_de(personaje, listas) -> dict:
    """{param1: puesto (1..)} del personaje (o de su liga) en cada lista.

    `listas` es {tipo: [fila de ranking.lista]}; solo cuentan las filas con
    puntos, para que nadie sea "el mejor cocinero" con 0."""
    cid = int(getattr(personaje, 'char_id', 0) or 0)
    gid = int(getattr(personaje, 'guild_id', 0) or 0)
    out = {}
    for clave, tipo in LISTA_DE_RANKING.items():
        filas = [f for f in listas.get(tipo, []) if int(f.get('puntos') or 0) > 0 or tipo == 0]
        quien = gid if tipo == 4 else cid
        for i, f in enumerate(filas, 1):
            if quien and int(f.get('a') or 0) == quien:
                out[clave] = i
                break
    return out


def comprobar_ranking(conseguidos, puestos) -> list:
    ya = set(int(x) for x in (conseguidos or []))
    return sorted(f['id'] for f in por_regla('排行榜相關')
                  if f['id'] not in ya and str(f.get('param1')) in puestos
                  and puestos[str(f.get('param1'))] <= _num(f.get('param2')))


# ---- REPUTACION (pestaña Reputation) ----
# Cada titulo de crown.xml da su 聲望值; la suma es la reputacion del
# personaje (el cliente la calcula de los titulos del 0x0002 y pinta la
# tabla). prestige.xml da, por cada nivel alcanzado, stats FIJAS que se
# acumulan: nivel 1 (10) Max HP+800, nivel 2 (20) Max MP+480, nivel 3 (30)
# Rigor+10 y resistencias... Las aplica el servidor como un bono permanente
# que se suma a los buffs al calcular los stats (con_reputacion).
_PRESTIGE_A_BUFF = {
    'HP': 'hp_bonus', 'MP': 'mp_bonus', '精準': 'hit', '靈敏': 'eva',
    '防禦': 'def', '魔防': 'mdef', '攻擊': 'atk', '魔攻': 'matk',
    '體質抵抗': 'res_body', '心靈抵抗': 'res_mind', '雷電防禦': 'res_lightning',
    '火焰防禦': 'res_fire', '寒冰防禦': 'res_ice', '腐蝕防禦': 'res_corrosion',
    '重擊機率': 'crit', '物理傷害抵銷': 'mit', '魔法傷害抵銷': 'mag_mit',
    '移動速度': 'move_speed_bonus', '攻擊速度': 'atk_speed',
}
CLAVE_REPUTACION = 'reputacion'


def _setting(nombre):
    import re
    raiz = pathlib.Path(__file__).resolve().parent.parent / 'extracted_paks'
    mejor = None
    for c in raiz.iterdir():
        m = re.fullmatch(r'update(\d*)', c.name.lower())
        f = c / 'setting' / 'eng' / nombre
        if m and f.is_file() and (mejor is None or int(m.group(1) or 0) > mejor[0]):
            mejor = (int(m.group(1) or 0), f)
    return mejor[1] if mejor else None


@__import__('functools').lru_cache(maxsize=1)
def _crown_reputacion() -> dict:
    import re
    f = _setting('crown.xml')
    if not f:
        return {}
    return {int(i): int(v) for i, v in re.findall(r'編號="(\d+)" 封號="[^"]*" 聲望值="(\d+)"',
                                                    f.read_text(encoding='utf-8'))}


@__import__('functools').lru_cache(maxsize=1)
def _niveles_reputacion() -> list:
    """[(reputacion necesaria, {clave_buff: valor})] de prestige.xml."""
    import re
    f = _setting('prestige.xml')
    out = []
    if f:
        for attrs in re.findall(r'<prestige ([^>]*)/>', f.read_text(encoding='utf-8')):
            d = dict(re.findall(r'(\S+?)="([^"]*)"', attrs))
            bonos = {}
            for col, clave in _PRESTIGE_A_BUFF.items():
                if _num(d.get(col)):
                    bonos[clave] = bonos.get(clave, 0) + _num(d.get(col))
            out.append((_num(d.get('聲望')), bonos))
    return sorted(out, key=lambda x: x[0])


def reputacion(conseguidos) -> int:
    rep = _crown_reputacion()
    return sum(rep.get(t, 0) for t in titulos_de(conseguidos))


def bono_reputacion(conseguidos) -> dict:
    """Las stats de todos los niveles de reputacion alcanzados, sumadas."""
    r = reputacion(conseguidos)
    total = {}
    for necesita, bonos in _niveles_reputacion():
        if r < necesita:
            break
        for k, v in bonos.items():
            total[k] = total.get(k, 0) + v
    return total


def con_reputacion(buffs, personaje):
    """Los buffs del personaje mas el bono de reputacion como uno permanente."""
    bono = bono_reputacion(getattr(personaje, 'logros', None) or []) if personaje is not None else {}
    # Y lo que suben para siempre las semillas / frutos (inventario.stats_permanentes_de).
    perm = getattr(personaje, 'stats_permanentes', None) if personaje is not None else None
    amp = getattr(personaje, 'stats_amplify', None) if personaje is not None else None
    star = __import__('star_blessing').bonos(personaje) if personaje is not None else {}
    album = __import__('album').bono_buff(personaje) if personaje is not None else {}
    if not bono and not perm and not amp and not star and not album:
        return buffs
    out = dict(buffs or {})
    if bono:
        out[CLAVE_REPUTACION] = dict(bono, fin=float('inf'))
    if perm:
        out['permanentes'] = dict(perm, fin=float('inf'))
    if amp:
        out['pet_amplify'] = dict(amp, fin=float('inf'))
    if star:
        out['star_blessing'] = dict(star, fin=float('inf'))
    if album:
        out['album'] = dict(album,fin=float('inf'))
    return out


@__import__('functools').lru_cache(maxsize=1)
def _nombres_titulo() -> dict:
    import re
    f = _setting('crown.xml')
    if not f:
        return {}
    return {int(i): n.strip() for i, n in re.findall(r'編號="(\d+)" 封號="([^"]*)"', f.read_text(encoding='utf-8'))}


def nombre_titulo(titulo) -> str:
    return _nombres_titulo().get(int(titulo or 0), str(titulo))


# ===================================================================
# Reglas AMPLIADAS (20/10/2026). Cada una devuelve (valor, meta): se
# cumple cuando valor >= meta, y valor/meta es el % de la ventana.
#
# Unas salen del ESTADO del personaje (misiones, casa, oro, mascotas,
# equipo...) y otras de CONTADORES que el servidor va sumando en
# p.logros_cont al pasar cosas (ver app._logros_contar): 'mata:<npc>',
# 'muertes', 'totem_roto', 'captura:<npc>', 'captura_rango:<1..5>',
# 'obtiene:<item>', 'usa:<item>', 'fusion_pet:<item>', 'fusion_cons:<item>',
# 'fusion_pets', 'fusion_estrellas' (maximo), 'voto', 'baile',
# 'mejora_ok', 'mejora_fallo', 'transforma:<sprite>'.
#
# NO se pueden: NPC觸發 (297) -- los scripts de mapa de este cliente no usan
# la accion de dar logros, son de eventos japoneses que aqui no existen --,
# las mazmorras contadas (刷過幾次副本/完成某副本), los minijuegos, el
# Holy Battle, los puestos, el matrimonio y el resto de sistemas que el
# servidor aun no tiene.
# ===================================================================
TAMANO_DE_CASA = {10115: '小屋', 20076: '小屋', 10116: '中屋', 10117: '大屋', 17934: '豪華別墅',
                  17935: '大型豪華別墅', 17936: '大型豪宅', 17937: '超大型豪宅'}
CALIDAD = {'普通': 1, '優質': 2, '特級': 3, '稀有': 4, '極品': 5}
RANURA_MONTURA = 10


def _meta_del_nombre(f):
    """Algunas filas solo traen el numero en el nombre ("...House-1,500")."""
    import re
    m = re.findall(r'(\d[\d,]*)', str(f.get('nombre') or ''))
    return _num(m[-1].replace(',', '')) if m else 0


def _casa(personaje):
    try:
        import casas
        raw = getattr(personaje, 'casa', None)
        if hasattr(raw, 'serializar'):
            return raw
        if not raw:
            return None
        return casas.obtener_o_crear_casa(personaje.char_id, personaje.nombre, raw_data=raw)
    except Exception:
        return None


def _veces_mejora(m):
    m = m or {}
    try:
        return int(m.get('veces') or 0)
    except (TypeError, ValueError):
        return 0


def medir(f, personaje, ctx):
    """(valor, meta) de las reglas ampliadas, o None si la regla no se mide."""
    regla = f.get('regla')
    p1, p2 = f.get('param1'), f.get('param2')
    cont = ctx.get('cont') or {}
    import competicion_logros
    competencia = competicion_logros.medir(f, cont)
    if competencia is not None:
        return competencia
    olympic = __import__('olympus').medir_logro(f,cont)
    if olympic is not None:
        return olympic

    def c(clave):
        return int(cont.get(clave, 0) or 0)

    if regla == '任務完成':
        try:
            import misiones
            return (1 if misiones.mision_completada(personaje, _num(p1)) else 0), 1
        except Exception:
            return None
    if regla == '房屋系統':
        casa = ctx.get('casa')
        if p1 == '累積投出票數':
            return c('voto'), _num(p2)
        if p1 == '累積舞會啟動次數':
            return c('baile'), _num(p2)
        if casa is None:
            return 0, max(1, _num(p2) or _meta_del_nombre(f))
        if p1 == '展示房屋成功':
            ok = bool(getattr(casa, 'is_open', False)) and TAMANO_DE_CASA.get(int(casa.deed_id)) == p2
            return (1 if ok else 0), 1
        if p1 == '傢俱類別數量':
            import casas
            cats = {(casas.mueble(x.get('item_id', 0)) or {}).get('categoria')
                    for x in (casa.placed_furniture or [])}
            cats.discard(None)
            return len(cats), _num(p2)
        if p1 == '房屋等級提升':
            return int(getattr(casa, 'level', 1) or 1), _num(p2)
        if p1 == '參訪人數突破':
            return int(casa.visitors_total or 0), _num(p2)
        if p1 == '房屋排行榜改變':
            valor = casa.votes_today if p2 == '當日人氣數' else casa.votes_total
            return int(valor or 0), _meta_del_nombre(f)
        return None
    if regla == '卡片系統' and p1 == '蒐集卡片數量':
        return len(getattr(personaje, 'cartas', None) or []), _num(p2)
    if regla == '擁有遊戲幣':
        return int(ctx.get('oro') or 0), _num(p1)
    if regla == '功勳到達指定等級':
        return int(getattr(personaje, 'rango', 1) or 1), _num(p1)
    if regla == '學會招式數量':
        return len(getattr(personaje, 'hechizos_aprendidos', None) or []), _num(p1)
    if regla == '學會V數量':
        return ctx.get('hechizos_v', 0), _num(p1)
    if regla == '有3個角色':
        return int(ctx.get('num_pj') or 1), 3
    if regla in ('擁有指定物品', '獲得特定道具'):
        tiene = _num(p1) in set(int(x) for x in (ctx.get('bolsa') or {}).values())
        return max(c('obtiene:%d' % _num(p1)), 1 if tiene else 0), max(1, _num(p2, 1))
    if regla == '獲得特定道具次數':
        return c('obtiene:%d' % _num(p1)), max(1, _num(p2, 1))
    if regla == '獲得特定法術次數':
        return c('buff:%d' % _num(p1)), max(1, _num(p2, 1))
    if regla in ('使用物品編號和數量', '使用特定道具次數'):
        return c('usa:%d' % _num(p1)), max(1, _num(p2, 1))
    mascotas = ctx.get('mascotas') or []
    if regla == '訓練寵物達指定等級':
        return max([int(m.get('nivel') or 0) for m in mascotas] or [0]), _num(p1)
    if regla == '訓練出指定寵物':
        return (1 if any(int(m.get('sprite') or 0) == _num(p1) for m in mascotas) else 0), 1
    if regla == '訓練寵物達指定階級':
        try:
            import mascotas as _ms
            ok = any(_ms.ficha_de_sprite(int(m.get('sprite') or 0)).get('etapa') == p1 for m in mascotas)
        except Exception:
            ok = False
        return (1 if ok else 0), 1
    if regla == '抓到指定編號寵物':
        return c('captura:%d' % _num(p1)), 1
    if regla == '抓到指定品級寵物和數量':
        return c('captura_rango:%d' % CALIDAD.get(str(p1), 0)), max(1, _num(p2, 1))
    if regla == '強化相關':
        mej = ctx.get('mejoras') or {}
        if p1 == '強化裝備到強N':
            return max([_veces_mejora(v) for k, v in mej.items() if int(k) != RANURA_MONTURA] or [0]), _num(p2)
        if p1 == '強化坐騎到強N':
            return _veces_mejora(mej.get(RANURA_MONTURA) or mej.get(str(RANURA_MONTURA))), _num(p2)
        if p1 == '強化寵物到強N':
            return max([int(m.get('mejoras') or 0) for m in mascotas] or [0]), _num(p2)
        if p1 == '打孔到N個洞':
            return max([int((v or {}).get('huecos') or 0) for v in mej.values()] or [0]), _num(p2)
        if p1 == '強化成功次數':
            return c('mejora_ok'), _num(p2)
        if p1 == '強化失敗次數':
            return c('mejora_fallo'), _num(p2)
        return None
    if regla == '圖騰戰累計擊殺數':
        return int(getattr(personaje, 'pvp_kills', 0) or 0), _num(p1)
    if regla == '圖騰戰個人單場擊殺數':
        return int(ctx.get('ronda_tw') or 0), _num(p1)
    if regla == '圖騰戰個人擊破圖騰':
        return c('totem_roto'), _num(p1)
    if regla == '死亡次數':
        return c('muertes'), _num(p1)
    if regla == '融合相關':
        if p1 == '融合出指定寵':
            return c('fusion_pet:%d' % _num(p2)), 1
        if p1 == '融合出指定消耗品':
            return c('fusion_cons:%d' % _num(p2)), 1
        if p1 == '累計融合多少隻寵物':
            return c('fusion_pets'), _num(p2)
        if p1 == '融合出幾星的寵物':
            return c('fusion_estrellas'), _num(p2)
        return None
    if regla == '變身成特定圖號':
        return c('transforma:%d' % _num(p1)), 1
    dias = ctx.get('dias') or []
    if regla == '累計上線時間N天':
        return len(set(dias)), _num(p1)
    if regla == '連續N天每天登入':
        return _racha(dias), _num(p1)
    return None


def _racha(dias):
    """Dias seguidos conectado hasta el ultimo (fechas 'YYYY-MM-DD')."""
    import datetime
    fechas = sorted({datetime.date.fromisoformat(d) for d in dias if d})
    if not fechas:
        return 0
    racha = 1
    for a, b in zip(fechas[::-1], fechas[::-1][1:]):
        if (a - b).days == 1:
            racha += 1
        else:
            break
    return racha


def comprobar_extra(personaje, conseguidos, ctx) -> list:
    ya = set(int(x) for x in (conseguidos or []))
    nuevos = []
    for f in tabla():
        if f['id'] in ya:
            continue
        try:
            r = medir(f, personaje, ctx)
        except Exception:
            r = None
        if r and r[1] > 0 and r[0] >= r[1]:
            nuevos.append(f['id'])
    return nuevos


@__import__('functools').lru_cache(maxsize=1)
def items_contados() -> tuple:
    """(obtener, usar): los objetos cuyo conteo mira algun logro."""
    obt = {_num(f.get('param1')) for f in tabla()
           if f.get('regla') in ('獲得特定道具次數', '獲得特定道具', '擁有指定物品')}
    usa = {_num(f.get('param1')) for f in tabla()
           if f.get('regla') in ('使用物品編號和數量', '使用特定道具次數')}
    return frozenset(obt - {0}), frozenset(usa - {0})
