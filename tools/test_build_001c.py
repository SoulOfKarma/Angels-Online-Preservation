import struct

def construir_001c(habilidades: list) -> bytes:
    """Construye el paquete 0x001C (1008 bytes: 72 entradas de 14 bytes).

    i=0..35: ceros (o reservado)
    i=36..41: las 6 habilidades del personaje con sus niveles, exp y slot (1..6)
    i=42..71: las demas habilidades disponibles con nivel 1 y slot 0
    """
    buf = bytearray(1008)
    
    # Mapear las 6 habilidades del personaje a slots 1..6 (en indices 36..41)
    hab_dict = {}
    for idx, h in enumerate(habilidades[:6], 1):
        sid = h[0] if isinstance(h, (list, tuple)) else h
        lvl = h[1] if isinstance(h, (list, tuple)) and len(h) > 1 else 1
        exp = h[2] if isinstance(h, (list, tuple)) and len(h) > 2 else 0
        hab_dict[sid] = (lvl, exp, idx)

    # Las 36 habilidades estándar de Angels Online (level.xml)
    ALL_SKILLS = [
        9, 12, 13, 15, 16, 33, # Swordsman tipicas
        1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 14, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 35, 36
    ]

    # Entradas en i = 36..71
    entry_idx = 36
    # Primero las habilidades del personaje
    for sid in hab_dict:
        lvl, exp, slot = hab_dict[sid]
        # Chunk 14 bytes:
        # byte 0: sid (U8)
        # byte 1: lvl (U8)
        # byte 2..3: lvl (LE16)
        # byte 4..7: exp (LE32)
        # byte 8..11: exp_max (LE32) - 8 o lvl * 3
        # byte 12..13: slot (LE16)
        struct.pack_into('<BBHIIH', buf, entry_idx * 14, sid, lvl, lvl, exp, 8, slot)
        entry_idx += 1

    # Despues las demas habilidades
    for sid in ALL_SKILLS:
        if sid not in hab_dict and entry_idx < 72:
            struct.pack_into('<BBHIIH', buf, entry_idx * 14, sid, 1, 1, 0, 3, 0)
            entry_idx += 1

    return struct.pack('<H', 0x001C) + bytes(buf)

# Test encoding
b = construir_001c([(9, 2, 100), (12, 2, 100), (13, 1, 0), (15, 1, 0), (16, 2, 100), (33, 2, 100)])
print("Total size:", len(b), "bytes (header + 1008 payload)")

