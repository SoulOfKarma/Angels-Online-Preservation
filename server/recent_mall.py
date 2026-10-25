"""Recent IGG bags and voucher exchanges; atomic inventory changes."""
import functools
import json
import pathlib
import random
import struct
import time


@functools.lru_cache(maxsize=1)
def datos():
    return json.loads((pathlib.Path(__file__).parent/'plantillas/recent_mall.json').read_text('utf8'))


class Rechazo(ValueError):pass


def _aviso(ses,text):
    import clases
    ses.enviar(clases.aviso(text,tipo=0))


def cerca(ses,name):
    p=ses.personaje
    return p.stage==41 and any(n['nombre']==name and
        max(abs(p.tile_x-n['tile'][0]),abs(p.tile_y-n['tile'][1]))<=4 for n in datos()['npcs'])


def poblar(stage):
    if stage!=41:return []
    import login
    # Gear Clerk is already present in lyceum.json; Fashionable was missing.
    return [login._npc_spawn(n['entity_id'],n['npc_type'],n['nombre'],tuple(n['tile']),
                            sprite=n['sprite'],klass=200,direccion=n['direccion'])
            for n in datos()['npcs'] if n['nombre']!='Gear Clerk']


def pulsar(ses,ent,addr):
    if ses.personaje.stage!=41:return False
    for n in datos()['npcs']:
        if n['entity_id']!=ent:continue
        if cerca(ses,n['nombre']) and not getattr(ses,'muerto',False):
            import app
            ses._recent_mall_npc=n['nombre'];ses._lyceum_exchange=None
            app._recorrer_dialogo_mapa(ses,addr,41,n['root'])
        return True
    return False


def antes_dialogo(ses,stage,node):
    if stage!=41 or str(node) not in datos()['nodes']:return False
    owner=datos()['node_owners'][str(node)]
    if getattr(ses,'_recent_mall_npc',None)!=owner or not cerca(ses,owner):return True
    if owner=='Daily Events Clerk' and any(a[0]==108 for a in datos()['nodes'][str(node)].get('a',[])):
        __import__('daily_events').claim(ses)
        return True
    groups=[a[1][0] for a in datos()['nodes'][str(node)].get('a',[]) if a[0]==98]
    if groups:
        ses._lyceum_exchange=groups[0]
        ses.enviar(struct.pack('<HI',0x0151,groups[0]))
        return True
    return False


def cambiar(ses,consume,rewards,transaccion=None):
    """Validate the entire batch and commit once, preserving other character data.

    consume is an exact slot->quantity map, rewards are item/quantity pairs.
    No session changes or success packets occur before a successful SQL commit.
    """
    import app,cuentas,inventario
    p=ses.personaje
    if getattr(ses,'muerto',False) or getattr(ses,'mapa_cargando',False):
        raise Rechazo('Wait until your character is ready.')
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',(ses.usuario,p.char_id)).fetchone()
        if not row:raise Rechazo('Character not found.')
        data=json.loads(row[0])
        if not cuentas.inventario_equivalente(data,ses.inventario,app._cantidades(ses)):
            raise Rechazo('Inventory changed. Reconnect before trying again; no items were consumed.')
        bag,counts=dict(ses.inventario),dict(app._cantidades(ses))
        upgrades={int(k):dict(v) for k,v in data.get('mejoras',{}).items()}
        changed=set();fresh=set()
        for slot,qty in consume.items():
            if not 20<=slot<=app._tope_bolsa(bag) or slot not in bag or not 0<qty<=counts.get(slot,1):
                raise Rechazo('The required item is no longer available.')
            if upgrades.get(slot,{}).get('mall_fin',float('inf'))<=time.time():
                raise Rechazo('This item has expired.')
            counts[slot]=counts.get(slot,1)-qty;changed.add(slot)
            if not counts[slot]:bag.pop(slot);counts.pop(slot);upgrades.pop(slot,None)
        for item,remaining in rewards:
            duration=datos()['items'].get(str(item),{}).get('duration',0)
            deadline=time.time()+duration*60 if duration else None
            stackable=inventario.es_apilable(item)
            while remaining:
                slot=next((s for s,it in sorted(bag.items()) if stackable and not deadline and it==item
                           and 20<=s<=app._tope_bolsa(bag) and not upgrades.get(s) and counts.get(s,1)<999),None)
                if slot is None:
                    slot=app._ranura_libre(bag)
                    if slot is None:raise Rechazo('Your backpack is full; no items were consumed.')
                    bag[slot]=item;counts[slot]=0;fresh.add(slot);upgrades.pop(slot,None)
                    if deadline:upgrades[slot]={'mall_fin':deadline,'mall_item':item}
                amount=min(remaining,999-counts.get(slot,1)) if stackable else 1
                counts[slot]=counts.get(slot,1)+amount;remaining-=amount;changed.add(slot)
        data.update(inventario={str(k):v for k,v in bag.items()},cantidades={str(k):v for k,v in counts.items()},
                    mejoras={str(k):v for k,v in upgrades.items()})
        if transaccion is not None:transaccion(con,data)
        upgrades={int(k):dict(v) for k,v in data.get('mejoras',{}).items()}
        con.execute('UPDATE personajes SET datos=? WHERE usuario=? AND char_id=?',(json.dumps(data),ses.usuario,p.char_id))
    ses.inventario.clear();ses.inventario.update(bag)
    app._cantidades(ses).clear();app._cantidades(ses).update(counts)
    p.inventario,p.cantidades,p.mejoras=ses.inventario,app._cantidades(ses),upgrades
    for slot in changed:
        if slot not in bag:app._instancias(ses).pop(slot,None)
        elif slot in fresh:app._instancias(ses)[slot]=inventario.instancia_nueva()
    cuentas._notificar_cambio(inmediato=True)
    ses.enviar(*app._refrescar(ses,sorted(changed)))
    import clases,misiones
    for item,qty in rewards:
        ses.enviar(clases.aviso('You received %s x%d.'%(app._nombre_item(item),qty),tipo=0))
    ses.enviar(*misiones.verificar_progreso_recoleccion(ses,[i for i,_ in rewards]))


def usar(ses,slot):
    item=ses.inventario.get(slot);meta=datos()['items'].get(str(item))
    if meta is None:return False
    if meta.get('unsupported_box'):
        _aviso(ses,'The original reward table for this box is unavailable. The box was not consumed.')
        return True
    if (getattr(ses.personaje,'mejoras',{}) or {}).get(slot,{}).get('mall_fin',float('inf'))<=time.time():
        import item_mall
        item_mall.caducados(ses)
        _aviso(ses,'This item has expired.');return True
    level=meta['level'];current=ses.personaje.nivel
    if level>0 and current<level or level<0 and current>-level:
        _aviso(ses,'Requires level %d%s.'%(abs(level),' or below' if level<0 else ' or above'));return True
    box=datos()['boxes'].get(str(item))
    if not box:return False
    rewards=box['rewards']
    if box['mode']=='random':
        # Preserve the individual XML weights, including repeated prizes at
        # different quantities. Fixed bundles have no prob fields at all.
        rewards=random.choices(rewards,weights=[r[2] for r in rewards],k=1)
    try:cambiar(ses,{slot:1},[(i,n) for i,n,_ in rewards])
    except Rechazo as exc:_aviso(ses,str(exc))
    return True


def ajustar_buff(item,entry):
    """The four Newbie boosts also affect gathering/crafting, and survive death."""
    if item not in (82000,82001,82002,82003):return
    from house_services import xml_rows
    magic=xml_rows('magic.xml')[entry['mag']['id']]
    for source,target in (('\u63a1\u96c6\u901f\u5ea6','recoleccion_pct'),
                          ('\u88fd\u4f5c\u901f\u5ea6','fabricacion_pct'),
                          ('\u7d93\u9a57\u52a0\u500d','exp_extra_pct'),
                          ('\u6280\u80fd\u7d93\u9a57\u52a0\u500d','skill_exp_extra_pct')):
        if magic.get(source):entry[target]=int(magic[source])
    entry['persist_death']=magic.get('\u6b7b\u4ea1\u4e0d\u6d88\u5931')=='\u662f'


def canjear(ses,recipe_id,times):
    import app
    from house_services import xml_rows
    row=xml_rows('exchange.xml').get(int(recipe_id),{})
    group=str(row.get('\u7fa4\u7d44') or '')
    owner=datos()['exchange_owners'].get(group)
    if not owner:return False
    if (not cerca(ses,owner) or getattr(ses,'_lyceum_exchange',None)!=int(group)
            or getattr(ses,'_recent_mall_npc',None)!=owner):
        _aviso(ses,'Open this exchange at %s first.'%owner);return True
    recipe=app._obtener_receta_exchange(recipe_id)
    if not recipe or not recipe['materiales'] or not recipe['premios']:
        _aviso(ses,'Invalid exchange recipe.');return True
    if any(datos()['items'].get(str(i),{}).get('unsupported_box') for i,_ in recipe['premios']):
        _aviso(ses,'The original contents of this reward box are unavailable. No materials were consumed.');return True
    times=max(1,min(100,int(times)));consume={}
    for item,qty in recipe['materiales']:
        remaining=qty*times
        for slot,it in sorted(ses.inventario.items()):
            if it!=item or not 20<=slot<=app._tope_bolsa(ses.inventario):continue
            amount=min(remaining,app._cantidades(ses).get(slot,1)-consume.get(slot,0))
            if amount:consume[slot]=consume.get(slot,0)+amount;remaining-=amount
            if not remaining:break
        if remaining:_aviso(ses,'You do not have enough materials for this exchange.');return True
    try:cambiar(ses,consume,[(i,n*times) for i,n in recipe['premios']])
    except Rechazo as exc:_aviso(ses,str(exc))
    return True
