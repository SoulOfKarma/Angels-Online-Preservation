import json
import struct

with open('logs/sesiones/127_0_0_1_16769_20261018_193120_orden.jsonl', 'r', encoding='utf-8') as f:
    lines = [json.loads(l) for l in f]

pkt_1b = lines[6201]
print("Packet 6201:", pkt_1b)
raw = bytes.fromhex(pkt_1b['hex'])
print("Total bytes:", len(raw))
count = struct.unpack_from('<I', raw, 0)[0]
print("Item count:", count)
# First entry: 86 bytes
e1 = raw[4:4+86]
item1 = struct.unpack_from('<I', e1, 9)[0]
slot1 = struct.unpack_from('<H', e1, 38)[0]
print(f"Entry 1: slot={slot1}, item_id={item1}")

e2 = raw[4+86:4+86+86]
item2 = struct.unpack_from('<I', e2, 9)[0]
slot2 = struct.unpack_from('<H', e2, 38)[0]
print(f"Entry 2: slot={slot2}, item_id={item2}")

