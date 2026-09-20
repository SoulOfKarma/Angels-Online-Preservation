import os

d = 'server/plantillas/mundo_real'
f = [x for x in os.listdir(d) if '0002' in x][0]
raw = open(os.path.join(d, f), 'rb').read()[2:] # skip opcode
unk50 = raw[50:102]
print("unk_50 hex:", unk50.hex())
for i, b in enumerate(unk50):
    if b != 0:
        print(f"offset +{50+i}: {b} (0x{b:02X})")

