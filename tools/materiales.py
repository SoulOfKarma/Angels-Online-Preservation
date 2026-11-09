"""Escribe server/plantillas/materiales.json: lo que da cada veta y que objetos son vetas.

DE DONDE SALE. Dos ficheros del cliente:

  setting/eng/material.xml   cada 物產 (recurso): nombre, cuantas veces se
                             puede sacar (開採上限), cada cuanto se repone
                             (重置時間), lo que tarda (採集時間), la herramienta
                             (裝備限制) y lo que da: 原料NN con 機率NN.
  setting/server.obd         la tabla de objetos del SERVIDOR, en texto: cada
                             [OBJECT] con su Sequence (el id de objeto del
                             .mpc) y su Process. Los de SERV_CLASS_MATOBJ son
                             las vetas, arboles y hierbas que se recolectan.

Y el enlace entre los dos esta en el .mpc: en un objeto MATOBJ el u16 del +22
es el id del material. En la Magic Kichen Path (stage 73) las seis vetas
60243 "物產-01中型礦" llevan ahi el 153, que es el Flint Ore, y el Flint
(4673) es lo que pide el arbol de dialogo de las antorchas.

    python tools/materiales.py
"""
import json
import os
import pathlib
import re
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))

import paks

SALIDA = RAIZ / 'server' / 'plantillas' / 'materiales.json'


def materiales():
    raiz = ET.fromstring(paks.texto('material.xml'))
    salida = {}
    for m in raiz.iter('物產'):
        items = []
        for k in range(1, 21):
            it, pr = m.get('原料%02d' % k), m.get('機率%02d' % k)
            if it and pr:
                items.append([int(it), int(pr)])
        salida[m.get('編號')] = {
            'nombre': m.get('名稱') or '',
            'limite': int(m.get('開採上限') or 0),
            'reponer': int(m.get('重置時間') or 0),
            'tiempo': int(m.get('採集時間') or 0),
            'herramienta': m.get('裝備限制') or '',
            'no_produce': int(m.get('不產機率') or 0),
            'items': items}
    return salida


def objetos_material():
    """Los ids de objeto de clase SERV_CLASS_MATOBJ, con su nombre interno."""
    txt = paks.texto('server.obd')
    salida = {}
    for blk in txt.split('[OBJECT]')[1:]:
        seq = re.search(r'Sequence\s*=\s*(\d+)', blk)
        pro = re.search(r'Process\s*=\s*(\w+)', blk)
        nom = re.search(r'Name\s*=\s*(.*)', blk)
        if seq and pro and pro.group(1) == 'SERV_CLASS_MATOBJ':
            salida[seq.group(1)] = nom.group(1).strip() if nom else ''
    return salida


def vetas_de_plantillas(objs, solo=None):
    """{stage: {entity_id: material}} de las vetas que YA mandan las plantillas.

    Las plantillas de los mapas abiertos traen sus vetas, arboles y hierbas
    copiados de capturas del IGG, pero solo con el px: ni casilla ni
    material. El material esta en el .mpc (u16 +22 del objeto), asi que cada
    veta de la plantilla se casa con el objeto del .mpc del mismo sprite mas
    cercano. Medido en Riprap Coast, Blue Sea y Mushroom Forest: todas caen a
    24 px o menos del suyo, con la x tal cual y la y = casilla*32+16.
    """
    sys.path.insert(0, str(RAIZ / 'server'))
    import mapa_del_cliente as mc
    import login as lg
    vetas = {int(k) for k in objs}
    mapas = mc.mapas_del_cliente()
    salida = {}
    plantillas = dict(lg.PLANTILLAS_POR_STAGE)
    # Daily se carga por su controlador, fuera de PLANTILLAS_POR_STAGE.
    # Los MATOBJ de Joy tambien llevan el material exacto en MPC+22.
    for stage in (182, 372):
        plantillas[stage] = 'daily_%d.json' % stage
    for stage, fichero in sorted(plantillas.items()):
        if solo is not None and stage not in solo:
            continue
        f = RAIZ / 'server' / 'plantillas' / fichero
        if stage not in mapas or not f.exists():
            continue
        rec = [r for r in json.loads(f.read_text(encoding='utf-8')).get('recursos') or []
               if r.get('sprite') in vetas and r.get('px')]
        if not rec:
            continue
        ruta = mapas[stage]
        m = mc.Mapa(stage, ruta)
        crudo = ruta.read_bytes() if hasattr(ruta, 'read_bytes') else open(ruta, 'rb').read()
        libres = []
        for o in m.objetos:
            if o['id'] in vetas:
                mat = struct.unpack_from('<H', crudo, m.off_objetos + o['i'] * 74 + 22)[0]
                if mat:
                    libres.append((o['id'], o['px'][0], o['tile'][1] * 32 + 16, mat))
        casadas = {}
        for r in rec:
            # Las de instancia (objetos_de_instancia.py) ya traen el id. En
            # las demas 'material' es el NOMBRE (nombrar_recursos.py).
            if isinstance(r.get('material'), int):
                casadas[str(r['entity_id'])] = r['material']
                continue
            cand = [(abs(x - r['px'][0]) + abs(y - r['px'][1]), k)
                    for k, (sp, x, y, _m) in enumerate(libres) if sp == r['sprite']]
            if not cand:
                continue
            dist, k = min(cand)
            if dist > 64:
                continue
            casadas[str(r['entity_id'])] = libres.pop(k)[3]
        if casadas:
            salida[str(stage)] = casadas
    return salida


def main():
    if '--solo-daily' in sys.argv or '--comprobar-daily' in sys.argv:
        data = json.loads(SALIDA.read_text(encoding='utf-8'))
        vetas = vetas_de_plantillas(data['objetos_material'], solo={182, 372})
        for stage in (182, 372):
            recursos = json.loads((SALIDA.parent / ('daily_%d.json' % stage)).read_text(encoding='utf-8'))['recursos']
            assert len(vetas.get(str(stage), {})) == len(recursos), ('Joy sin vincular', stage)
            assert all(str(mid) in data['materiales'] for mid in vetas[str(stage)].values())
        if '--comprobar-daily' in sys.argv:
            assert all(data['vetas'].get(stage) == rows for stage, rows in vetas.items())
            print('Joy: %d vinculos coinciden con MPC+22' % sum(map(len, vetas.values())))
        else:
            data['vetas'].update(vetas)
            SALIDA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            print('Joy: %d vinculos actualizados; resto de materiales conservados' % sum(map(len, vetas.values())))
        return
    mats, objs = materiales(), objetos_material()
    vetas = vetas_de_plantillas(objs)
    SALIDA.write_text(json.dumps({
        'comentario': ('Generado por tools/materiales.py desde material.xml y '
                       'server.obd del cliente. No editar a mano.'),
        'materiales': mats,
        'objetos_material': objs,
        'vetas': vetas}, ensure_ascii=False, indent=1) + '\n',
        encoding='utf-8')
    print('%s: %d materiales, %d objetos de material' % (SALIDA, len(mats), len(objs)))
    print('   vetas casadas: %d en %d mapas' % (sum(len(v) for v in vetas.values()), len(vetas)))
    print('   153 ->', mats.get('153'))


if __name__ == '__main__':
    # Los imports del servidor pueden inicializar cuentas; el exportador
    # de contenido nunca necesita ni debe abrir la base de juego real.
    with tempfile.TemporaryDirectory(prefix='ao_materiales_') as cuentas:
        os.environ['AO_DATOS'] = cuentas
        main()
