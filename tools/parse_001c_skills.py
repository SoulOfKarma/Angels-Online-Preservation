import json
import struct

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

for e in entries:
    if e['dir'] == 's2c' and e['opcode'] == 0x1c:
        raw = bytes.fromhex(e['hex'])
        print(f"Len: {len(raw)}")
        # 72 entries of 14 bytes = 1008 bytes
        for i in range(72):
            chunk = raw[i*14 : (i+1)*14]
            sk_id, lvl, lvl2, exp, idx = struct.unpack('<HBBII', chunk[:12] + b'\x00' * (12 - len(chunk[:12]))) if len(chunk)>=12 else (0,0,0,0,0)
            # unpack:
            # chunk: 14 bytes
            # byte 0: skill_id
            # byte 1: lvl
            # byte 2..3: lvl2 (LE16)
            # byte 4..7: zeros
            # byte 8..11: exp (LE32)
            # byte 12..13: idx (LE16)
            if chunk[0] != 0:
                sk_id = chunk[0]
                lvl = chunk[1]
                lvl2 = struct.unpack_from('<H', chunk, 2)[0]
                exp = struct.unpack_from('<I', chunk, 8)[0]
                idx = struct.unpack_from('<H', chunk, 12)[0]
                print(f"  Slot {idx:2d} (i={i:2d}): skill_id={sk_id:2d}, lvl={lvl}, lvl2={lvl2}, exp={exp} ({exp/10.0:.1f}%) hex={chunk.hex()}")
        break

