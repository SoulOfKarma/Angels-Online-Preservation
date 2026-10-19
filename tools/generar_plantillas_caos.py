import sys
import json
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import poblar_del_cliente

for stage, nombre, boss_extra in [
    (413, 'c_dinosaur_arena', None),
    (414, 'c_end_time', {
        'entity_id': 81400999,
        'nombre': "Ba'shin",
        'npc_type': 23839,
        'sprite': 111551,
        'klass': 1,
        'monstruo': True,
        'tile': [142, 95],
        'direccion': 2,
        'visible': 0,
        'nivel': 470
    })
]:
    sp, _ = poblar_del_cliente.spawns_de(stage, con_zonas_de_evento=True)
    if boss_extra:
        sp.append(boss_extra)
    rec, _ = poblar_del_cliente.recursos_de(stage)
    dest = pathlib.Path(__file__).parent.parent / 'server' / 'plantillas' / f'{nombre}.json'
    dest.write_text(json.dumps({
        '_nota': poblar_del_cliente.NOTA % (nombre, stage, stage),
        'stage': stage,
        'spawns': sp,
        'recursos': rec,
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    mobs = sum(1 for e in sp if e.get('monstruo'))
    print(f"{nombre}.json: {len(sp)} spawns ({mobs} monsters, {len(sp)-mobs} NPCs) and {len(rec)} map objects")

