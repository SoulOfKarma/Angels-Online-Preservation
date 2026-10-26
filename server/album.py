"""El Album de equipo (Ctrl+B): valor de coleccion y sus bonos.

Metes piezas en el album, se CONSUMEN, y a cambio cada categoria acumula
valor. Al pasar de cada umbral se gana un bono pasivo permanente.

La tabla sale de setting/eng/collection.xml, que solo trae UPDATE8: 90
filas, nueve categorias por diez niveles, cada una con su umbral y su bono.
La novena, `total`, mira la suma de las otras ocho.

    arma  nv 1  umbral    704  ->  atk +140, matk +70
    arma  nv 10 umbral  46900  ->  atk +460, matk +230
    total nv 10 umbral 113300  ->  hp +1%, mp +1%, exp +3

El valor base se calcula con la formula del cliente705d50 y sus tablas
705dd0/705e40: nivel al cuadrado, atributos de la pieza, categoria y color.
S2C0156 serializa las filas de la coleccion;5f5120 lee sus registros.
"""
import json
import pathlib
import functools
import math
import struct

CATEGORIAS = ('arma', 'tocado', 'ropa', 'guantes', 'zapatos',
              'montura', 'accesorio', 'apariencia')

# De la categoria de item.xml a la del album.
POR_CATEGORIA_ITEM = {
    '劍': 'arma', '刀': 'arma', '斧': 'arma', '錘': 'arma', '槍': 'arma',
    '杖': 'arma', '弓箭': 'arma', '彈弓': 'arma', '影刃': 'arma',
    '頭飾': 'tocado', '衣服': 'ropa', '手套': 'guantes', '鞋子': 'zapatos',
    '座騎': 'montura', '機甲': 'montura',
    '飾品': 'accesorio', '披風': 'accesorio', '盾': 'accesorio',
    '紙娃娃': 'apariencia',
}

_TABLA = None


def tabla() -> list:
    """Las 90 filas de collection.xml, de plantillas/album.json."""
    global _TABLA
    if _TABLA is None:
        f = pathlib.Path(__file__).parent / 'plantillas' / 'album.json'
        try:
            _TABLA = json.loads(f.read_text(encoding='utf-8'))['filas']
        except Exception:
            _TABLA = []
    return _TABLA


def categoria_de(item_id: int) -> str:
    """En que pagina del album entra ese objeto, o '' si no entra."""
    try:
        import inventario as _iv
        cat = _iv.categoria_de(item_id) or ''
    except Exception:
        return ''
    for chino, nom in POR_CATEGORIA_ITEM.items():
        if chino in cat:
            return nom
    return ''


@functools.lru_cache(maxsize=1)
def _items():
    from house_services import xml_rows
    return {i:r for n in range(1,10) for i,r in xml_rows('item%s.xml'%(n if n>1 else '')).items()}


# Native categories0..7: Weapon, Headwear, Attire, Gloves, Shoes, Robot,
# Mantle, Appearance. Preserve the legacy saved category names.
_CATEGORY={**{k:0 for k in ('\u528d','\u5200','\u65a7','\u939a','\u69cd','\u6756','\u5f13\u7bad','\u5f48\u5f13','\u5f71\u5203')},
           '\u982d\u98fe':1,'\u8863\u670d':2,'\u624b\u5957':3,'\u9774\u5b50':4,
           '\u5ea7\u9a0e':5,'\u6a5f\u7532':5,'\u62ab\u98a8':6,'\u76fe':6}


def descripcion(item_id,extra=None):
    """Native705d50/705dd0/705e40 score and5f5300 level/color row."""
    import inventario
    row=_items().get(int(item_id or 0),{})
    if row.get('\u7269\u54c1\u985e\u5225')=='\u7d19\u5a03\u5a03':
        return _apariencia(row)
    category=_CATEGORY.get(row.get('\u7269\u54c1\u985e\u5225'))
    if category is None:return None
    color={'':0,'\u767d':0,'\u85cd':1,'\u9ec3':2}.get(row.get('\u984f\u8272',''))
    level=int(row.get('\u7269\u54c1\u7b49\u7d1a') or 0)
    if color is None or level<=0 or int(row.get('\u6301\u7e8c\u6642\u9593') or 0)>0:return None
    slot=(3,1,2,5,6,8,7)[category]
    #514e50 counts additional attributes, gems and enhancement; it does NOT
    #add the item's base attack/defense a second time on top of level squared.
    modifiers=dict(extra or {});greens=modifiers.pop('extra',{}) or {}
    base=inventario.bonos_de_equipo({slot:item_id})
    equipped=inventario.bonos_de_equipo({slot:item_id},mejoras={slot:modifiers})
    delta={k:equipped[k]-v for k,v in base.items()}
    stat_sum=sum(v for k,v in delta.items() if k!='atk_l')+sum(int(v) for v in greens.values())
    # Native stat blocks keep both min/max attack. The equipment helper
    #folds accuracy into the right-hand attack, which must be removed here.
    stat_sum+=delta.get('atk_r',0)-(2*delta.get('accuracy',0) if category==0 else 0)
    weight=(225,45,72,32,30,100,75)[category]
    multiplier=(1,2,5)[color]
    if category==5:multiplier=(2,5,0)[color]
    if not multiplier:return None
    value=math.ceil((level*level*.3+stat_sum)*weight*.01*.0072)*multiplier
    bucket=0 if level<100 else min(4,(level-100)//20+1)
    return category,color,bucket,max(1,min(0x1ffff,int(value)))


def _apariencia(row):
    """Doll collection theme aliases and705e80; five copies per cell."""
    from house_services import xml_rows
    if int(row.get('\u6301\u7e8c\u6642\u9593') or 0)>0:return None
    doll=xml_rows('doll.xml').get(int(row.get('\u539f\u578b\u5916\u89c0') or 0),{})
    # Native VALUE aliases at the end of the current doll.xml.
    themes={'\u5404\u570b\u98a8\u60c5':1,'\u53ef\u611b\u52d5\u7269':2,
            '\u7e7d\u7d1b\u8077\u696d':3,'\u6b61\u6a02\u7bc0\u6176':4,'\u7279\u6b8a\u5176\u4ed6':5}
    theme=themes.get(doll.get('\u6536\u85cf\u985e\u5225'))
    color={'':0,'\u767d':0,'\u85cd':1,'\u9ec3':2}.get(row.get('\u984f\u8272',''))
    if theme is None or color is None:return None
    cell=_tipo_apariencia(doll)
    if cell is None:return None
    value=(7,10,5,5)[cell]*(1,2,5)[color]
    # Registrar needs the apparel type rather than choosing a free grid.
    return 7,color,theme,value


def _tipo_apariencia(doll):
    #5f5d40 tests head before body, gloves and feet.
    groups=(('\u982d\u90e8\u88dd\u5099','\u982d\u90e8\u534a\u7f69','\u982d\u90e8\u5168\u7f69'),
            ('\u8eab\u9ad4\u88dd\u5099','\u8eab\u9ad4\u888d','\u8b8a\u8eab\u63db\u5716'),
            ('\u624b\u90e8\u88dd\u5099',),('\u8173\u90e8\u88dd\u5099',))
    return next((i for i,keys in enumerate(groups) if any(doll.get(k)=='\u662f' for k in keys)),None)


def valor_de(item_id,extra=None):
    desc=descripcion(item_id,extra)
    return desc[3] if desc else 0


def registros(valores):
    if '_entries' in valores:return [list(r) for r in valores['_entries']]
    # Older saves only retained category totals. Represent those totals as
    # legacy cells instead of erasing previously earned points on migration.
    result=[]
    for category,key in enumerate(CATEGORIAS):
        remaining=max(0,int(valores.get(key,0)))
        for cell in range(4):
            if not remaining:break
            value=min(0x1ffff,remaining);result.append([category,0,4,cell,value]);remaining-=value
    return result


def paquete(personaje):
    """S2C0156: expansion mask,u16 count per category,packed32-bit cells."""
    values=getattr(personaje,'album',None) or {};records=registros(values)
    counts=[0]*8;words=[]
    for category in range(8):
        rows=[r for r in records if r[0]==category]
        counts[category]=len(rows)
        for _,color,bucket,cell,value in rows:
            words.append((color<<30)|(bucket<<20)|(cell<<17)|value)
    return struct.pack('<HI8H',0x156,int(values.get('_expanded',0)),*counts)+struct.pack('<%dI'%len(words),*words)


def registrar(ses,slot):
    import app,clases,recent_mall
    item=ses.inventario.get(slot)
    def reject(text):ses.enviar(clases.aviso(text,tipo=0));return False
    if not 20<=slot<160:return reject('Move the item to your backpack before adding it to the Album.')
    if (__import__('arena_premios_compat').es_premio(ses,slot)
            or __import__('item_mall').es_temporal(ses,slot)
            or __import__('furniture_items').protegido(ses,slot)):
        return reject('Temporary or registered items cannot be added to the Album.')
    description=descripcion(item,(ses.personaje.mejoras or {}).get(slot))
    if description is None:return reject('This item cannot be added to the Album.')
    category,color,bucket,value=description
    updated=[]
    def collect(con,data):
        values=dict(data.get('album') or {});records=registros(values)
        limit=5 if int(values.get('_expanded',0))&(1<<(color+4*category)) else 4
        cells={r[3]:r for r in records if r[:3]==[category,color,bucket]}
        if category==7:
            from house_services import xml_rows
            row=_items()[item]
            doll=xml_rows('doll.xml').get(int(row.get('\u539f\u578b\u5916\u89c0') or 0),{})
            cell=_tipo_apariencia(doll)
            old=cells.get(cell)
            if old and old[4]+value>value*5:
                raise recent_mall.Rechazo('This Appearance grid already contains five copies.')
            if old:old[4]+=value
            else:records.append([category,color,bucket,cell,value])
        else:
            cell=next((i for i in range(limit) if i not in cells),None)
            if cell is None:
                cell=min(cells,key=lambda k:cells[k][4])
                if cells[cell][4]>=value:raise recent_mall.Rechazo('The Album already contains stronger equipment in these grids.')
                records.remove(cells[cell])
            records.append([category,color,bucket,cell,value])
        values['_entries']=records
        for index,key in enumerate(CATEGORIAS):values[key]=sum(r[4] for r in records if r[0]==index)
        data['album']=values;updated.append(values)
    try:recent_mall.cambiar(ses,{slot:1},[],transaccion=collect)
    except recent_mall.Rechazo as exc:return reject(str(exc))
    ses.personaje.album=updated[0]
    ses.enviar(paquete(ses.personaje),app._stats_ses(ses),clases.aviso('Added to Album: %s (+%d collection value).'%(app._nombre_item(item),value),tipo=0))
    return True


def bono_buff(personaje):
    raw=bonos(getattr(personaje,'album',None) or {})
    aliases={'dfs':'def','rigor':'hit','agilidad':'eva','hp':'hp_bonus','mp':'mp_bonus',
             'critico':'crit','peso':'carga','res_con':'res_body','res_spr':'res_mind',
             'res_rayo':'res_lightning','res_fuego':'res_fire','res_hielo':'res_ice',
             'res_corrosion':'res_corrosion','velocidad':'move_speed_bonus',
             'vel_fabricacion':'fabricacion_pct','vel_recoleccion':'recoleccion_pct','exp':'exp_extra_pct'}
    return {((aliases.get(k,k) if not isinstance(v,dict) else k+'_pct')):
            (v.get('pct',0) if isinstance(v,dict) else v) for k,v in raw.items()}


def nivel_alcanzado(categoria: str, valor: int) -> int:
    """El nivel mas alto de esa categoria cuyo umbral ya se paso."""
    nv = 0
    for f in tabla():
        if f['categoria'] == categoria and valor >= f['valor']:
            nv = max(nv, f['nivel'])
    return nv


def bonos(valores: dict) -> dict:
    """Los bonos que dan esos valores por categoria.

    `valores` es {categoria: valor}. Se suma el bono de la categoria y, al
    final, el de `total` con la suma de las ocho. Se acumulan los de todos
    los niveles alcanzados, no solo el ultimo.
    """
    fuera = {}

    def _sumar(b):
        for k, v in b.items():
            if isinstance(v, dict):          # {'pct': n}
                prev = fuera.get(k)
                if isinstance(prev, dict):
                    prev['pct'] = prev.get('pct', 0) + v.get('pct', 0)
                else:
                    fuera[k] = dict(v)
            else:
                prev = fuera.get(k)
                fuera[k] = (prev + v) if isinstance(prev, int) else v

    for cat in CATEGORIAS:
        val = int(valores.get(cat, 0) or 0)
        for f in tabla():
            if f['categoria'] == cat and val >= f['valor']:
                _sumar(f['bonos'])
    total = sum(int(valores.get(c, 0) or 0) for c in CATEGORIAS)
    for f in tabla():
        if f['categoria'] == 'total' and total >= f['valor']:
            _sumar(f['bonos'])
    return fuera


def resumen(valores: dict) -> dict:
    """Lo que necesita la ventana: valor y nivel de cada pagina."""
    out = {c: {'valor': int(valores.get(c, 0) or 0),
               'nivel': nivel_alcanzado(c, int(valores.get(c, 0) or 0))}
           for c in CATEGORIAS}
    total = sum(v['valor'] for v in out.values())
    out['total'] = {'valor': total, 'nivel': nivel_alcanzado('total', total)}
    return out
