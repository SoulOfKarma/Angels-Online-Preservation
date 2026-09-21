import sys
sys.path.insert(0, 'server')
import crypto

clave = open('logs/sesiones/127_0_0_1_16769_20260920_194815_clave.txt', 'rb').read()
c2s_raw = open('logs/sesiones/127_0_0_1_16769_20260920_194815_c2s.bin', 'rb').read()
s2c_raw = open('logs/sesiones/127_0_0_1_16769_20260920_194815_s2c.bin', 'rb').read()

print(f"c2s len: {len(c2s_raw)}, s2c len: {len(s2c_raw)}")

# Decrypt c2s
dec_c2s = crypto.descifrar(c2s_raw, clave)
# Scan for packets in dec_c2s
pos = 0
import struct
while pos + 2 <= len(dec_c2s):
    op = struct.unpack_from('<H', dec_c2s, pos)[0]
    print(f"c2s offset {pos}: op={hex(op)}")
    if op == 6: # skill
        sk = struct.unpack_from('<H', dec_c2s, pos+2)[0]
        tgt = struct.unpack_from('<I', dec_c2s, pos+4)[0]
        print(f"  -> SKILL CAST: {sk} tgt={hex(tgt)}")
        pos += 18
    elif op == 4:
        pos += 13
    elif op == 0xf:
        pos += 10
    else:
        pos += 2
        # just break or scan

