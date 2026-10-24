"""Native per-character, per-chat-tab filters (no message suppression hacks)."""
import struct


def validar(canal,mascara):
    return (isinstance(canal,int) and isinstance(mascara,int) and 0<=canal<=3
            and bool(mascara&0x8000) and not mascara&~0x80ff)


def paquetes(p):
    return [struct.pack('<HIBBII',0x001d,p.entity_id,1,7,int(canal),int(mascara))
            for canal,mascara in (getattr(p,'chat_filtros',None) or {}).items()
            if validar(int(canal),int(mascara))]


def guardar(ses,parametro):
    import cuentas
    canal=parametro>>16
    mascara=parametro&0xffff
    p=getattr(ses,'personaje',None)
    if not p or not getattr(ses,'usuario',None) or not validar(canal,mascara):return False
    filtros=dict(getattr(p,'chat_filtros',None) or {})
    filtros[canal]=mascara
    if not cuentas.guardar_chat_filtros(ses.usuario,p.char_id,filtros):return False
    p.chat_filtros=filtros
    ses.enviar(struct.pack('<HIBBII',0x001d,p.entity_id,1,7,canal,mascara))
    return True
