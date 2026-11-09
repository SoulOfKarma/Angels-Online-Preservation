"""Callback _respawn ORIGINAL: registro cambiado, EID reutilizado y viajes."""
import ast,json,pathlib,random
from types import SimpleNamespace
RAIZ=pathlib.Path(__file__).resolve().parent.parent
def validar(datos,h):
    import app,combate as cb
    tree=ast.parse((RAIZ/'server/app.py').read_text(encoding='utf8'))
    padre=next(f for f in tree.body if isinstance(f,ast.FunctionDef) and f.name=='_procesar_muerte_monstruo')
    fn=next(f for f in padre.body if isinstance(f,ast.FunctionDef) and f.name=='_respawn')
    codigo=compile(ast.Module(body=[fn],type_ignores=[]),'app.py:_respawn','exec')
    def vista(m):return None if m is None else [m.hp,[m.tile_x,m.tile_y],m.muerto_en,m.captura_fallida_en]
    for i,c in enumerate(datos['callbacks']):
        random.seed(i);m=cb.Monstruo(900,39,'White Wolf',[50,50],42064,stage=41);m.hp=1 if c['vivo'] else 0;m.muerto_en=1000.0;m.captura_fallida_en=999.0
        m.generado=c['generado'];m.zona_generador=c['zona']
        actual=m if c['registro']=='original' else (cb.Monstruo(900,19,'replacement',[5,5],42107,stage=c['stage']) if c['registro']=='reemplazo' else None)
        if actual is not None and actual is not m:actual.hp=0
        salida=[];ses=SimpleNamespace(personaje=SimpleNamespace(stage=c['stage']),monstruos={900:actual} if actual else {})
        ses.enviar_inmediato=lambda *ps:salida.extend([['p',p.hex()] for p in ps])
        estado=SimpleNamespace(stage=c['stage'],generadores_activos={75} if c['activa'] else set(),juego_matar=None)
        ns=app.__dict__.copy();ns.update(ses=ses,m=m,objetivo=900,addr='test',_cb=cb,_companeros=lambda s:[],_generar_zona=lambda s,a,st,z,cuantos:salida.append(['g',st,z,cuantos]))
        from unittest.mock import patch
        with patch.object(__import__('eventos_mundo'),'estado_de',lambda s:estado):
            exec(codigo,ns);ns['_respawn']()
        resultado=[vista(m),vista(actual),salida,random.getrandbits(64)]
        print('CALLBACK',i,h(resultado))
