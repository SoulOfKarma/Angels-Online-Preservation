# -*- coding: utf-8 -*-
"""
Restaura el formateador dinámico /c$2%s/c* en las descripciones de lucky bags y cofres
de item4.xml hasta item9.xml, y traduce items pendientes como el martillo 78384.
"""
import os
import sqlite3
import xml.etree.ElementTree as ET

BACKUP_DIR = 'work/backup/item9_completo_20261026_233046'
TARGET_DIR = 'extracted_paks/update26/setting/eng'
DB_PATH = 'corpus/content.db'

FILES = ['item4.xml', 'item5.xml', 'item6.xml', 'item7.xml', 'item8.xml', 'item9.xml']

def restore_description(b_desc: str, c_desc: str) -> str:
    token = '/c$2%s/c*'
    b_stripped = b_desc.strip()
    
    # 1. Si el backup era puramente el token
    if b_stripped in [token, '%s']:
        return b_desc
        
    # 2. Si el backup empezaba con el token
    if b_stripped.startswith(token) or b_stripped.startswith('%s'):
        actual_tok = token if token in b_desc else '%s'
        c_stripped = c_desc.strip()
        if not c_stripped:
            return actual_tok
        if c_desc.startswith('\n'):
            return actual_tok + c_desc
        else:
            return actual_tok + '\n' + c_desc
            
    # 3. Si el backup terminaba con el token
    if b_stripped.endswith(token) or b_stripped.endswith('%s'):
        actual_tok = token if token in b_desc else '%s'
        c_stripped = c_desc.strip()
        if not c_stripped:
            return actual_tok
        if c_desc.endswith('\n'):
            return c_desc + actual_tok
        else:
            return c_desc + '\n' + actual_tok
            
    # 4. En cualquier otro caso fallback respetando posición
    idx = b_desc.find('%s')
    if idx != -1:
        prefix = b_desc[:idx]
        suffix = b_desc[idx+2:]
        return f"{prefix}%s{suffix}"
        
    return c_desc

def main():
    total_restored = 0
    all_restored_items = {} # iid -> (name, new_desc)

    for fname in FILES:
        b_path = os.path.join(BACKUP_DIR, fname)
        c_path = os.path.join(TARGET_DIR, fname)
        if not os.path.exists(b_path) or not os.path.exists(c_path):
            print(f"Saltando {fname} (no existe backup o destino)")
            continue

        tb = ET.parse(b_path)
        tc = ET.parse(c_path)
        
        b_map = {el.attrib.get('編號'): el.attrib.get('說明定義', '') for el in tb.getroot()}
        
        file_restored = 0
        for el in tc.getroot():
            iid = el.attrib.get('編號')
            if not iid:
                continue
                
            # Corrección especial 78384: Weighted Wooden Hammer
            if iid == '78384' and el.attrib.get('基本名稱') == '附重木錘':
                el.attrib['基本名稱'] = 'Weighted Wooden Hammer'
                print("Item 78384 traducido a 'Weighted Wooden Hammer'")
                
            b_desc = b_map.get(iid)
            if b_desc and ('%s' in b_desc):
                c_desc = el.attrib.get('說明定義', '')
                if '%s' not in c_desc:
                    new_desc = restore_description(b_desc, c_desc)
                    el.attrib['說明定義'] = new_desc
                    file_restored += 1
                    all_restored_items[iid] = (el.attrib.get('基本名稱', ''), new_desc)

        print(f"{fname}: {file_restored} descripciones restauradas.")
        total_restored += file_restored

        # Guardar XML con declaración UTF-8
        tc.write(c_path, encoding='utf-8', xml_declaration=True)

    print(f"\nTotal items restaurados: {total_restored}")

    # Sincronizar en content.db
    if os.path.exists(DB_PATH):
        print(f"Actualizando {DB_PATH}...")
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Verificar tablas existentes
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"Tablas encontradas en content.db: {tables}")
        
        # Actualizar en tabla item si existe
        if 'item' in tables:
            # Obtener columnas de item
            cur.execute("PRAGMA table_info(item)")
            cols = [r[1] for r in cur.fetchall()]
            desc_col = 'desc' if 'desc' in cols else ('description' if 'description' in cols else ('說明定義' if '說明定義' in cols else None))
            name_col = 'name' if 'name' in cols else ('基本名稱' if '基本名稱' in cols else None)
            id_col = 'id' if 'id' in cols else ('編號' if '編號' in cols else None)
            
            print(f"Columnas detectadas en 'item': id={id_col}, name={name_col}, desc={desc_col}")
            if id_col and desc_col:
                updated_db = 0
                for iid, (iname, ndesc) in all_restored_items.items():
                    cur.execute(f"UPDATE item SET {desc_col} = ? WHERE {id_col} = ?", (ndesc, iid))
                    if cur.rowcount > 0:
                        updated_db += 1
                print(f"Actualizados {updated_db} registros en tabla 'item'.")
                
                # Actualizar 78384 en DB
                if name_col:
                    cur.execute(f"UPDATE item SET {name_col} = 'Weighted Wooden Hammer' WHERE {id_col} = '78384'")
                    print(f"Item 78384 actualizado en DB con name='Weighted Wooden Hammer' (rows={cur.rowcount}).")
                    
        # Actualizar en tabla item9 si existe
        if 'item9' in tables:
            cur.execute("PRAGMA table_info(item9)")
            cols = [r[1] for r in cur.fetchall()]
            desc_col = 'desc' if 'desc' in cols else ('description' if 'description' in cols else ('說明定義' if '說明定義' in cols else None))
            id_col = 'id' if 'id' in cols else ('編號' if '編號' in cols else None)
            if id_col and desc_col:
                updated_db9 = 0
                for iid, (iname, ndesc) in all_restored_items.items():
                    cur.execute(f"UPDATE item9 SET {desc_col} = ? WHERE {id_col} = ?", (ndesc, iid))
                    if cur.rowcount > 0:
                        updated_db9 += 1
                print(f"Actualizados {updated_db9} registros en tabla 'item9'.")

        conn.commit()
        conn.close()
        print("content.db sincronizado exitosamente.")

if __name__ == '__main__':
    main()
