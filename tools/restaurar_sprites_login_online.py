# -*- coding: utf-8 -*-
"""
Restaura los sprites en ingles para Login Rewards y Online Rewards
(SHAPE\\ACTBOARD\\BTN_LOGIN.SHP, BTN_LOGIN2.SHP, BTN_ONLINE.SHP, BTN_ONLINE2.SHP)
extrayendolos de update24.pak y actualizando update29.pak.
"""
import pathlib
import shutil
from tools import pak_tool

C_AO = pathlib.Path(r'C:\AO\Angels Online')
U24_PATH = C_AO / 'update24.pak'
U29_PATH = C_AO / 'update29.pak'
SALIDA_U29 = pathlib.Path('work/salida/paks/update29.pak')

TARGETS = [
    'shape\\actboard\\btn_login.shp',
    'shape\\actboard\\btn_login2.shp',
    'shape\\actboard\\btn_online.shp',
    'shape\\actboard\\btn_online2.shp',
]

def main():
    if not U24_PATH.exists():
        raise FileNotFoundError(f"No se encontro {U24_PATH}")
    if not U29_PATH.exists():
        raise FileNotFoundError(f"No se encontro {U29_PATH}")

    print("Leyendo sprites de update24.pak...")
    u24_data = U24_PATH.read_bytes()
    u24_entries, _ = pak_tool.leer_indice(u24_data)
    targets_lower = {t.lower(): t for t in TARGETS}

    nuevos = {}
    for e in u24_entries:
        nl = e['nombre'].lower()
        if nl in targets_lower:
            raw = pak_tool.leer_entrada(u24_data, e)
            nuevos[e['nombre']] = raw
            print(f"  Extraido: {e['nombre']} ({len(raw)} bytes)")

    if len(nuevos) != 4:
        raise RuntimeError(f"Solo se encontraron {len(nuevos)} de 4 sprites en update24.pak")

    # Guardar copia de los sprites extraidos en extracted_paks/update26 por si acaso
    ext_dir = pathlib.Path('extracted_paks/update26/shape/actboard')
    ext_dir.mkdir(parents=True, exist_ok=True)
    for k, v in nuevos.items():
        fname = pathlib.Path(k).name
        (ext_dir / fname).write_bytes(v)
    print(f"Sprites guardados en {ext_dir}")

    # Respaldar update29.pak en C:\AO\Angels Online
    bak_path = C_AO / 'update29.pak.bak_sprites'
    if not bak_path.exists():
        print(f"Creando respaldo {bak_path.name}...")
        shutil.copy2(U29_PATH, bak_path)

    print("Actualizando C:\\AO\\Angels Online\\update29.pak...")
    rep, add = pak_tool.actualizar(U29_PATH, nuevos)
    print(f"  update29.pak en cliente actualizado: {rep} reemplazados, {add} anadidos.")

    if SALIDA_U29.exists():
        print("Actualizando work/salida/paks/update29.pak...")
        rep_s, add_s = pak_tool.actualizar(SALIDA_U29, nuevos)
        print(f"  update29.pak en repo actualizado: {rep_s} reemplazados, {add_s} anadidos.")

    print("Restauracion de sprites completada con exito.")

if __name__ == '__main__':
    main()
