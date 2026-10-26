"""Love Broadcasting: native window953 -> C2S004D [u8 slot][name17].

Angel.exe6659e0 /622930 and wnd01.xml956 establish the request layout.
The item XML supplies the original love message, not player-supplied chat.
"""
import time

ITEMS=frozenset((4458,4459,4460,4840,4892,6385,6386,6387,6388,6389))


def procesar(ses,body):
    import app,clases,recent_mall
    from house_services import xml_rows
    if len(body)!=18:return
    slot=body[0];item=ses.inventario.get(slot)
    if item not in ITEMS:return
    def notice(text):ses.enviar(clases.aviso(text,tipo=0))
    try:name=body[1:].split(b'\0',1)[0].decode('ascii','strict')
    except UnicodeDecodeError:return
    if not name or any(ord(c)<32 for c in name):return
    if time.time()<getattr(ses,'_love_next',0):return
    template=xml_rows('item.xml').get(item,{})
    message=xml_rows('string.xml').get(int(template.get('\u52d5\u614b\u8cc7\u65991') or 0),{}).get('\u6587\u5b57')
    if not message or message.count('%s')!=1:
        notice('The original broadcasting text is unavailable. Your item was not consumed.');return
    target=[]
    def validate(con,data):
        rows=con.execute('SELECT nombre FROM personajes WHERE nombre=? COLLATE NOCASE',(name,)).fetchall()
        if len(rows)!=1:raise recent_mall.Rechazo('That character does not exist. Your item was not consumed.')
        target.append(rows[0][0])
    try:recent_mall.cambiar(ses,{slot:1},[],transaccion=validate)
    except recent_mall.Rechazo as exc:notice(str(exc));return
    ses._love_next=time.time()+1
    text=(message%target[0]).replace('\\n',' ')
    packet=clases.chat_broadcast(0,ses.personaje.nombre,text)
    recipients={id(s):s for s in app._tw_sesiones() if getattr(s,'personaje',None)
                and not getattr(s,'desconectado',False)}
    recipients[id(ses)]=ses
    for recipient in recipients.values():recipient.enviar(packet)

