# -*- coding: utf-8 -*-
"""
Empaqueta los XMLs corregidos (item4..item9 con %s restaurados, martillo 78384 y shop.xml)
en update26.pak de C:\\AO\\Angels Online y sincroniza con F:\\Ao Proyect\\AO 2.
"""
import datetime
import os
import pathlib
import shutil
import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from tools import pak_tool

C_AO = pathlib.Path(r'C:\AO\Angels Online')
U26_CLIENT = C_AO / 'update26.pak'
U26_BAK = C_AO / 'update26.pak.bak'
U26_SALIDA = pathlib.Path('work/salida/paks/update26.pak')

F_PROYECT = pathlib.Path(r'F:\Ao Proyect\AO 2')

RECURSOS_PATHS = [
    ('setting/eng/drop.xml', 'extracted_paks/update26/setting/eng/drop.xml'),
    ('setting/eng/item4.xml', 'extracted_paks/update26/setting/eng/item4.xml'),
    ('setting/eng/item5.xml', 'extracted_paks/update26/setting/eng/item5.xml'),
    ('setting/eng/item6.xml', 'extracted_paks/update26/setting/eng/item6.xml'),
    ('setting/eng/item7.xml', 'extracted_paks/update26/setting/eng/item7.xml'),
    ('setting/eng/item8.xml', 'extracted_paks/update26/setting/eng/item8.xml'),
    ('setting/eng/item9.xml', 'extracted_paks/update26/setting/eng/item9.xml'),
    ('setting/eng/itemset.xml', 'extracted_paks/update26/setting/eng/itemset.xml'),
    ('setting/eng/pet.xml', 'extracted_paks/update26/setting/eng/pet.xml'),
    ('setting/shop.xml', 'extracted_paks/update26/setting/shop.xml'),
]

def main():
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = pathlib.Path(f'work/backup/u26_fix_{stamp}')
    backup_dir.mkdir(parents=True, exist_ok=True)

    recursos = {}
    for internal_name, src_path in RECURSOS_PATHS:
        p = pathlib.Path(src_path)
        if not p.exists():
            raise FileNotFoundError(f"No existe {p}")
        data = p.read_bytes()
        recursos[internal_name] = data
        recursos[internal_name.replace('/', '\\')] = data
        print(f"Cargado {internal_name}: {len(data)} bytes")

    # 1. Actualizar C:\AO\Angels Online\update26.pak
    if U26_CLIENT.exists():
        print(f"Respaldando {U26_CLIENT}...")
        shutil.copy2(U26_CLIENT, backup_dir / 'update26.pak')
        print(f"Actualizando {U26_CLIENT}...")
        rep, add = pak_tool.actualizar(U26_CLIENT, recursos)
        print(f"  update26.pak cliente: {rep} reemplazados, {add} anadidos.")

    if U26_BAK.exists():
        print(f"Actualizando {U26_BAK}...")
        rep, add = pak_tool.actualizar(U26_BAK, recursos)
        print(f"  update26.pak.bak cliente: {rep} reemplazados, {add} anadidos.")

    if U26_SALIDA.exists():
        print(f"Actualizando {U26_SALIDA}...")
        rep, add = pak_tool.actualizar(U26_SALIDA, recursos)
        print(f"  update26.pak repo salida: {rep} reemplazados, {add} anadidos.")

    # 2. Sincronizar a F:\Ao Proyect\AO 2
    if F_PROYECT.exists():
        print("\nSincronizando a F:\\Ao Proyect\\AO 2...")
        for _, src_rel in RECURSOS_PATHS:
            src_f = pathlib.Path(src_rel)
            dst_f = F_PROYECT / src_rel
            dst_f.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_f, dst_f)
            print(f"  Copiado: {src_rel} -> {dst_f}")

        # Copiar content.db
        src_db = pathlib.Path('corpus/content.db')
        dst_db = F_PROYECT / 'corpus/content.db'
        if src_db.exists() and dst_db.parent.exists():
            shutil.copy2(src_db, dst_db)
            print(f"  Copiado: corpus/content.db -> {dst_db}")

    print("\nProceso completado con exito.")

if __name__ == '__main__':
    main()
