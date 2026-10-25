"""El Rank List de las ciudades (WND_HITPARADEWIN).

Sacado con REA del cliente (play_angel_unpacked.exe) el 19/10/2026:

- Al hacer clic en el NPC 2089 "Rank List" el servidor abre la ventana con
  s2c 0x001D codigo 26 (CreateHitParadeWin; se guarda en +0x45a8 de la tabla
  de 0x5fbdd0, (0x45a8 - 0x4408) / 16 = 26).
- La ventana pide los datos con game.netcommand2 (FUN_00614e20), que es el
  c2s 0x002F [u8 cmd][u32 a][u32 b]. script/pvp.l, SendRequestHitParade:
  cmd 26, a = tipo, b = alineacion * 10 + pagina. Al abrirse manda ademas
  cmd 27 (0, 0).
- La respuesta es el s2c 0x014B (FUN_005efec0):
  [u8 tipo][u32 k][u16 n] y n registros de 33 bytes
  [u32 a][u32 b][char nombre[17]][u32 puntos_lo][u32 puntos_hi].
  El registro va a la celda tipo*700 + 0x230 + k*0x1c de la tabla +0x6c1c,
  que tiene 63 tipos x 5 alineaciones x 5 paginas de 0x1c. El 0x230 es la
  alineacion 4 ya sumada, asi que k = (alineacion - 4) * 5 + pagina.
- showhitparadedata (FUN_0060bb30) pinta el puesto como pagina*20 + i:
  20 por pagina, 5 paginas, el top 100.

Tipos (los textos de string.xml que pone la lista desplegable de pvp.l):
0 Exp, 1 Credit, 2 Target killed, 3 Death Times, 4 League rep., 11..15
Weapon/Armor/Dress/Craft/Food Skill, 17 Number of Cards. La alineacion 4 es
"todas" (la que pone por defecto); 0..3 se toman como las facciones 1..4
(Aurora, Beasts, Steel, Shadow), sin captura que lo confirme.
"""
import json
import struct

import cuentas

POR_PAGINA = 20
PAGINAS = 5

TIPO_EXP, TIPO_CREDITO, TIPO_LIGA, TIPO_CARTAS = 0, 1, 4, 17

_FACCION_DE_ALINEACION = {0: 'Aurora', 1: 'Beasts', 2: 'Steel', 3: 'Shadow'}


def _consulta(sql):
    con = cuentas._get_conn()
    try:
        return con.execute(sql).fetchall()
    except Exception:
        return []
    finally:
        con.close()


def _personajes():
    filas = _consulta('SELECT char_id, nombre, datos FROM personajes')
    salida = []
    for cid, nombre, datos in filas:
        try:
            d = json.loads(datos or '{}')
        except Exception:
            d = {}
        salida.append((int(cid), nombre or d.get('nombre', ''), d))
    return salida


def _gremios():
    return _consulta('SELECT guild_id, nombre, nivel, reputacion FROM gremios')


# Faccion como la pinta la columna "Faction" (0 Aurora .. 3 Shadow, medido:
# con 0 salia "Aurora"); las alineaciones de la lista van en el mismo orden.
_FACCION_COLUMNA = {'Aurora': 0, 'Beasts': 1, 'Steel': 2, 'Shadow': 3}


def lista(tipo, alineacion=4):
    """[{a, nombre, nivel, segundo, faccion, puntos}] de mayor a menor, top 100.

    Se calcula en cada peticion, asi que se va actualizando solo."""
    tipo = int(tipo)
    filtro = _FACCION_DE_ALINEACION.get(int(alineacion))
    filas = []
    if tipo in (38,39):
        import olympus
        return [r for r in olympus.clasificacion(tipo)
                if not filtro or r['faccion']==_FACCION_COLUMNA[filtro]][:POR_PAGINA*PAGINAS]
    if tipo == TIPO_LIGA:
        for gid, nom, niv, rep in _gremios():
            lider = _consulta('SELECT p.datos FROM gremios g JOIN personajes p '
                              'ON p.char_id = g.lider_char_id WHERE g.guild_id = %d' % int(gid))
            try:
                fac = json.loads(lider[0][0]).get('faction') if lider else None
            except Exception:
                fac = None
            if filtro and fac != filtro:
                continue
            miembros = _consulta('SELECT COUNT(*) FROM gremio_miembros WHERE guild_id = %d' % int(gid))
            filas.append({'a': int(gid), 'nombre': nom or '', 'nivel': int(niv or 1),
                          'segundo': int(miembros[0][0]) if miembros else 0,
                          'faccion': _FACCION_COLUMNA.get(fac, 0), 'puntos': int(rep or 0)})
    else:
        clave = {TIPO_EXP: lambda d: int(d.get('exp', 0) or 0),
                 TIPO_CREDITO: lambda d: int(d.get('creditos', 0) or 0),
                 2: lambda d: int(d.get('pvp_kills', 0) or 0),
                 3: lambda d: int(d.get('pvp_deaths', 0) or 0),
                 37: lambda d: len(d.get('logros') or []),
                 TIPO_CARTAS: lambda d: len(d.get('cartas') or [])}.get(tipo)
        if tipo in (11, 12, 13, 14, 15):
            sid = {11: 26, 12: 27, 13: 28, 14: 29, 15: 31}[tipo]
            clave = lambda d: max((int(h[1]) for h in d.get('habilidades', [])
                                   if len(h) >= 2 and int(h[0]) == sid), default=0)
        if clave is None:
            return []           # muertes, bajas, oficios: no se llevan aun
        for cid, nombre, d in _personajes():
            if filtro and d.get('faction') != filtro:
                continue
            filas.append({'a': cid, 'nombre': nombre, 'nivel': int(d.get('nivel', 1) or 1),
                          'segundo': int(d.get('rango', 1) or 1),
                          'faccion': _FACCION_COLUMNA.get(d.get('faction'), 0),
                          'puntos': clave(d)})
        if tipo == TIPO_EXP:
            filas.sort(key=lambda f: (f['nivel'], f['puntos']), reverse=True)
            return filas[:POR_PAGINA * PAGINAS]
    filas.sort(key=lambda f: f['puntos'], reverse=True)
    return filas[:POR_PAGINA * PAGINAS]


def paquete(tipo, alineacion, pagina, filas):
    """s2c 0x0133 con una pagina (20 filas). REA, FUN_0060c2b0:

        +2 u32 ?   +6 u8 tipo   +7 u8 alineacion   +8 u32 pagina   +12 u16 n
        n x 49 bytes: [u32 a][u32 b][nombre 17][u32 c][u32 d][u32 e][u64 puntos][u32 f]

    El cliente copia c, d, e y f a +0x1c, +0x20, +0x24 y +0x30 de su fila;
    son las columnas Level, Members (en lo personal la clase) y Faction. El
    0x014B que se usaba antes es el del ranking de las CASAS (FUN_005efec0):
    no trae esas columnas y salian en 0 y "Aurora".

    La columna Faction sale del ULTIMO u32 (f, +0x30 de la fila; FUN_0060bb30
    lo copia al [0xe] del elemento de la lista): con f a 0 todas las ligas
    salian "Aurora", tambien Moonlights, que es Beasts (20/10/2026). Va en
    e y en f, 0 Aurora .. 3 Shadow.
    """
    alineacion = min(max(int(alineacion), 0), 4)
    pagina = min(max(int(pagina), 0), PAGINAS - 1)
    trozo = filas[pagina * POR_PAGINA:(pagina + 1) * POR_PAGINA]
    cuerpo = b''.join(
        struct.pack('<II17sIIIQI', f['a'] & 0xFFFFFFFF, 0,
                    (f['nombre'] or '').encode('latin-1', 'replace')[:16].ljust(17, b'\0'),
                    f['nivel'] & 0xFFFFFFFF, f['segundo'] & 0xFFFFFFFF, f['faccion'] & 0xFFFFFFFF,
                    max(0, int(f['puntos'])) & 0xFFFFFFFFFFFFFFFF, f['faccion'] & 0xFFFFFFFF)
        for f in trozo)
    return struct.pack('<HIBBIH', 0x0133, 0, int(tipo) & 0xFF, alineacion, pagina,
                       len(trozo)) + cuerpo


def respuesta(cuerpo):
    """El 0x014B para un c2s 0x002F cmd 26, o None si no es eso."""
    if len(cuerpo) < 9 or cuerpo[0] != 26:
        return None
    tipo, mezcla = struct.unpack_from('<II', cuerpo, 1)
    # pvp.lua: __ACHIEVEMENT usa 11; anteriores usan 10. El 44 moderno es
    # All/pagina 1, no All/pagina 5. No recortar entradas invalidas a otro filtro.
    alineacion, pagina = divmod(mezcla, 11)
    if alineacion > 4 or pagina >= PAGINAS:
        alineacion, pagina = divmod(mezcla, 10)
    if alineacion > 4 or pagina >= PAGINAS:
        return None
    if tipo >= 63:
        return None
    return paquete(tipo, alineacion, pagina, lista(tipo, alineacion))


def abrir_ventana(entity_id):
    """s2c 0x001D codigo 26: CreateHitParadeWin."""
    return struct.pack('<HIBBII', 0x001D, entity_id, 1, 26, 0, 0)
