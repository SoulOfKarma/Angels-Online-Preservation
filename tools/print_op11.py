import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('F:/Ao Proyect/AO/Angel_unpacked.c', 'r', encoding='utf-8', errors='ignore') as f:
    for idx, line in enumerate(f, 1):
        if 319440 <= idx <= 319520:
            print(f"{idx}: {line}", end='')
        elif idx > 319520:
            break

