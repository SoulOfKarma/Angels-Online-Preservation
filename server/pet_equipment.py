"""Pet equipada en Gear: slot 558, distinto de accesorios y Pet Amplify.

Slot: Angel_unpacked.c, sub_57B320 (control 16026 -> 558).
Requisito: string.xml 2732 (cinco estrellas).
Transferencia de verdes: 1/5, documentada en la nota de auditoria.
"""
RANURA = 558
ESTRELLAS_MINIMAS = 50  # el protocolo guarda decimas
DIVISOR_BONOS = 5


def error_equipar(ficha):
    if not isinstance(ficha, dict):
        return 'Pet data is unavailable.'
    if ficha.get('fuera'):
        return 'Please recall this pet before equipping it.'
    if int(ficha.get('hp') or 0) <= 0:
        return 'The pet is dead.'
    if int(ficha.get('estrellas') or 0) < ESTRELLAS_MINIMAS:
        return 'Only pets with 5 stars or higher can be equipped.'
    return None


def bonos(bolsa, mascotas):
    """Solo verdes guardados, sin base por nivel ni buffs de saciedad."""
    import inventario
    item = (bolsa or {}).get(RANURA) or (bolsa or {}).get(str(RANURA))
    ficha = (mascotas or {}).get(str(RANURA)) or (mascotas or {}).get(RANURA)
    if not item or not inventario.es_mascota(int(item)) or error_equipar(ficha):
        return {}
    if ficha.get('item') and int(ficha['item']) != int(item):
        return {}
    verdes = ficha.get('bonos') or {}
    nombres = {'hp': 'hp', 'mp': 'mp', 'atk': 'atk', 'dfs': 'def',
               'matk': 'matk', 'mdef': 'mdef', 'rigor': 'accuracy',
               'agilidad': 'agility'}
    return {destino: max(0, int(verdes.get(origen) or 0)) // DIVISOR_BONOS
            for origen, destino in nombres.items()}
