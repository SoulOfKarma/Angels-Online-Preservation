"""Aliua y el [Supreme Power] (misión 1491 "Surpass Your Limits").

Aliua (npc 14517, retrato 40002) está en el Angel Lyceum en (202,106)
(captura mundo_192439). Su diálogo son los msg 149101..149129 y la misión la
1491 de quest.xml. Lo que ella cuenta:

  - Hace falta nivel 401 o más (149113) y estar en una facción (149129).
  - Prueba 1: 200 Pearl Cockatrice (20817) y 200 Ruby Cockatrice (20816) en
    Perilous Depths; se ven en el registro con los objetos 8783 / 8784.
  - Prueba 2: 200 de UNO de los cinco materiales de nivel 301 (149120).
  - Al aceptar el poder: logro 3715 "Attain Angel's Zenith" (título 467).

Compatibilidad del servidor: Aliua NO concede ranuras ni habilidades al azar.
Las ranuras 7, 8 y 9 ya las administra skills.py por nivel (301/351/401).
Completar esta misión solo registra el poder y conserva el logro: no cambia
las habilidades equipadas ni su banco, y nunca debe crear una décima rama.
El cambio visual a PLV usa el estado 0x02000000 del cliente; el nivel real
y la progresion del servidor siguen intactos.
"""
import dialogos

MISION = 1491
NPC = 'Aliua'
RETRATO = 2                      # sprite 40002 -> retrato 2 (como Michael 40001 -> 1)
NIVEL_MINIMO = 401
LOGRO = 3715
CLAVE = 'supremo'                # en p.logros_cont
ESTADO_SUPREMO = 0x02000000       # cliente sub_63AA20: PLV = nivel - 400
ESTADO_PROPIO = 0x80000000       # mismo estado base de login._ficha (funciones de casa)


def estado(personaje, base=ESTADO_PROPIO):
    """Componer flags sin cambiar nivel, habilidades ni EXP.

    No basta el nivel: hace falta la recompensa persistente de Aliua.
    El cliente solo muestra PLV para niveles superiores a 400.
    """
    activo = (int(getattr(personaje, 'nivel', 0) or 0) >= NIVEL_MINIMO
              and bool((getattr(personaje, 'logros_cont', None) or {}).get(CLAVE)))
    return (int(base) & ~ESTADO_SUPREMO) | (ESTADO_SUPREMO if activo else 0)


def paquete_estado(personaje, base=ESTADO_PROPIO):
    import combate
    return combate.atributo(personaje.entity_id, estado(personaje, base), combate.KIND_ESTADO)

PEARL, RUBY = 20817, 20816
TOKENS = {PEARL: 8783, RUBY: 8784}
BAJAS = 200
MATERIALES = (51631, 51633, 51635, 51637, 51639)   # Lv 301 Ashen Berries .. Tanzatox Fang
CANTIDAD_MATERIAL = 200


def conceder_poder(personaje):
    """Marca la recompensa sin conceder/modificar slots, skills ni su EXP.

    No llamar a completar_ranuras_extra ni añadir una rama aquí. Esa política
    pertenece exclusivamente al sistema existente de skills por nivel.
    La persistencia y el logro los gestiona el diálogo de app.py.
    """
    if getattr(personaje, 'logros_cont', None) is None:
        personaje.logros_cont = {}
    personaje.logros_cont[CLAVE] = 1

# Opciones del diálogo
OP_QUE_ES, OP_QUIERO, OP_NO = 149102, 149103, 149104
OP_REQUISITOS = 149107
OP_ACEPTO_PRUEBA, OP_NO_PRUEBA = 149115, 149116
OP_SI_PODER, OP_LUEGO = 149125, 149126
OPCIONES = {OP_QUE_ES, OP_QUIERO, OP_NO, OP_REQUISITOS, OP_ACEPTO_PRUEBA,
            OP_NO_PRUEBA, OP_SI_PODER, OP_LUEGO}


def _l(mid, opts=None):
    return dialogos.armar_linea(mid, RETRATO, list(opts or []))[2:]


def guion(*mids, opts=None):
    """Varias lineas seguidas; la ultima con sus opciones."""
    g = [_l(m) for m in mids[:-1]]
    g.append(_l(mids[-1], opts))
    return g


def saludo():
    return guion(149101, opts=[OP_QUE_ES, OP_QUIERO, OP_NO])


def explicacion():
    return guion(149105, 149106, opts=[OP_REQUISITOS, OP_QUIERO, OP_NO])


def requisitos():
    return guion(149108, 149109, 149110, 149111)


def bajas_hechas(tokens):
    return all(tokens.get(t, 0) >= BAJAS for t in TOKENS.values())


def material_listo(cantidad_de):
    """El primer material del que hay 200, o None."""
    for it in MATERIALES:
        if cantidad_de(it) >= CANTIDAD_MATERIAL:
            return it
    return None
