import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('F:/Ao Proyect/AO/Angel_unpacked.c', 'r', encoding='utf-8', errors='ignore') as f:
    for idx, line in enumerate(f, 1):
        if 319521 <= idx <= 319600:
            print(f"{idx}: {line}", end='')
        elif idx > 319600:
            break

