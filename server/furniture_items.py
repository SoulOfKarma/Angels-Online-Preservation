"""Furniture is tradable backpack stock until explicitly registered for decor."""
import json


def protegido(ses,slot):
    import casas
    item=getattr(ses,'inventario',{}).get(slot)
    if not item or casas.item_a_mueble(item) is None:return False
    state=(getattr(ses.personaje,'mejoras',{}) or {}).get(slot,{})
    return casas.SLOT_FURN_INI<=slot<=casas.SLOT_FURN_FIN or bool(state.get('vinculacion'))


def usar(ses,slot):
    import app,casas,clases,cuentas,inventario
    item=ses.inventario.get(slot)
    if casas.item_a_mueble(item or 0) is None:return False
    def notice(text):ses.enviar(clases.aviso(text,tipo=0))
    if casas.SLOT_FURN_INI<=slot<=casas.SLOT_FURN_FIN:
        notice('This decoration is registered. Place it from your Furniture bag.');return True
    if getattr(ses,'muerto',False) or getattr(ses,'mapa_cargando',False):return True
    if not 20<=slot<=app._tope_bolsa(ses.inventario):return True
    dest=next((s for s in range(casas.SLOT_FURN_INI,casas.SLOT_FURN_FIN+1) if s not in ses.inventario),None)
    if dest is None:notice('Your Furniture bag is full. The item remains in your backpack.');return True
    bag=dict(ses.inventario);counts=dict(app._cantidades(ses));p=ses.personaje
    bag[dest]=item
    qty=counts.get(slot,1)
    if qty>1:counts[slot]=qty-1
    else:bag.pop(slot);counts.pop(slot,None)
    counts.pop(dest,None)
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',(ses.usuario,p.char_id)).fetchone()
        if not row or not cuentas.inventario_equivalente(json.loads(row[0]),ses.inventario,app._cantidades(ses)):
            notice('Inventory changed. Reconnect before registering furniture.');return True
        data=json.loads(row[0]);upgrades={int(k):dict(v) for k,v in data.get('mejoras',{}).items()}
        state=dict(upgrades.get(slot,{}));inventario.vincular_equipo(item,p.char_id,state)
        upgrades[dest]=state
        if slot not in bag:upgrades.pop(slot,None)
        data.update(inventario={str(k):v for k,v in bag.items()},cantidades={str(k):v for k,v in counts.items()},
                    mejoras={str(k):v for k,v in upgrades.items()})
        con.execute('UPDATE personajes SET datos=? WHERE usuario=? AND char_id=?',(json.dumps(data),ses.usuario,p.char_id))
    inst=app._instancias(ses).get(slot) or inventario.instancia_nueva()
    if slot not in bag:app._instancias(ses).pop(slot,None)
    app._instancias(ses)[dest]=inst if qty==1 else inventario.instancia_nueva()
    ses.inventario.clear();ses.inventario.update(bag)
    app._cantidades(ses).clear();app._cantidades(ses).update(counts)
    p.inventario,p.cantidades,p.mejoras=ses.inventario,app._cantidades(ses),upgrades
    cuentas._notificar_cambio(inmediato=True)
    ses.enviar(*app._refrescar(ses,[slot,dest]))
    notice('Decoration registered in your Furniture bag. It can now be placed and cannot be sold.')
    return True
