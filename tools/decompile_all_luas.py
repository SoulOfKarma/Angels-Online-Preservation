import os
import glob
import subprocess
import pathlib

SRC_ROOT = pathlib.Path(r'G:\extracted_paks')
OUT_ROOT = pathlib.Path(r'F:\Ao Proyect\AO 2\extracted_luas')
OUT_ROOT.mkdir(parents=True, exist_ok=True)
JAR = pathlib.Path(r'F:\Ao Proyect\AO 2\tools\unluac.jar')

paks = ['data1', 'update', 'update2', 'update3'] + [f'UPDATE{i}' for i in range(4, 22)] + [f'update{i}' for i in range(22, 27)]

total = 0
success = 0
failed = 0

# We process chronological order, later paks overwrite older ones (same semantics)
for pak in paks:
    pak_dir = SRC_ROOT / pak / 'script'
    if not pak_dir.exists():
        continue
    for l_file in pak_dir.glob('*.l'):
        total += 1
        name = l_file.stem + '.lua'
        out_file = OUT_ROOT / name
        try:
            res = subprocess.run(['java', '-jar', str(JAR), str(l_file)], capture_output=True, text=True, check=True)
            out_file.write_text(res.stdout, encoding='utf-8')
            success += 1
        except Exception as e:
            failed += 1
            print(f"Error decompiling {l_file}: {e}")

print(f"Total processed: {total}, Decompiled: {success}, Failed: {failed}")
print(f"Saved into: {OUT_ROOT}")

