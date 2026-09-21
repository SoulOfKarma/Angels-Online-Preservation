import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('F:/Ao Proyect/AO/Angel_unpacked.c', 'r', encoding='utf-8', errors='ignore') as f:
    for idx, line in enumerate(f, 1):
        if 320310 <= idx <= 320350:
            print(f"{idx}: {line}", end='')
        elif idx > 320350:
            break

