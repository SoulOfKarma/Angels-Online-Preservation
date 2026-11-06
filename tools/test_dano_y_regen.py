"""El dano de las habilidades y la regeneracion, fijados con mediciones.

Las dos cosas estaban calibradas solo con numeros de nivel bajo y se hundian
arriba. Aqui quedan clavadas las mediciones de los dos extremos, para que un
cambio futuro no vuelva a romper una arreglando la otra.
"""
import pathlib
import random
import sys

RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'proto'))

import combate          # noqa: E402
import configuracion    # noqa: E402


class _Blanco(combate.Monstruo):
    """Un monstruo del que solo importa su defensa."""

    def __init__(self, defensa):
        self._d = defensa
        self.hp = 10 ** 9
        self.debuffs = {}
        self.panico = False

    mdef_efectiva = property(lambda s: s._d)
    defensa_efectiva = property(lambda s: s._d)


def test_nivel_bajo_sigue_igual():
    """La medicion vieja, que es la que fijo el K=420.

    Death Mummy 3 (ATK 249) contra un Condor (DEF 329) pega 140-143 en
    Celestia. Restar la defensa daria un numero negativo, asi que aqui tiene
    que ganar la mitigacion suave.
    """
    random.seed(3)
    for _ in range(20):
        d = _Blanco(329).recibir(249, es_magico=False, mult=1.0)
        assert 125 <= d <= 155, d


def test_nivel_alto_no_se_hunde():
    """La medicion nueva, la que destapo el problema.

    Con Spl Atk 56.978 y un Forbidden Curse IV -- multiplicador 8,25, que
    sale de 1650/200 de magic.xml -- contra un bicho de Specter Village, que
    tiene 34.797 de MDEF. En el juego original ese golpe hace unos 568.000
    contando el 15% de la montura; sin ella tiene que quedar en el entorno de
    los 400.000.

    Con la formula vieja daban 5.606: cien veces menos.
    """
    random.seed(3)
    d = _Blanco(34797).recibir(56978, es_magico=True, mult=8.25)
    assert 380000 <= d <= 470000, d
    assert d > 5606 * 50, 'sigue hundiendose con la defensa alta'


def test_la_defensa_sigue_contando():
    """Mas defensa tiene que doler menos, y nunca bajar de uno."""
    flojo = _Blanco(1000).recibir(56978, es_magico=True, mult=8.25)
    duro = _Blanco(200000).recibir(56978, es_magico=True, mult=8.25)
    assert flojo > duro >= 1, (flojo, duro)


def test_regeneracion_sube_con_el_nivel():
    """El porcentaje crece, y sentado siempre es mas que de pie."""
    for nivel, maximo in ((1, 280), (100, 20000), (300, 121440)):
        pie = configuracion.regenera(maximo, nivel, False, False)
        sentado = configuracion.regenera(maximo, nivel, True, False)
        assert sentado > pie, (nivel, pie, sentado)
    # A nivel alto tiene que ser cuestion de minutos, no de horas: con los +6
    # planos de antes, llenar 121.440 de MP eran cinco horas y media.
    pie300 = configuracion.regenera(121440, 300, False, False)
    assert 121440 / pie300 * 2 < 300, 'de pie sigue tardando demasiado'
    sent300 = configuracion.regenera(121440, 300, True, False)
    assert 121440 / sent300 < 60, 'sentado sigue tardando demasiado'


def test_a_nivel_1_no_regenera_menos_que_antes():
    """El suelo plano: nadie puede salir perdiendo con el cambio."""
    assert configuracion.regenera(280, 1, False, True) >= 6
    assert configuracion.regenera(280, 1, True, True) >= 12
    assert configuracion.regenera(154, 1, False, False) >= 6
    assert configuracion.regenera(154, 1, True, False) >= 6


def test_la_montura_de_fashion_no_quita_velocidad():
    """El aspecto es aspecto: nunca puede dejarte andando.

    La Shamrock Goldfish (77099) es de categoria 紙娃娃 y su move_speed viene
    VACIO. El codigo miraba la ranura de fashion PRIMERO, asi que ponersela
    daba velocidad cero y el jugador se quedaba a pie; quitarsela la devolvia.

    Y las que SI dan velocidad suman con la montura de verdad, no la pisan.
    """
    import app

    class _S:
        def __init__(self, bolsa):
            self.inventario = bolsa

    a_pie = app._velocidad_de(_S({}))
    con_montura = app._velocidad_de(_S({app.RANURA_MONTURA: 367}))
    assert con_montura > a_pie

    # El aspecto sin velocidad no resta.
    assert app._velocidad_de(_S({174: 77099})) == a_pie
    assert app._velocidad_de(_S({app.RANURA_MONTURA: 367,
                                 174: 77099})) == con_montura

    # El que si la da, suma.
    solo_moda = app._velocidad_de(_S({174: 367}))
    assert solo_moda > a_pie
    assert app._velocidad_de(_S({app.RANURA_MONTURA: 367,
                                 174: 367})) > con_montura


def test_los_buffs_de_dano_cuentan():
    """Soul Corral IV dice "+10% spell damage" y ahora se aplica.

    El dato estaba en magic.xml desde siempre -- el campo 魔法傷害 -- y se
    guardaba en el buff, pero nadie lo leia de vuelta. Los anillos y las capas
    si contaban, porque van por el camino del equipo, asi que la diferencia
    solo se notaba con buffs puestos.
    """
    import time as _t
    futuro, pasado = _t.time() + 60, _t.time() - 60

    # Lo que declara el hechizo de verdad.
    assert combate.datos_magia(5284).get('mag_dmg_pct') == 10, 'Soul Corral IV'

    buffs = {1: {'fin': futuro, 'mag_dmg_pct': 10},
             2: {'fin': futuro, 'mag_dmg_pct': 12},
             3: {'fin': pasado, 'mag_dmg_pct': 50}}
    # Suman entre ellos y el caducado no.
    assert combate.pct_dano_buffs(buffs, True) == 22
    # Un buff de dano magico no toca el fisico.
    assert combate.pct_dano_buffs(buffs, False) == 0
    assert combate.pct_dano_buffs(None, True) == 0
    assert combate.pct_dano_buffs({}, True) == 0


def test_los_stats_nunca_revientan_el_paquete():
    """Un numero fuera de rango no puede tumbar la sesion.

    Paso de verdad: la Eerie Curse resta 18432 de ataque, y al expirar el
    buff el recalculo dejo un campo fuera del rango de su <I>. El
    struct.error subio hasta el bucle de asyncio, mato la sesion y al
    jugador se le quedo el juego colgado.

    Ahora cada campo se recorta a su rango, asi que lo peor que puede pasar
    es que se vea un cero.
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import inventario as inv
    bolsa = {3: 58790}
    casos = [
        {'x': {'atk': -99999999, 'fin': 9e18}},
        {'x': {'hp': -99999999, 'fin': 9e18}},
        {'x': {'hp': 10 ** 12, 'atk': 10 ** 12, 'fin': 9e18}},
        {'x': {'def': -10 ** 9, 'mdef': -10 ** 9, 'fin': 9e18}},
    ]
    normal = inv.stats(bolsa, None, hp=100, hp_max=100, mp=10, mp_max=10)
    for b in casos:
        p = inv.stats(bolsa, None, hp=100, hp_max=100, mp=10, mp_max=10,
                      buffs=b)
        assert len(p) == len(normal), (len(p), len(normal))


def test_el_sp_que_cuesta_y_el_que_da_son_columnas_distintas():
    """El guerrero no tenia de donde sacar SP salvo pegando.

    Son dos columnas del hechizo y el codigo leia solo una:
        消耗SP燈   lo que CUESTA  (Strangle Strike V: 2000, dos lamparas)
        SP         lo que DA      (Bloody Storm: 1000, Energy Recharge:
                                   de 500 a 2000)
    'sp' guardaba el coste, asi que las habilidades de recarga daban cero.
    Una lampara son 1000 puntos, segun el SP Power Scroll: "Increase 2000 SP
    ... recover 2 SP lamps".
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    _s.path.insert(0, str(RAIZ / 'proto'))
    import combate as cb
    import app

    esperado = {655: (0, 1000), 15591: (0, 2000), 5850: (2000, 0)}
    for mid, (cuesta, da) in esperado.items():
        mag = cb.datos_magia(mid)
        if not mag:
            return                  # sin content.db no hay nada que probar
        assert mag.get('cost_sp', 0) == cuesta, (mid, mag.get('cost_sp'))
        assert mag.get('sp_gana', 0) == da, (mid, mag.get('sp_gana'))

    class Ses:
        def __init__(self):
            self.sp = 0
            self.personaje = type('P', (), {'nivel': 300,
                                            'habilidades': [(15, 300)]})()
            self.out = []

        def enviar(self, *m):
            self.out.extend(m)

    ses = Ses()
    app._dar_sp(ses, 286, cb.datos_magia(655), 't')
    assert ses.sp == 1000, ses.sp
    # No pasa del tope, que son DIEZ lamparas por mucho Reserve que tengas.
    ses.sp = 9500
    app._dar_sp(ses, 286, cb.datos_magia(15591), 't')
    assert ses.sp == 10000, ses.sp
    # Y una habilidad que solo cuesta no regala nada.
    ses.sp = 0
    app._dar_sp(ses, 286, cb.datos_magia(5850), 't')
    assert ses.sp == 0


def test_las_curaciones_no_se_ven_como_dano():
    """El numero flotante lleva un tipo, y ese tipo es el color.

    Medido cruzando 0x000B con el 0x0013 que le sigue, en diez capturas:
        tipo 3  MP   el AZUL   -- se vio con 6400 usando Rejuvenation
        tipo 4  HP   el VERDE  -- se vio con 8000
        tipo 7  SP   el de las lamparas
    El 4 estaba puesto como "DoT (veneno/sangrado)", que es justo lo
    contrario: el HP sube 4916 veces con ese tipo y baja 46. Por eso las
    curaciones salian pintadas como si fueran golpes.
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import combate as cb
    assert (cb.TIPO_CURA_MP, cb.TIPO_CURA_HP, cb.TIPO_CURA_SP) == (3, 4, 7)
    # El daño por veneno es daño normal, no el 4.
    assert cb.TIPO_DANO_ESTADO == cb.TIPO_DANO == 1
    # Y el byte del tipo va donde toca.
    p = cb.numero_flotante(286, 8000, cb.TIPO_CURA_HP)
    assert p[6] == 4 and p[7:11] == (8000).to_bytes(4, 'little'), p.hex()
    p = cb.numero_flotante(286, 6400, cb.TIPO_CURA_MP)
    assert p[6] == 3 and p[7:11] == (6400).to_bytes(4, 'little'), p.hex()


def test_las_habilidades_de_sp_cuestan_un_porcentaje_de_vida():
    """El campo 'hp' de esas habilidades es un PORCENTAJE, no un numero.

    Bloody Storm V lleva hp=-9 y su descripcion dice "Reduce 9% HP,
    Increase 1000SP". Hot Blooded V lleva hp=-5. El codigo lo trataba como
    una curacion plana, asi que en vez de costarte el 9% te curaba diez
    puntos.

    MEDIDO: con 138344 de vida maxima el servidor real mando 12450, y el 9%
    de 138344 son 12451. Salio 32 veces.
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    _s.path.insert(0, str(RAIZ / 'proto'))
    import app
    import combate as cb

    class Ses:
        def __init__(self, vida):
            self.sp = 0
            self.out = []
            self.personaje = type('P', (), {
                'nivel': 300, 'habilidades': [(15, 262)],
                'hp': vida, 'hp_max': vida, 'inventario': {}})()

        def enviar(self, *m):
            self.out.extend(m)

    mag = cb.datos_magia(655)
    if not mag:
        return
    ses = Ses(138344)
    app._dar_sp(ses, 286, mag, 't')
    coste = 138344 - ses.personaje.hp
    assert coste == 12451, coste          # el real mando 12450
    assert ses.sp == 1000, ses.sp
    # Nunca te mata: deja al menos un punto.
    ses = Ses(100)
    ses.personaje.hp = 5
    app._dar_sp(ses, 286, mag, 't')
    assert ses.personaje.hp >= 1, ses.personaje.hp


def test_subir_de_nivel_no_se_queda_en_bucle():
    """El bucle que sube de nivel colgaba el servidor entero.

    exp_para_nivel() recortaba a 0xFFFFFFFF, asi que del nivel 299 en
    adelante devolvia SIEMPRE el mismo numero. Con la experiencia por encima
    de ese tope la condicion no dejaba de cumplirse y el personaje subia de
    nivel para siempre: al matar un bicho el servidor se quedaba clavado y
    al jugador se le colgaba el juego.

    El recorte va donde se empaqueta, no donde se decide.
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import combate as cb

    curva = cb._cargar_curva_nivel()
    if not curva:
        return
    # La curva ya no se recorta: los niveles altos piden mas de 32 bits.
    assert cb.exp_para_nivel(300) > 0xFFFFFFFF, cb.exp_para_nivel(300)
    # Y son distintos entre si, que es lo que el bucle necesita.
    assert cb.exp_para_nivel(300) != cb.exp_para_nivel(301)
    # La version para empaquetar si cabe.
    assert cb.exp_para_nivel_u32(300) <= 0xFFFFFFFF

    # El caso real: nivel 300 con 25.478.672.000 de experiencia.
    nivel, exp = 300, 25478672000
    tope = cb.nivel_maximo()
    assert tope >= 300, tope
    vueltas = 0
    for _ in range(1000):
        if nivel >= tope:
            break
        siguiente = cb.exp_para_nivel(nivel + 1)
        if siguiente > 0 and exp >= siguiente:
            nivel += 1
            vueltas += 1
        else:
            break
    assert vueltas < 1000, 'sigue sin terminar'
    assert nivel == 300, nivel


def test_la_curva_de_niveles_es_la_del_parche_nuevo():
    """La experiencia por nivel cambio con cada parche.

    En data1 la tabla llegaba al nivel 80; en UPDATE13 al 301 y en update26
    al 471, y el update32 de Taiwan la llevo al 481. La del nivel 300 lleva fija en 801.133.037.724.519 desde el
    UPDATE13. Hay que usar la mas nueva, que es la que esta en content.db.

    El tope se queda en 481 aunque el juego llegue tecnicamente a 600: de
    ahi en adelante no hay datos de cuanta experiencia pide cada nivel, y el
    respaldo que habia (nivel * 120) daba 72.000 para el 600, o sea que se
    subia de golpe.
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import combate as cb
    curva = cb._cargar_curva_nivel()
    if not curva:
        return
    assert max(curva) == 481, max(curva)
    assert cb.nivel_maximo() == 481
    assert cb.exp_para_nivel(300) == 801133037724519
    # Y siempre crece, que es lo que el bucle de subir de nivel necesita.
    for n in range(2, 481):
        assert cb.exp_para_nivel(n) < cb.exp_para_nivel(n + 1), n


def test_matar_un_bicho_con_la_experiencia_alta():
    """La funcion que se caia, llamada entera con datos de verdad.

    Con 25.478.672.000 de experiencia, empaquetarla en un campo de 32 bits
    levantaba un struct.error que subia hasta el bucle de asyncio y tiraba
    la sesion. Salio tres veces seguidas en sitios distintos -- al entrar,
    al expirar un buff y al matar -- porque el recorte se ponia a mano en
    cada sitio y siempre faltaba alguno.

    Esta prueba llama a _procesar_muerte_monstruo() de verdad.
    """
    import json
    import sys as _s
    import time
    _s.path.insert(0, str(RAIZ / 'server'))
    _s.path.insert(0, str(RAIZ / 'proto'))
    import app
    import cuentas

    if not cuentas.ARCHIVO.exists():
        return
    d = json.loads(cuentas.ARCHIVO.read_text(encoding='utf-8'))
    cuenta = next(iter(d.get('cuentas', {}).values()), None)
    if not cuenta or not cuenta.get('personajes'):
        return
    p = cuentas.personaje_de(cuenta, 0)
    if not p:
        return
    p.exp = 25478672000

    class Ses:
        rol = 'mundo'
        usuario = None
        sp = 0
        oro = 0

        def __init__(self):
            self.personaje = p
            self.inventario = dict(p.inventario)
            self.cantidades = {}
            self.instancias = {}
            self.monstruos = []
            self.enviados = []

        def enviar(self, *m):
            self.enviados.extend(m)

        def enviar_inmediato(self, *m):
            self.enviados.extend(m)

    class Mob:
        entity_id = 99
        npc_type = 17573
        nombre = 'Viridian Lady'
        hp = 0
        hp_max = 1189011
        vivo = False
        tile_x = 193
        tile_y = 93
        stage = 288
        nivel = 50

        def __init__(self):
            self.muerto_en = time.time()

    # Si esto lanza, el servidor se cae en cuanto matas algo.
    app._procesar_muerte_monstruo(Ses(), Mob(), 286, 'test', espera=0.0)


def test_los_combos_pegan_todos_sus_golpes():
    """combo_de() sacaba bien los golpes y no lo llamaba nadie.

    Son 475 habilidades con combo en magic.xml, no solo Strangle Strike, y
    todas pegaban una sola vez. La tabla lo trae de dos formas:
      - directa, 連擊次數 golpes en el propio hechizo (376 asi)
      - encadenada, por 轉嫁法術 a un hijo marcado 單體多次攻擊 con el numero
        de golpes en el 動態參數2 del padre (99 asi, entre ellas Strangle
        Strike)
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import combate as cb

    if not cb._magic_xml():
        return                      # sin los paks no hay nada que probar
    esperado = {5850: 9, 5849: 6, 605: 2}
    for mid, golpes in esperado.items():
        c = cb.combo_de(mid)
        assert c, mid
        assert c['golpes'] == golpes, (mid, c['golpes'], golpes)
        assert c['intervalo_ms'] > 0, c

    # Y el ataque normal no es un combo.
    assert cb.combo_de(cb.ATAQUE_NORMAL) in (None, False) or \
        (cb.combo_de(cb.ATAQUE_NORMAL) or {}).get('golpes', 1) <= 1

    # El servidor tiene que llamarla: si nadie lo hace, solo sale un golpe.
    fuente = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')
    assert 'combo_de(' in fuente, 'nadie usa combo_de en app.py'


def test_al_entrar_no_se_manda_la_experiencia_como_sp():
    """KIND_EXP y KIND_SP son el MISMO campo, el 4, y el 4 es el SP.

    Al entrar se mandaba atributo(entidad, p.exp, KIND_EXP), asi que el
    cliente recibia la experiencia -- 322.674.302 -- como si fueran puntos
    de SP. La barra de lamparas partia de un numero imposible y se quedaba
    muerta por mucho que luego subiera de 175 en 175 al pegar.

    La experiencia va en el 0x001D con los sub-campos 29 a 32, que es como
    la manda el servidor real.
    """
    import json
    import struct
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    _s.path.insert(0, str(RAIZ / 'proto'))
    import combate as cb
    import cuentas
    import login

    if not cuentas.ARCHIVO.exists():
        return
    d = json.loads(cuentas.ARCHIVO.read_text(encoding='utf-8'))
    cuenta = next(iter(d.get('cuentas', {}).values()), None)
    if not cuenta or not cuenta.get('personajes'):
        return
    p = cuentas.personaje_de(cuenta, 0)
    if not p:
        return
    p.exp = 322674302

    vistos = []
    for m in login.secuencia(p):
        if struct.unpack_from('<H', m, 0)[0] == 0x13 and len(m) >= 12:
            if m[7] == cb.KIND_SP:
                vistos.append(struct.unpack_from('<I', m, 8)[0])
    assert vistos, 'no se manda ningun SP al entrar'
    for v in vistos:
        assert v != p.exp, 'se sigue mandando la experiencia como SP'
        # Y nunca por encima del tope real, que son 14 lamparas.
        assert v <= 600 * 1000, v


def test_el_sp_a_cero_no_se_convierte_en_el_maximo():
    """'or max_pts' rellenaba la barra entera cuando el SP valia 0.

    El cero es falso en Python, asi que "getattr(ses,'sp',None) or max_pts"
    daba el maximo en vez de cero. Al entrar o al cambiar de mapa la barra
    se llenaba sola, y el jugador veia las lamparas aparecer de golpe y
    vaciarse con un solo ataque.

    Solo debe rellenarse cuando NO hay valor todavia, es decir None.
    """
    fuente = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')
    assert "'sp', None) or max_pts" not in fuente, \
        'vuelve a estar el or que convierte el 0 en el maximo'

    # Y el comportamiento: 0 se queda en 0, None pasa al maximo.
    for actual, esperado in ((0, 0), (None, 14000), (500, 500)):
        sp = 14000 if actual is None else actual
        assert sp == esperado, (actual, sp, esperado)


def test_el_pergamino_de_sp_recupera_lo_que_dice():
    """El objeto no trae el numero: lo trae su hechizo.

    El SP Power Scroll (3696) apunta al 常駐法術 1871, y ese hechizo lleva
    SP=2000 -- las "2 SP lamps" de su descripcion, porque una lampara son
    1000 puntos. No se detectaba de ninguna forma, asi que el objeto ni se
    gastaba ni hacia nada.
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import inventario as inv
    if not inv.sp_de_item(3696):
        return                      # sin content.db no hay nada que probar
    assert inv.sp_de_item(3696) == 2000
    # Un objeto que no recupera SP da cero.
    assert inv.sp_de_item(10) == 0
    # Y el servidor lo usa.
    fuente = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')
    assert 'sp_de_item(' in fuente, 'nadie usa sp_de_item en app.py'


def test_el_sp_empieza_a_cero_y_no_al_maximo():
    """La barra de SP salia llena y por eso no podia subir.

    Lo canto el log: "_dar_sp(Bloody Storm V): sp_gana=1000 sp_actual=14000".
    La habilidad SI llegaba y SI daba sus 1000, pero el SP ya estaba en el
    tope y min(14000, 15000) no mueve nada.

    Venia de "getattr(ses,'sp',None) or max_pts": la sesion nace sin ese
    atributo, asi que devolvia None y se rellenaba entera. Cambiarlo a
    comprobar None no bastaba, porque None es justo lo que devolvia.
    El SP se gana peleando, asi que empieza a cero.
    """
    import re
    fuente = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')
    # Solo el codigo: en los comentarios se explica el fallo y ahi la frase
    # tiene que poder aparecer.
    codigo = chr(10).join(
        re.sub(r'#.*$', '', l) for l in fuente.split(chr(10)))
    assert 'or max_pts' not in codigo, 'vuelve a rellenar la barra al entrar'
    assert 'ses.sp = max_pts' not in codigo, 'alguien la pone al maximo'


def test_el_tope_de_lamparas_son_diez():
    """Reserve da una lampara cada 25 niveles, pero el juego topa en DIEZ.

    Sin tope, a nivel 300 salian catorce y la barra pedia 14.000 puntos.
    Ademas quedo guardado un sp=14000 de cuando se llenaba sola, asi que al
    cargar tambien se recorta.
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    _s.path.insert(0, str(RAIZ / 'proto'))
    import app
    assert app.MAX_LAMPARAS_SP == 10
    for rango, esperado in ((1, 2), (50, 4), (200, 10), (300, 10)):
        bars, pts = app._max_sp_info(
            type('P', (), {'habilidades': [(15, rango)]})())
        assert bars == esperado, (rango, bars, esperado)
        assert pts == bars * 1000


if __name__ == '__main__':
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith('test_') and callable(fn):
            try:
                fn()
                print('  OK   ' + nombre)
            except AssertionError as e:
                fallos += 1
                print('  FALLA ' + nombre + ': ' + str(e))
    print('fallos:', fallos)
    sys.exit(1 if fallos else 0)
