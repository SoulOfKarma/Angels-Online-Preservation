"""Las mejoras de equipo: morteros, martillos, piensos y gemas.

Lo que se comprueba es que las reglas salgan de los DATOS del cliente y no de
una tabla escrita a mano, y que las tres que el juego deja por escrito en las
descripciones se cumplan:

  - un objeto solo sirve hasta cierto nivel de equipo
  - una gema solo entra de su nivel HACIA ARRIBA
  - fallar un mortero no rompe nada, pero fallar un martillo se lleva el
    hueco anterior y la gema que tuviera dentro
"""
import pathlib
import random
import sys

RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import mejoras as m         # noqa: E402

MORTERO_10 = 6904           # 10-star Lucky Enhanced Pestle, hasta nivel 109
MORTERO_11 = 12218          # 11-star, hasta 119, con los % escritos
MARTILLO = 6914             # 10-star Lucky Piercing Hammer, hasta 109


def test_clasifica_por_su_categoria():
    """La clase sale de 物品類別, no de una lista de ids."""
    assert m.clase_de(MORTERO_10) == 'mortero'
    assert m.clase_de(MORTERO_11) == 'mortero'
    assert m.clase_de(MARTILLO) == 'perforar'
    assert m.clase_de(10) == ''          # una espada no es objeto de mejora


def test_lee_el_tope_de_nivel_de_la_descripcion():
    """"Exclusively for enhancing gears under lvl 109" -> 109."""
    assert m.tope_nivel(MORTERO_10) == 109
    assert m.tope_nivel(MORTERO_11) == 119
    assert m.tope_nivel(MARTILLO) == 109


def test_lee_los_porcentajes_cuando_estan_escritos():
    """Los morteros de once estrellas para arriba los declaran."""
    b = m.bonos_de(MORTERO_11)
    assert b['arma'] == {'atk': 6, 'matk': 6}
    assert b['armadura'] == {'dfs': 3, 'mdef': 3}
    assert b['escudo'] == {'dfs': 3, 'mdef': 3}


def test_los_viejos_heredan_lo_de_sus_hermanos():
    """Los de diez estrellas para abajo no dicen nada: 85 de 92.

    Se les da lo que declaran los mayores, que es lo unico que los datos
    respaldan.
    """
    assert m.stats_de_mejora(MORTERO_10, 'arma', 3) == {'atk': 18, 'matk': 18}
    assert m.stats_de_mejora(MORTERO_10, 'armadura', 2) == {'dfs': 6,
                                                            'mdef': 6}


def test_no_pasa_del_tope_de_nivel():
    ok, motivo = m.puede_mejorar(MORTERO_10, 150, 'arma', 0)
    assert not ok and '109' in motivo, motivo
    assert m.puede_mejorar(MORTERO_10, 100, 'arma', 0)[0]


def test_el_tope_son_quince():
    assert m.puede_mejorar(MORTERO_10, 100, 'arma', 14)[0]
    ok, motivo = m.puede_mejorar(MORTERO_10, 100, 'arma', 15)
    assert not ok and '15' in motivo, motivo


def test_el_pienso_de_montura_no_vale_para_un_arma():
    """Y el de mascota tampoco: cada uno a lo suyo."""
    feeds = m.ids_de_clase('pienso_montura')
    if feeds:
        f = feeds[0]
        assert not m.puede_mejorar(f, 10, 'arma', 0)[0]
        assert m.puede_mejorar(f, 10, 'montura', 0)[0]


def test_la_gema_solo_entra_de_su_nivel_hacia_arriba():
    """La regla que se pidio explicitamente.

    Una gema de nivel 120 no entra en un arma de 110, aunque el arma sea peor:
    la restriccion mira el nivel de la GEMA.
    """
    gemas = [i for i in m.ids_de_clase('gema') if m.nivel_requerido(i)]
    assert gemas, 'no se encontro ninguna gema con nivel exigido'
    g = gemas[0]
    req = m.nivel_requerido(g)
    ok, motivo = m.puede_engarzar(g, req - 10, 'arma', 1)
    assert not ok and 'hacia arriba' in motivo, motivo
    assert m.puede_engarzar(g, req, 'arma', 1)[0]
    assert m.puede_engarzar(g, req + 50, 'arma', 1)[0]
    # Y sin hueco no entra ninguna.
    assert not m.puede_engarzar(g, req + 50, 'arma', 0)[0]


def test_fallar_el_mortero_baja_un_nivel():
    """No rompe la pieza, pero se pierde una mejora.

    Se leyo mal la descripcion la primera vez: "the number of times the gear
    has been enhanced decreases by 1" no son los intentos que quedan, es el
    +N. La captura lo confirma -- +6, fallo, +6 otra vez, +7, fallo -- porque
    si el fallo no restara, el segundo exito habria dado +7.
    """
    est = {}
    suerte = random.Random(1)
    suerte.random = lambda: 0.0              # siempre acierta
    for _ in range(6):
        m.aplicar(est, 20, MORTERO_10, 100, 'arma', rng=suerte)
    assert est[20]['veces'] == 6
    sin_suerte = random.Random(1)
    sin_suerte.random = lambda: 1.0          # siempre falla
    ok, motivo = m.aplicar(est, 20, MORTERO_10, 100, 'arma', rng=sin_suerte)
    assert not ok and est[20]['veces'] == 5, (motivo, est[20])
    assert est[20]['gemas'] == [], 'la pieza no se toca'
    # Y desde cero no baja a negativo.
    est2 = {}
    m.aplicar(est2, 21, MORTERO_10, 100, 'arma', rng=sin_suerte)
    assert est2[21]['veces'] == 0


def test_fallar_el_martillo_se_lleva_el_hueco_y_la_gema():
    """Lo dice su propia descripcion, y es lo que lo hace peligroso."""
    est = {20: {'veces': 0, 'gemas': [1234], 'extra': {}, 'huecos': 1}}
    sin_suerte = random.Random(1)
    sin_suerte.random = lambda: 1.0
    ok, motivo = m.perforar(est, 20, MARTILLO, 100, 'arma', rng=sin_suerte)
    assert not ok
    assert est[20]['huecos'] == 0, 'el hueco tenia que perderse'
    assert est[20]['gemas'] == [], 'la gema tenia que perderse'


def test_la_bandera_de_exito_seguro():
    est = {}
    sin_suerte = random.Random(1)
    sin_suerte.random = lambda: 1.0
    for _ in range(15):
        m.aplicar(est, 20, MORTERO_10, 100, 'arma', exito_seguro=True,
                  rng=sin_suerte)
    assert est[20]['veces'] == m.MAX_MEJORA


def test_la_bandera_tambien_vale_para_el_martillo():
    """El 100% se pidio para las perforaciones tambien, no solo morteros."""
    est = {20: {'veces': 0, 'gemas': [], 'extra': {}, 'huecos': 0}}
    sin_suerte = random.Random(1)
    sin_suerte.random = lambda: 1.0          # siempre fallaria
    # Entre hueco y hueco hay que meter una gema, asi que se alternan.
    gema = next(i for i in m.ids_de_clase('gema')
                if m.nivel_requerido(i) <= 100)
    for n in range(3):
        ok, _msg = m.perforar(est, 20, MARTILLO, 100, 'arma',
                              exito_seguro=True, rng=sin_suerte)
        assert ok, _msg
        assert m.engarzar(est, 20, gema, 100, 'arma')[0]
    assert est[20]['huecos'] == 3


def test_hay_que_engarzar_antes_de_abrir_otro_hueco():
    """Lo dijo el usuario: con un hueco vacio no se puede abrir el siguiente.

    Encaja con que fallar el martillo se lleve "el hueco anterior y la gema
    de dentro": si se pudieran acumular huecos vacios esa frase no tendria
    sentido.
    """
    est = {}
    ok, _ = m.perforar(est, 20, MARTILLO, 100, 'arma', exito_seguro=True)
    assert ok and est[20]['huecos'] == 1
    ok, motivo = m.perforar(est, 20, MARTILLO, 100, 'arma', exito_seguro=True)
    assert not ok and 'gema' in motivo, motivo
    # Con la gema puesta ya deja.
    gema = next(i for i in m.ids_de_clase('gema') if m.nivel_requerido(i) <= 100)
    assert m.engarzar(est, 20, gema, 100, 'arma')[0]
    assert m.perforar(est, 20, MARTILLO, 100, 'arma', exito_seguro=True)[0]
    assert est[20]['huecos'] == 2


def test_el_tope_de_huecos_son_cinco():
    est = {20: {'veces': 0, 'gemas': [1] * 5, 'extra': {}, 'huecos': 5}}
    ok, motivo = m.perforar(est, 20, MARTILLO, 100, 'arma',
                            exito_seguro=True)
    assert not ok and '5' in motivo, motivo


def test_el_pienso_de_mascota():
    """El 7094, que en Celestia no se vende y no se pudo medir."""
    assert m.clase_de(7094) == 'pienso_mascota'
    assert m.stats_de_mejora(7094, 'mascota', 3) == {'atk': 24, 'matk': 24, 'dfs': 15, 'mdef': 15, 'hp': 150}
    assert not m.puede_mejorar(7094, 10, 'arma', 0)[0]


def test_el_martillo_verde():
    """Sorteando sale dentro del rango; con la bandera, el maximo."""
    rangos = {'atk': (0, 210), 'dfs': (0, 210), 'rigor': (0, 54),
              'velocidad': (0, 40)}
    r = m.tirar_verde(rangos, todos=False, rng=random.Random(5))
    for k, (lo, hi) in rangos.items():
        assert lo <= r[k] <= hi, (k, r[k])
    todo = m.tirar_verde(rangos, todos=True)
    assert todo == {k: hi for k, (lo, hi) in rangos.items()}


def test_las_ranuras_de_equipo_que_faltaban():
    """Las insignias y el segundo trinket, que no se podian usar.

    Las insignias (categoria 徽章) no declaran ninguna columna de equipo, asi
    que se quedaban sin ranura: no se podian poner y sus bonos no llegaban
    nunca, aunque se leyeran bien. Van en la 175, medido al ponerse una
    Purple Seashell Badge en el servidor real.

    Y los accesorios tienen DOS ranuras, la 8 y la 9 -- los dos "Trinket" de
    la ventana --, no una: se vio un Stealth Ring en la 9.
    """
    import inventario as inv

    # La insignia tiene ranura, y esa ranura cuenta como equipo.
    assert inv.ranura_equipo_de(70792) == inv.RANURA_INSIGNIA == 175
    assert inv.es_equipo(175)
    assert not inv.es_equipo(176)

    # Y sus bonos llegan de verdad a los stats.
    bonos = inv._bonus(70792)
    assert bonos['hp'] == 6800 and bonos['atk'] == 3484
    sin_ella = inv.vida_maxima(280, [], bolsa={20: 10})
    con_ella = inv.vida_maxima(280, [], bolsa={20: 10, 175: 70792})
    assert con_ella == sin_ella + bonos['hp'], (sin_ella, con_ella)

    # El segundo trinket.
    assert inv.ranuras_posibles(24954) == [8, 9]
    assert inv.ranura_libre_equipo(24954, {}) == 8
    assert inv.ranura_libre_equipo(24954, {8: 1}) == 9


def test_el_mas_n_y_los_stats_verdes_viajan_en_la_entrada():
    """Los dos datos que el cliente necesita para pintar el tooltip.

    El "+N" va en el byte 83 de la entrada: se midio viendo ir y venir unas
    Boots Of Contempt -- 6 -> 5 al fallar, 5 -> 6 y 6 -> 7 al acertar.

    Los stats del martillo verde van desde el 13, en registros de cuatro
    bytes [u16 valor][u8 0][u8 id]. Los ids salieron comparando nueve
    tiradas contra los rangos que enseñaba el cuadro del juego, porque cada
    valor solo cabia en uno: HP 0-272, MP 0-184, Defense 0-824, Spell
    Defense 0-145, Agility 0-27. La tirada que dio "HP 53, MP 178" aparecio
    como dos registros, id 4 e id 12.
    """
    import inventario as inv

    linea = inv.actualizar_ranura(4794, 6, 32763, 1, None, 0x11e)
    assert linea[6 + inv.OFF_MEJORA] == 0

    con_mas = inv.marcar_mejora(linea, 7)
    assert con_mas[6 + inv.OFF_MEJORA] == 7
    # Y no toca nada mas.
    assert sum(1 for a, b in zip(linea, con_mas) if a != b) == 1

    con_verde = inv.marcar_extras(linea, {'hp': 53, 'mp': 178})
    assert inv.leer_extras(con_verde) == {'hp': 53, 'mp': 178}

    # Los dos a la vez conviven: van en sitios distintos.
    ambos = inv.marcar_extras(inv.marcar_mejora(linea, 7),
                              {'dfs': 681, 'agilidad': 21})
    assert ambos[6 + inv.OFF_MEJORA] == 7
    assert inv.leer_extras(ambos) == {'dfs': 681, 'agilidad': 21}

    # Los nueve stats que puede dar, ida y vuelta.
    todos = {'hp': 100, 'mp': 90, 'atk': 200, 'dfs': 192, 'matk': 105,
             'mdef': 137, 'rigor': 8, 'agilidad': 38, 'velocidad': 40}
    # Solo caben CINCO registros por entrada: el sexto empezaria en el byte
    # 33, que es donde va el contenedor de la pieza. Aqui ponia seis, y por
    # eso el martillo verde con todos los stats cerraba el cliente.
    cinco = dict(list(todos.items())[:5])
    assert inv.leer_extras(inv.marcar_extras(linea, cinco)) == cinco
    entera = inv.marcar_extras(linea, cinco)
    assert entera[6 + 33:6 + 37] == linea[6 + 33:6 + 37]


def test_el_verde_no_pisa_el_contenedor():
    """Cinco stats como mucho: el sexto caeria encima del contenedor.

    Con la bandera de "todos los stats" salian siete, se escribian seis, y el
    sexto borraba los bytes 33..36, que dicen si la pieza esta en la mochila
    o en el banco. El cliente se cerraba con "This program will be
    terminated becuase an error occur".
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import inventario as _inv
    rangos = {'atk': (0, 210), 'dfs': (0, 210), 'matk': (0, 210),
              'mdef': (0, 210), 'rigor': (0, 54), 'agilidad': (0, 54),
              'velocidad': (0, 40)}
    v = m.tirar_verde(rangos, todos=True)
    assert len(v) <= 5, v
    e = _inv._entrada(4794, 20, 5293, 1, None, 0x11e)
    marcada = _inv.marcar_extras(e, v)
    assert marcada[33:37] == e[33:37], 'el contenedor se piso'
    assert _inv.leer_extras(marcada) == v


def test_la_mascota_no_es_un_accesorio():
    """item.xml las manda a la ranura 9, que es el segundo Trinket."""
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import inventario as _inv
    for r in (1, 8, 9, 175):
        assert not _inv.es_ranura_valida(20012, r), r
    assert _inv.es_ranura_valida(20012, 34), 'en la mochila si'
    assert _inv.es_ranura_valida(290, 9), 'un accesorio normal sigue entrando'
    # El 5293 que se usaba aqui como "accesorio" es la Shark Armor, categoria
    # 機甲: un robot. Va en la ranura de la montura ("Ride / Robot").
    assert _inv.ranura_equipo_de(5293) == 10
    assert not _inv.es_ranura_valida(5293, 9)


def test_cada_pieza_reparte_lo_suyo():
    """Una espada no da defensa y unas botas no dan ataque.

    Contado en las entradas capturadas: en mas de 700 registros de armas no
    aparece dfs ni una vez, y en los de armadura no aparece atk. La tabla
    plana de antes daba los dos a todo.
    """
    arma = m.tirar_verde(m.rangos_verde(25670), todos=True)      # espada
    assert 'atk' in arma and 'dfs' not in arma, arma
    botas = m.tirar_verde(m.rangos_verde(32763), todos=True)
    assert 'dfs' in botas and 'atk' not in botas, botas
    # La velocidad es solo de las monturas, y no se puede quedar fuera por
    # el tope de cinco.
    montura = m.tirar_verde(m.rangos_verde(4159), todos=True)
    assert 'velocidad' in montura, montura
    for otra in (25670, 32763, 1869, 1873, 1784):
        assert 'velocidad' not in m.tirar_verde(m.rangos_verde(otra),
                                                todos=True), otra
    # La mochila da vida, mana y defensa, y ademas PESO y RANURAS, que no
    # los da ninguna otra pieza. Medidos en una Green Beetle Bag: los ids
    # 28 y 192 de la entrada, que el juego enseña como "Maximum Weight" y
    # "Backpack slots".
    bolso = m.tirar_verde(m.rangos_verde(1869), todos=True)
    assert set(bolso) == {'hp', 'mp', 'dfs', 'peso', 'ranuras'}, bolso
    for otra in (25670, 32763, 4159, 1873, 1784):
        sale = m.tirar_verde(m.rangos_verde(otra), todos=True)
        assert 'peso' not in sale and 'ranuras' not in sale, (otra, sale)


def test_los_topes_salen_de_adv_xml():
    """Los rangos son una TABLA, no una formula.

    Aqui hubo dos intentos de deducirla -- un tope fijo por categoria y
    luego 5*nivel-60 -- y los dos estaban mal. Lo que los tumbo fue usar el
    mismo martillo en dos piezas y ver que daban rangos distintos. El dato
    bueno es adv.xml, y estos cuatro se comprobaron contra el juego:
    """
    esperado = {
        58790: {'hp': 344, 'atk': 2428, 'matk': 697, 'agilidad': 30},
        500: {'atk': 17, 'dfs': 17, 'rigor': 13, 'velocidad': 14},
        6851: {'atk': 50, 'dfs': 50, 'rigor': 22, 'velocidad': 22},
        1869: {'dfs': 24, 'peso': 325, 'ranuras': 10},
    }
    if not m.rangos_verde(6851):
        return                      # sin los paks no hay nada que probar
    for item, topes in esperado.items():
        r = m.rangos_verde(item)
        for stat, tope in topes.items():
            assert stat in r, (item, stat, r)
            assert r[stat][1] == tope, (item, stat, r[stat], tope)


def test_la_armadura_se_parte_en_tres():
    """Tunica, ligera y pesada tienen rangos muy distintos.

    En item.xml solo esta la marca de tunica (身體袍); las otras dos se
    separan por la proporcion entre su defensa y su defensa magica. El
    Spring Gown es tunica, y se sabe porque llego a 53 de defensa magica
    cuando la ligera topa en 20 y la pesada en 18.
    """
    if not m.rangos_verde(4112):
        return
    assert m.parte_de(4112) == '衣服袍', m.parte_de(4112)
    assert m.rangos_verde(4112)['mdef'][1] >= 53


def test_las_mejoras_sobreviven_a_reconectar():
    """El +N, las gemas y los stats verdes tienen que ir a disco.

    Vivian solo en memoria: se mejoraba un arma a +15, se salia, y al volver
    a entrar estaba limpia. Se guardan aparte del inventario porque hay
    veinte sitios que guardan la bolsa y solo uno que toca las mejoras.
    """
    import json as _json
    import sys as _s
    import tempfile
    from unittest.mock import patch
    _s.path.insert(0, str(RAIZ / 'server'))
    import cuentas

    with tempfile.TemporaryDirectory(prefix='ao_mejoras_') as directory:
      base = pathlib.Path(directory)
      with patch.multiple(cuentas, BASE=base, DB_PATH=base / 'cuentas.db',
                          ARCHIVO=base / 'cuentas.json', BACKUPS_DIR=base / 'backups'), \
           patch.object(cuentas, '_notificar_cambio'):
        cuentas._init_db()
        usuario, cid = 'test_only', 1
        fixture = dict(char_id=cid, ranura=0, nombre='Test Only', tile_x=1,
                       tile_y=1, habilidades=[], barra=[], quests=[], inventario={})
        con = cuentas._get_conn()
        try:
            con.execute('INSERT INTO cuentas(usuario,password) VALUES (?,?)', (usuario, ''))
            con.execute('INSERT INTO personajes(usuario,char_id,ranura,nombre,datos) VALUES (?,?,?,?,?)',
                        (usuario, cid, 0, fixture['nombre'], _json.dumps(fixture)))
            con.commit()
        finally:
            con.close()
        antes = {6: {'veces': 15, 'gemas': [3001], 'huecos': 1,
                     'extra': {'atk': 210, 'hp': 240}},
                 9: {'veces': 0, 'gemas': [], 'extra': {}}}
        cuentas.guardar_mejoras(usuario, cid, antes)
        d2 = cuentas.cargar()
        p = cuentas.personaje_de(d2['cuentas'][usuario], 0)
        despues = getattr(p, 'mejoras', None) or {}
        assert despues.get(6) == antes[6], despues
        # Las claves vuelven como numeros, no como el texto del JSON.
        assert all(isinstance(k, int) for k in despues), list(despues)
        # Una casilla sin nada no ocupa sitio en el guardado.
        assert 9 not in despues, despues


def test_ninguna_llamada_manda_el_inventario_sin_las_mejoras():
    """Nadie puede mandar inventario ni stats sin las mejoras.

    Habia SEIS llamadas a completo() y NUEVE a stats() que no las pasaban.
    Bastaba con que saltara una -- cambiar de mapa, pelear, un buff, subir
    de nivel -- para que el cliente recibiera el inventario limpio o los
    stats sin el "+15" del arma, y todo volviera a desaparecer.

    Se mira el ARBOL del fuente, no el texto: al corregirlo a mano el
    "mejoras=" se colo en el enviar() en vez de en el stats() de dentro, y
    eso compila pero tira el servidor en cuanto se usa. Un regex no lo
    habria visto; el arbol si.
    """
    import ast
    fuente = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')
    malas = []
    for n in ast.walk(ast.parse(fuente)):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nom = getattr(f, "attr", None) or getattr(f, "id", "")
        kw = [k.arg for k in n.keywords]
        if nom in ('completo', 'stats', 'vida_maxima', 'mana_maximo'):
            if 'mejoras' not in kw and len(n.args) < 4:
                malas.append('linea %d: %s() sin mejoras' % (n.lineno, nom))
        if nom == 'enviar' and 'mejoras' in kw:
            malas.append('linea %d: el mejoras= se colo en enviar()'
                         % n.lineno)
    assert not malas, malas


def test_los_huecos_y_sus_gemas_viajan_en_la_entrada():
    """El numero de huecos en el 82 y las gemas del 62 al 81.

    Medido perforando tres veces la misma pieza y comparando la entrada
    byte a byte: solo cambiaron el 82 (1 -> 2 -> 3) y los pares 62/63,
    66/67 y 70/71, con los ids 3113 Sapphire, 3118 Purple Gem y 3093 Ruby.

    Las cuentas cuadran solas: 62 + 5 huecos de 4 bytes = 82, que es donde
    empieza el contador. O sea CINCO huecos, ni uno mas. Y el tooltip lo
    dice igual: "a diamond has been set ( 1 / 2 )".
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import inventario as inv

    fin = inv.OFF_GEMAS + inv.MAX_HUECOS_ENTRADA * inv.TAM_GEMA
    assert fin == inv.OFF_HUECOS, (fin, inv.OFF_HUECOS)
    e = inv._entrada(4794, 3, 58790, 1, None, 286)
    m = inv.marcar_huecos(e, 3, [3113, 3118, 3093])
    assert inv.leer_huecos(m) == (3, [3113, 3118, 3093])
    # El "+N" vive en el 83 y no se pisa.
    con_mas = inv.marcar_mejora(m, 15)
    assert inv.leer_huecos(con_mas) == (3, [3113, 3118, 3093])
    assert con_mas[inv.OFF_MEJORA] == 15
    # Y no se pasa de cinco.
    lleno = inv.marcar_huecos(e, 9, [1, 2, 3, 4, 5, 6, 7])
    assert inv.leer_huecos(lleno)[0] == 5


def test_el_ciclo_de_perforar_y_engarzar():
    """Cinco huecos, cada uno con su gema antes de abrir el siguiente."""
    est = {}
    for paso in range(1, 6):
        ok, _ = m.perforar(est, 3, 6914, 100, 'arma', exito_seguro=True)
        assert ok, paso
        assert est[3]['huecos'] == paso
        ok2, _ = m.engarzar(est, 3, 3113, 100, 'arma')
        assert ok2, paso
        assert len(est[3]['gemas']) == paso
    ok, motivo = m.perforar(est, 3, 6914, 100, 'arma', exito_seguro=True)
    assert not ok and '5' in motivo, motivo


def test_los_huecos_leidos_de_una_captura_de_verdad():
    """Los God's Grip de la sesion, contra lo que enseñaba el tooltip.

    En pantalla ponia "has been intensified ( 1 ) times" y "a diamond has
    been set ( 1 / 2 )" con un Ruby debajo. En la captura la entrada de ese
    guante pasa por cuatro estados y el ultimo es exactamente ese: +1, dos
    huecos, el primero con el Ruby y el segundo vacio.
    """
    import glob
    import json
    import struct
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import inventario as inv

    vistos = []
    for f in glob.glob(str(RAIZ / 'logs' / 'proxy' / 'mundo_*.jsonl')):
        for linea in open(f, encoding='utf-8'):
            try:
                r = json.loads(linea)
            except Exception:
                continue
            if r.get('dir') != 's2c' or r.get('opcode') != 0x1B:
                continue
            h = r.get('hex') or ''
            if len(h) < 170:
                continue
            e = bytes.fromhex(h)[4:]
            if len(e) < 84:
                continue
            if struct.unpack_from('<I', e, 9)[0] != 1985:
                continue
            vistos.append((e[83],) + inv.leer_huecos(e))
    if not vistos:
        return                      # sin esa captura no hay nada que probar
    # 3093 es el Ruby. El estado final estaba en la captura.
    assert (1, 2, [3093, 0]) in vistos, vistos[:6]


def test_la_gema_da_un_stat_distinto_segun_donde_este():
    """El Broken Purple Lunar Rune, contra su propia descripcion.

    El item 54573 dice: "Weapon: Spell Attack +1320 / Armor: Spell Defense
    +260 / Shield: Spell Defense +260". Los NUMEROS estan en sus columnas
    (matk 1320, mdef 260) y el REPARTO en jeweleffect.xml, que para su fila
    pone 魔攻 en el arma y 魔防 en escudo y armadura.
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import inventario as inv
    if not inv.bono_gema(54573, 3):
        return                      # sin los paks no hay nada que probar
    assert inv.bono_gema(54573, 3) == {'matk': 1320}, 'en el arma'
    assert inv.bono_gema(54573, 4) == {'mdef': 260}, 'en el escudo'
    assert inv.bono_gema(54573, 6) == {'mdef': 260}, 'en las botas'
    # La Purple Gem lleva matk 20 y mdef 5; en armadura solo cuenta el mdef.
    assert inv.bono_gema(3118, 6) == {'mdef': 5}
    assert inv.bono_gema(3118, 3) == {'matk': 20}
    # Lo que no es una gema no da nada.
    assert inv.bono_gema(3001, 6) == {}


def test_las_gemas_suman_a_los_stats_del_personaje():
    """Dos runas en el arma tienen que dar 2640 de ataque magico."""
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import inventario as inv
    if not inv.bono_gema(54573, 3):
        return
    bolsa = {3: 58790}
    sin = inv.bonos_de_equipo(bolsa, {3: {'gemas': []}})
    con = inv.bonos_de_equipo(bolsa, {3: {'gemas': [54573, 54573]}})
    assert con['matk'] - sin['matk'] == 2640, (sin['matk'], con['matk'])


def test_la_mano_izquierda_cuenta_segun_lo_que_lleve():
    """La ranura 4 puede llevar ESCUDO o, con duales, otra ESPADA.

    Se decidia por la ranura, asi que la misma runa daba 1650 de ataque en
    la derecha y 630 de defensa en la izquierda: con armas duales esa mano
    perdia todo el ataque de sus gemas. Ahora manda la PIEZA.
    """
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'server'))
    import inventario as inv
    if not inv.bono_gema(54569, 3):
        return                      # sin los paks no hay nada que probar
    espada, escudo = 58786, 9
    assert inv.bono_gema(54569, 3, espada) == {'atk': 1650}
    assert inv.bono_gema(54569, 4, espada) == {'atk': 1650}, 'dual'
    assert inv.bono_gema(54569, 4, escudo) == {'dfs': 630}, 'con escudo'

    # Y las dos manos suman lo mismo con duales iguales.
    bolsa = {3: espada, 4: espada}
    gemas = {'gemas': [54569] * 5, 'extra': {}, 'veces': 0}
    sin = inv.bonos_de_equipo(bolsa, {3: {'gemas': []}, 4: {'gemas': []}})
    con = inv.bonos_de_equipo(bolsa, {3: dict(gemas), 4: dict(gemas)})
    assert con['atk_r'] - sin['atk_r'] == 8250, (sin['atk_r'], con['atk_r'])
    assert con['atk_l'] - sin['atk_l'] == 8250, (sin['atk_l'], con['atk_l'])


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
