"""Native city scrolls, recorded marks and party books; atomic item/travel state."""
import functools
import time


class Rechazo(ValueError):pass


@functools.lru_cache(maxsize=None)
def item(ident):
    from house_services import xml_rows
    return next((r for n in range(1,10) if (r:=xml_rows('item%s.xml'%(n if n>1 else '')).get(ident))),{})


def _notice(s,text):
    import clases
    s.enviar(clases.aviso(text,tipo=0))


def _event(stage):
    import competiciones,daily_events,olympus,territorios_liga
    return stage in competiciones.MAPAS or stage in daily_events.STAGES or stage in olympus.STAGES or stage in territorios_liga.AREAS or stage in (500,501) or 200<=stage<=207


def _point(stage,x,y):
    import app,transitable
    stage,x,y=int(stage),int(x),int(y)
    if _event(stage) or app.es_instancia(stage) or not transitable.conocido(stage):
        raise Rechazo('Teleport items cannot enter private rooms or event maps.')
    if not transitable.se_pisa(stage,x,y):raise Rechazo('The recorded destination is unavailable.')
    return dict(stage=stage,x=x,y=y)


def _ready(s):
    if not getattr(s,'personaje',None) or getattr(s,'muerto',False) or getattr(s,'mapa_cargando',False):raise Rechazo('Wait until your character is ready.')
    if _event(s.personaje.stage):raise Rechazo('Teleport items cannot be used in this event or private room.')


def _move(s,point):
    import app
    p=s.personaje;stage,x,y=point['stage'],point['x'],point['y']
    if stage==p.stage:app._viajar_dentro_del_mapa(s,'travel item',dict(llegada=(x,y)))
    else:app._sincronizar_cambio_mapa(s,stage,x,y)


def _persist_position(con,s,point,data=None):
    import json
    if data is None:
        row=con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',(s.usuario,s.personaje.char_id)).fetchone()
        if not row:raise Rechazo('The destination character is unavailable.')
        data=json.loads(row[0]);data.update(stage_id=point['stage'],tile_x=point['x'],tile_y=point['y'])
        con.execute('UPDATE personajes SET datos=? WHERE usuario=? AND char_id=?',(json.dumps(data),s.usuario,s.personaje.char_id))
    else:data.update(stage_id=point['stage'],tile_x=point['x'],tile_y=point['y'])


def usar(s,slot,target=None):
    import app,recent_mall,eventos
    from house_services import xml_rows
    ident=s.inventario.get(slot);row=item(ident);formula=int(row.get('\u4f7f\u7528\u516c\u5f0f') or 0)
    magic=xml_rows('magic.xml').get(int(row.get('\u5e38\u99d0\u6cd5\u8853') or 0),{})
    city=int(magic.get('\u516c\u5f0f') or 0)==16
    maple=row.get('\u7269\u54c1\u985e\u5225')=='\u9b6f\u6613\u6d6e\u6a19'
    if not city and not maple and formula not in (2,7,8,9) and ident!=20566:return False
    try:
        _ready(s)
        if not 20<=slot<=app._tope_bolsa(s.inventario):raise Rechazo('Use this item from your backpack.')
        if ident==20566:raise Rechazo('Use a recorded Maple Mark to consume this scroll.')
        consume={} if row.get('\u4f7f\u7528\u4e0d\u6263')=='\u662f' else {slot:1}
        destination=None;traveler=s;record=None
        if city:
            stage=int(magic['\u52d5\u614b\u53c3\u65781']);tag=int(magic.get('\u52d5\u614b\u53c3\u65782') or 61)
            tiles=eventos.casillas_de_tag(stage,tag)
            if not tiles:raise Rechazo('The original revival destination is unavailable.')
            destination=_point(stage,*tiles[0])
        elif formula in (2,7):
            import equipos,presencia
            peers=[p for p in equipos.grupo_de(s) if p is not s and getattr(p,'personaje',None) and not getattr(p,'cerrada',False)]
            peer=next((p for p in peers if target and int(target) in (p.personaje.char_id,p.personaje.entity_id,presencia.entidad_de(p))),None)
            if peer is None and not target and len(peers)==1:peer=peers[0]
            if peer is None:
                if peers and not target:s._travel_item=(slot,ident,time.time()+30);raise Rechazo('Click the portrait of the teammate you want to select.')
                raise Rechazo('Select a current teammate to use this book.')
            _ready(peer);traveler=s if formula==2 else peer;anchor=peer if formula==2 else s
            destination=_point(anchor.personaje.stage,anchor.personaje.tile_x,anchor.personaje.tile_y)
        elif formula==8:record=_point(s.personaje.stage,s.personaje.tile_x,s.personaje.tile_y)
        elif maple:
            recorded=(getattr(s.personaje,'mejoras',{}) or {}).get(slot,{}).get('maple_mark')
            if recorded:
                destination=_point(recorded['stage'],recorded['x'],recorded['y'])
                scroll=next((k for k,i in s.inventario.items() if i==20566 and 20<=k<=app._tope_bolsa(s.inventario)),None)
                if scroll is None:raise Rechazo('You need a Maple Teleportation Scroll; the mark was not changed.')
                consume={scroll:1}
            else:record=_point(s.personaje.stage,s.personaje.tile_x,s.personaje.tile_y);consume={}
        else:
            mark=getattr(s.personaje,'travel_mark',{})
            if not mark:raise Rechazo('Record a destination with a Mark Stone first.')
            destination=_point(mark['stage'],mark['x'],mark['y'])
        def transaction(con,data):
            if record:
                if maple:data['mejoras'].setdefault(str(slot),{})['maple_mark']=record
                else:data['travel_mark']=record
            if destination:_persist_position(con,traveler,destination,data if traveler is s else None)
        recent_mall.cambiar(s,consume,[],transaccion=transaction)
        if record:
            if not maple:s.personaje.travel_mark=record
            _notice(s,'Location recorded: map %d (%d, %d).'%(record['stage'],record['x'],record['y']))
        if destination:_move(traveler,destination)
        s._travel_item=None
    except (Rechazo,recent_mall.Rechazo) as exc:_notice(s,str(exc))
    return True


def pulsar(s,target):
    pending=getattr(s,'_travel_item',None)
    if not pending:return False
    slot,ident,deadline=pending
    if deadline<time.time() or s.inventario.get(slot)!=ident:s._travel_item=None;return False
    import equipos,presencia
    if not any(p is not s and target in (p.personaje.char_id,p.personaje.entity_id,presencia.entidad_de(p)) for p in equipos.grupo_de(s) if getattr(p,'personaje',None)):return False
    return usar(s,slot,target)
