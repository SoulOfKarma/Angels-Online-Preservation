import struct
import sys
sys.path.insert(0, 'proto')
import framing

clave = open('logs/sesiones/127_0_0_1_16769_20260920_194815_clave.txt', 'rb').read()
c2s_raw = open('logs/sesiones/127_0_0_1_16769_20260920_194815_c2s.bin', 'rb').read()
s2c_raw = open('logs/sesiones/127_0_0_1_16769_20260920_194815_s2c.bin', 'rb').read()

c2s_dec = framing.XorEvolving(clave).decodificar(c2s_raw)
s2c_dec = framing.XorEvolving(clave).decodificar(s2c_raw)

# Find all 0x0011 in s2c_dec
idx = 0
while True:
    pos = s2c_dec.find(b'\x11\x00', idx)
    if pos == -1: break
    raw = s2c_dec[pos:pos+25]
    if len(raw) >= 25:
        ef = raw[2]
        phase = raw[3]
        atk = int.from_bytes(raw[4:8], 'little')
        tgt = int.from_bytes(raw[8:12], 'little')
        val = int.from_bytes(raw[20:22], 'little')
        tp = raw[22]
        sk = int.from_bytes(raw[23:25], 'little')
        print(f"s2c 0x0011 at {pos}: ef={ef} phase=0x{phase:02x} val={val} type={tp} skill={sk}")
    idx = pos + 1

# Check for 0x0016 in c2s_dec
idx = 0
while True:
    pos = c2s_dec.find(b'\x16\x00', idx)
    if pos == -1: break
    raw = c2s_dec[pos:pos+7]
    print(f"c2s 0x0016 at {pos}: hex={raw.hex()}")
    idx = pos + 1

