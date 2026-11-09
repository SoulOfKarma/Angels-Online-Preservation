"""Ejecuta _arrancar_temporizador ORIGINAL con reloj y efectos instrumentados."""
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import ExitStack
import random

def validar(datos,h):
    import app,asyncio,eventos,eventos_mundo as em,dialogos
    from session import Session
    for i,ops in enumerate(datos['barreras']):
        ses=SimpleNamespace(rol='mundo',mapa_cargando=False,_mapa_ui_diferida=[],mapa_cambiado_en=0)
        enviados=[];traza=[]
        ses.enviar_sin_espejo=lambda *ps:enviados.extend(p.hex() for p in ps)
        for op in ops:
            if op[0]=='send':enviados.extend(p.hex() for p in Session._filtrar_carga_mapa(ses,tuple(bytes(p) for p in op[1])))
            elif op[0]=='load':ses.mapa_cargando=False
            else:Session.terminar_carga_mapa(ses)
            traza.append([list(enviados),ses.mapa_cargando,[p.hex() for p in ses._mapa_ui_diferida]])
        print('BARRERA',i,h(traza))
    for i,c in enumerate(datos['timers']):
        original=em.EstadoDeMapa(c['stage']);otra=em.EstadoDeMapa(c['stage'] if i%2 else c['stage']+1)
        actual=[original];ses=SimpleNamespace(personaje=SimpleNamespace(stage=c['stage']));cola=[];tokens={};ejecuciones=[];traza=[]
        reloj=SimpleNamespace(call_later=lambda periodo,fn:cola.append((periodo,fn)))
        def arrancar(encender):
            app._arrancar_temporizador(ses,'test',original,c['tag'],encender)
            t=original.temporizadores.get(c['tag'])
            if t and len(t)>=3 and t[2] not in tokens:tokens[t[2]]=len(tokens)+1
        def ejecutar(st,ev,modo,ctx):
            ejecuciones.append([st,ev,modo,original.temporizador(c['tag'])[1]])
            return [('prueba',)] if c['efecto'] else []
        def efectos(*args):
            if c['efecto']=='off':arrancar(False)
            elif c['efecto']=='restart':arrancar(True)
            elif c['efecto']=='travel':actual[0]=otra
        def snap():
            t=original.temporizador(c['tag'])
            traza.append([t[0],t[1],tokens.get(t[2]) if len(t)>=3 else None,len(cola),len(ejecuciones),actual[0] is original])
        with ExitStack() as s:
            s.enter_context(patch.object(asyncio,'get_event_loop',lambda:reloj))
            s.enter_context(patch.object(em,'estado_de',lambda ses:actual[0]))
            s.enter_context(patch.object(em,'_CORRIDAS',{'test':{'estados':{c['stage']:original}}} if c['viva'] else {}))
            s.enter_context(patch.object(em,'ContextoSesion',lambda ses:None))
            s.enter_context(patch.object(eventos,'ejecutar',ejecutar))
            s.enter_context(patch.object(app,'_aplicar_efectos',efectos))
            for op in datos['timer_ops']:
                if op[0]=='start':arrancar(op[1])
                else:
                    actual[0]=original if op[1]==0 else otra
                    ses.personaje=SimpleNamespace(stage=actual[0].stage) if op[2] else None
                    if cola:cola.pop(0)[1]()
                snap()
        print('TIMER-VIAJE',i,h([traza,ejecuciones]))
    # CHAT de _aplicar_efectos real; se registra quien dice el texto y el RNG.
    mensajes=dialogos._cargar_msg_dict();ids=sorted(k for k,v in mensajes.items() if v)[:8]
    for i in range(120):
        random.seed(i);texts=([ids[i%8]] if i%3==0 else [ids[0],0,ids[1],999999999,ids[2]]) if i%7 else [0,999999999]
        ses=SimpleNamespace(personaje=SimpleNamespace(stage=41));salida=[]
        with patch.object(em,'estado_de',lambda ses:SimpleNamespace(stage=41)),patch.object(app,'_hablar_jugador',lambda ses,t:salida.append(t)):
            app._aplicar_efectos(ses,'test',[('chat',1,texts)])
        print('CHAT-VIAJE',i,h([salida,random.getrandbits(64)]))
