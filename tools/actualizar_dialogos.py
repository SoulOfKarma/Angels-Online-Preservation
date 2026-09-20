import json
import struct
import pathlib

p = pathlib.Path('server/plantillas/dialogos_npc.json')
d = json.load(open(p, encoding='utf-8'))

def armar_hex(mid, val, opts=[]):
    hdr = struct.pack('<IHBBB', mid, val, 0, len(opts), 0)
    body = b''.join(struct.pack('<I', o) for o in opts)
    return (hdr + body).hex()

npcs = d.setdefault('npcs', {})

# Director Wolay (default study text when in Heaven faction)
npcs['Director Wolay'] = {
    'msgid': 10004,
    'val': 49,
    'hex': armar_hex(10004, 49, []),
    'texto': "I'm Director Wolay. Don't forget to study hard to become an excellent Angel."
}

# 4 Totems in Lyceum
npcs['Aurora Totem'] = {
    'msgid': 10201,
    'val': 4,
    'hex': armar_hex(10201, 4, [10205, 10207, 10208, 10206]),
    'texto': "Hello, I'm the Angel Protector from Aurora City, do you want to join us?"
}

npcs['Dark City Totem'] = {
    'msgid': 10202,
    'val': 4,
    'hex': armar_hex(10202, 4, [10205, 10209, 10210, 10206]),
    'texto': "Hello, I'm the Angel Protector from Dark City, do you want to join us?"
}

npcs['Iron Totem'] = {
    'msgid': 10203,
    'val': 4,
    'hex': armar_hex(10203, 4, [10205, 10211, 10212, 10206]),
    'texto': "Hello, I'm the Angel Protector from Iron Castle, do you want to join us?"
}

npcs['Breeze Totem'] = {
    'msgid': 10204,
    'val': 4,
    'hex': armar_hex(10204, 4, [10205, 10213, 10214, 10206]),
    'texto': "Hello, I'm the Angel Protector from Breeze Woods, do you want to join us?"
}

# Pet Expert
npcs['Pet Expert'] = {
    'msgid': 6100,
    'val': 4,
    'hex': armar_hex(6100, 4, [6101, 6102, 6103, 6104]),
    'texto': "I'm the Pet Merchant, I sell many kinds of props and feedstuffs you can take a look around if you are interested!"
}

# Gaoler Angel
npcs['Gaoler Angel'] = {
    'msgid': 5085,
    'val': 3,
    'hex': armar_hex(5085, 3, []),
    'texto': "Gaoler Angel"
}

# Scroll Seller
npcs['Scroll Seller'] = {
    'msgid': 12101,
    'val': 4,
    'hex': armar_hex(12101, 4, [12103, 12105]),
    'texto': "Scroll Seller"
}

# Magic Seller
npcs['Magic Seller'] = {
    'msgid': 12101,
    'val': 4,
    'hex': armar_hex(12101, 4, [12103, 12105]),
    'texto': "Magic Seller"
}

# Michael
npcs['Michael'] = {
    'msgid': 5001,
    'val': 3,
    'hex': armar_hex(5001, 3, []),
    'texto': "Michael"
}

p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding='utf-8')
print("dialogos_npc.json actualizado con exito!")

