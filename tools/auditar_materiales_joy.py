"""Comprueba los99 enlaces Joy contra MPC+22 y material.xml, solo lectura.

Imprime evidencia JSON reproducible. No infiere materiales por sprite: hay
variantes con el mismo dibujo y diferentes tiempos/premios.
"""
import hashlib,json,pathlib,struct,sys
R=pathlib.Path(__file__).resolve().parent.parent
sys.path[:0]=[str(R/'tools'),str(R/'server')]
from mapa_del_cliente import mapa
from house_services import xml_rows

def auditar():
    materiales=json.loads((R/'server/plantillas/materiales.json').read_text(encoding='utf8'))
    rows=xml_rows('material.xml');result={}
    for stage in (182,372):
        m=mapa(stage);raw=pathlib.Path(m.ruta).read_bytes()
        resources=json.loads((R/f'server/plantillas/daily_{stage}.json').read_text(encoding='utf8'))['recursos']
        records=[]
        for r in resources:
            objects=[o for o in m.objetos if o['id']==r['sprite']and o['tile']==tuple(r['tile'])]
            ids={struct.unpack_from('<H',raw,m.off_objetos+o['i']*74+22)[0]for o in objects}
            assert len(ids)==1,(stage,r['entity_id'],ids)
            mid=next(iter(ids));assert materiales['vetas'][str(stage)][str(r['entity_id'])]==mid
            row=rows[mid];assert int(row['圖號'])==r['sprite']
            stored=materiales['materiales'][str(mid)]
            for dst,src in [('tiempo','採集時間'),('limite','開採上限'),('reponer','重置時間')]:assert stored[dst]==int(row.get(src)or 0)
            records.append(dict(entity=r['entity_id'],material=mid,sprite=r['sprite'],tile=r['tile'],
                objeto_mpc=[o['i']for o in objects],skill=row['使用技能'],nivel=int(row['等級限制']),
                tiempo=stored['tiempo'],limite=stored['limite'],reponer=stored['reponer']))
        assert len(records)==(79 if stage==182 else 20)
        result[str(stage)]=dict(mpc=str(pathlib.Path(m.ruta).relative_to(R)),sha256=hashlib.sha256(raw).hexdigest(),recursos=records)
    return result

if __name__=='__main__':
    print(json.dumps(auditar(),ensure_ascii=True,indent=1))
