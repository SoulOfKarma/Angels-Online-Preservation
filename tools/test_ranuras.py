import sys
sys.path.insert(0, 'server')
import inventario as inv

for item_id in [10, 19826, 2, 3605, 3396, 20103]:
    print(f"Item {item_id}: es_equipable={inv.es_equipable(item_id)}, ranura={inv.ranura_equipo_de(item_id)}")

