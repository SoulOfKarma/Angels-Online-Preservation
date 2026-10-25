"""Astrologer, Login Rewarder y Green Angel: datos IGG, sin paquetes visuales inventados."""
import asyncio
import datetime
import json
import random
import struct
import time

import cuentas
from house_services import xml_rows

NOMBRES = {'Astrologer', 'Login Rewarder', 'Green Angel'}
ASTRO_IDS = range(14533, 14569)
GREEN_IDS = range(20428, 20431)
CRISTAL, STRAW, SELLO = 54852, 60469, 60470
COSTES = (0, 1_000_000, 2_500_000, 5_000_000)
GRUPOS_LOGIN = {515008: 526, 515009: 527, 515010: 528}
GRUPO_GREEN = 401  # Catalogo completo: pociones, cervezas y nueve monturas.


def bendecir(ses):
    """Blessing Angel, map041: 6755 hasta nivel 50, 6756 desde 51, 2 horas.

    No cobrar MP de una skill ni apilar los dos rangos al subir de nivel.
    La duracion y los bonos vienen del magic.xml vigente.
    """
    import app, combate
    p = ses.personaje
    if not p or p.stage != 41 or getattr(ses, 'muerto', False):
        return False
    mid = 6756 if p.nivel >= 51 else 6755
    mag = combate.datos_magia(mid)
    duration = int(xml_rows('magic.xml')[mid]['持續時間'])
    if getattr(p, 'buffs', None) is None:
        p.buffs = {}
    for previous in (6755, 6756):
        if previous != mid and p.buffs.pop(previous, None) is not None:
            ses.enviar(struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 4, previous, 0))
    entry = app._entrada_de_buff(mag, duration)
    entry['persist_death'] = True
    app._buff_a_otro(ses, mid, entry, duration * 1000, mag)
    if getattr(ses, 'usuario', None):
        cuentas.guardar_buffs(ses.usuario, p.char_id, p.buffs)
    return True


def saludo(nombre):
    return {'Astrologer': (142501, [142502, 142503, 142504, 142505]),
            'Login Rewarder': (515006, [515007, 515008, 515009, 515010, 515011]),
            'Green Angel': (513638, [513639, 513640, 513641, 513642, 513643])}[nombre]


def bendicion_party(ses):
    """Original free Party Angel blessing, including production/EXP bonuses."""
    import recent_mall,app,combate
    if not recent_mall.cerca(ses,'Party Angel') or getattr(ses,'muerto',False):return False
    if getattr(ses,'_recent_mall_npc',None)!='Party Angel':return False
    mid=14955
    duration=int(xml_rows('magic.xml')[mid]['\u6301\u7e8c\u6642\u9593'])
    entry=entrada_buff(mid)
    entry['drop_extra_pct']=int(xml_rows('magic.xml')[mid].get('\u6389\u5bf6\u52a0\u500d') or 0)
    app._buff_a_otro(ses,mid,entry,duration*1000,combate.datos_magia(mid))
    cuentas.guardar_buffs(ses.usuario,ses.personaje.char_id,ses.personaje.buffs)
    return True


def mostrar(ses, mensajes, opciones=()):
    import dialogos
    cara = getattr(ses, 'dlg_val', 4)
    guion = [dialogos.armar_linea(mid, cara, list(opciones) if i == len(mensajes)-1 else [])[2:]
             for i, mid in enumerate(mensajes)]
    ses.dlg_guion, ses.dlg_paso = guion, 1
    ses.enviar(dialogos.linea_de(guion, 0, ses.personaje.nombre))


def usos_hoy(ses):
    con = cuentas._get_conn()
    try:
        row = con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',
                          (ses.usuario, ses.personaje.char_id)).fetchone()
        d = json.loads(row[0]).get('astrologer', {}) if row else {}
        return int(d.get('usos', 0)) if d.get('dia') == datetime.date.today().isoformat() else 0
    finally:
        con.close()


def entrada_buff(mid):
    import app, combate
    r = xml_rows('magic.xml')[mid]
    mag = combate.datos_magia(mid)
    e = app._entrada_de_buff(mag, int(r['持續時間']))
    # Campos de servicios que no traduce el lector general de hechizos.
    for de, a in (('負重', 'carga'), ('採集速度', 'recoleccion_pct'),
                  ('製作速度', 'fabricacion_pct'), ('經驗加倍', 'exp_extra_pct'),
                  ('技能經驗加倍', 'skill_exp_extra_pct')):
        e[a] = int(r.get(de) or 0)
    e['persist_death'] = True
    return e


def bono(buffs, campo):
    ahora = time.time()
    return sum(float(e.get(campo) or 0) for e in (buffs or {}).values()
               if isinstance(e, dict) and e.get('fin', 0) > ahora)


class Rechazo(Exception):
    def __init__(self, mensaje):
        self.mensaje = mensaje


def confirmar(ses, servicio, esperado=None):
    """Un commit para coste, contador, inventario, buff o sello. Nada se gasta al fallar."""
    import app, configuracion
    p = ses.personaje
    if p.stage != 41 or getattr(ses, 'muerto', False):
        return None
    app._logros_datos(ses)
    bolsa, cantidades = dict(ses.inventario), dict(app._cantidades(ses))
    buffs = dict(getattr(p, 'buffs', None) or {})
    cont = dict(p.logros_cont)
    oro = int(ses.oro)
    tocadas, quitados, mid = [], [], None
    hoy = datetime.date.today().isoformat()
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',
                              (ses.usuario, p.char_id)).fetchone()
            if not row:
                raise RuntimeError('Personaje no encontrado; servicio cancelado')
            d = json.loads(row[0])
            item, cantidad, coste = 0, 0, 0
            if servicio == 'astro':
                anterior = d.get('astrologer', {})
                n = int(anterior.get('usos', 0)) if anterior.get('dia') == hoy else 0
                if n >= 5:
                    raise Rechazo(142506)
                # No confirmar una tarifa distinta de la que el jugador acepto.
                if esperado != (hoy, n):
                    return None
                if n == 4:
                    item, cantidad = CRISTAL, 1
                else:
                    coste = COSTES[n]
                if oro < coste:
                    raise Rechazo(142515)
                pesos = (configuracion.ASTRO_PESOS_CRISTAL if n == 4
                         else configuracion.ASTRO_PESOS_NORMAL)
                nivel = random.choices((0, 1, 2), weights=pesos, k=1)[0]
                mid = 14533 + random.randrange(12)*3 + nivel
                d['astrologer'] = {'dia': hoy, 'usos': n+1}
            elif servicio in ('green_buff', 'green_stamp'):
                item, cantidad = STRAW, 30 if servicio == 'green_buff' else 100
                if servicio == 'green_buff':
                    mid = 20428 + (2 if p.nivel >= 210 else 1 if p.nivel >= 100 else 0)
                else:
                    clave = 'obtiene:%d' % SELLO
                    cont[clave] = int(cont.get(clave, 0)) + 1
            else:
                raise ValueError(servicio)
            if item:
                falta = cantidad
                for slot, it in sorted(bolsa.items()):
                    if it != item or not 20 <= slot <= app._tope_bolsa(bolsa):
                        continue
                    hay = int(cantidades.get(slot, 1))
                    tomar = min(falta, hay)
                    falta -= tomar
                    tocadas.append(slot)
                    if tomar == hay:
                        del bolsa[slot]
                        cantidades.pop(slot, None)
                    else:
                        cantidades[slot] = hay-tomar
                    if not falta:
                        break
                if falta:
                    raise Rechazo(142510 if servicio == 'astro' else 513656)
            if mid:
                familia = ASTRO_IDS if servicio == 'astro' else GREEN_IDS
                for bid in list(buffs):
                    if str(bid).isdigit() and int(bid) in familia:
                        quitados.append(int(bid))
                        buffs.pop(bid)
                buffs[mid] = entrada_buff(mid)
                clave = 'buff:%d' % mid
                cont[clave] = int(cont.get(clave, 0)) + 1
                if item == CRISTAL:
                    clave = 'usa:%d' % CRISTAL
                    cont[clave] = int(cont.get(clave, 0)) + 1
            oro -= coste
            d.update(oro=oro, inventario={str(k): v for k, v in bolsa.items()},
                     cantidades={str(k): v for k, v in cantidades.items()},
                     buffs={str(k): v for k, v in buffs.items()}, logros_cont=cont)
            con.execute('UPDATE personajes SET datos=?, actualizado_en=CURRENT_TIMESTAMP '
                        'WHERE usuario=? AND char_id=?',
                        (json.dumps(d, ensure_ascii=False), ses.usuario, p.char_id))
            con.commit()
        finally:
            con.close()
    # Solo despues del commit se modifica la sesion.
    ses.oro = p.oro = oro
    ses.inventario.clear()
    ses.inventario.update(bolsa)
    p.inventario = ses.inventario
    app._cantidades(ses).clear()
    app._cantidades(ses).update(cantidades)
    p.cantidades = app._cantidades(ses)
    for slot in tocadas:
        if slot not in bolsa:
            app._instancias(ses).pop(slot, None)
    p.buffs, p.logros_cont = buffs, cont
    cuentas._notificar_cambio()
    ses.enviar(*app._refrescar(ses, tocadas, con_oro=True))
    for bid in quitados:
        ses.enviar(struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 4, bid, 0))
    if mid:
        publicar_buff(ses, mid)
    app._logros_actualizar(ses, enviar=True)
    app._logros_guardar(ses)
    return mid or SELLO


def publicar_buff(ses, mid):
    import app, combate
    p = ses.personaje
    fin = p.buffs[mid]['fin']
    def enviar():
        p.hp = min(p.hp, app._vida_max(p, ses.inventario))
        p.mp = min(p.mp, app._mana_max(p, ses.inventario))
        ses.enviar(struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 4, mid,
                               max(0, int((fin-time.time())*1000))),
                   combate.atributo(p.entity_id, p.hp, combate.KIND_HP),
                   combate.atributo(p.entity_id, p.mp, combate.KIND_MP), app._stats_ses(ses))
    enviar()
    def caducar():
        if (getattr(ses, 'cerrada', False) or ses.personaje is not p
                or (p.buffs.get(mid) or {}).get('fin') != fin):
            return
        p.buffs.pop(mid, None)
        cuentas.guardar_buffs(ses.usuario, p.char_id, p.buffs)
        if not getattr(ses, 'cerrada', False):
            enviar()
    try:
        asyncio.get_running_loop().call_later(max(0, fin-time.time()), caducar)
    except RuntimeError:
        pass


def procesar_opcion(ses, nombre, opcion):
    """Solo opciones presentes en el dialogo activo (ver guardia del dispatcher)."""
    import dialogos
    if nombre not in NOMBRES or ses.personaje.stage != 41:
        return False
    if opcion in (142505, 142509, 515011, 513643, 513653):
        ses.dlg_ent = None
        ses._astro_pendiente = None
        ses.enviar(struct.pack('<H', 0x0012) + dialogos.FIN)
        return True
    if nombre == 'Astrologer':
        if opcion in (142502, 142533):
            n = usos_hoy(ses)
            ses._astro_pendiente = (datetime.date.today().isoformat(), n)
            mostrar(ses, [142506 if n >= 5 else (142514, 142513, 142512, 142511, 142507)[n]],
                    [] if n >= 5 else [142508, 142509])
        elif opcion == 142503:
            mostrar(ses, [142516, 142517, 142518], [142502, 142505])
        elif opcion == 142504:
            mostrar(ses, [142519, 142520], [142502, 142505])
        elif opcion == 142508:
            esperado = getattr(ses, '_astro_pendiente', None)
            ses._astro_pendiente = None
            try:
                mid = confirmar(ses, 'astro', esperado)
                if mid:
                    mostrar(ses, [142521+(mid-14533)//3], [142533, 142505])
                else:
                    mostrar(ses, [142501], [142502, 142505])
            except Rechazo as e:
                mostrar(ses, [e.mensaje], [142502, 142505])
        else:
            return False
    elif nombre == 'Login Rewarder':
        if opcion in (515007, 515014):
            mostrar(ses, [515012, 515013], [515008, 515009, 515010, 515011])
        elif opcion in GRUPOS_LOGIN:
            ses._lyceum_exchange = GRUPOS_LOGIN[opcion]
            ses.enviar(struct.pack('<HI', 0x0151, GRUPOS_LOGIN[opcion]),
                       struct.pack('<H', 0x0012) + dialogos.FIN)
            ses.dlg_ent = None
        else:
            return False
    else:
        if opcion in (513639, 513645):
            mostrar(ses, [513644, 513646], [513647, 513648, 513649, 513653])
        elif opcion == 513647:
            mostrar(ses, [513650, 513651, 513652], [513640, 513653])
        elif opcion == 513648:
            mostrar(ses, [513654], [513641, 513653])
        elif opcion in (513642, 513649):
            # 348 es la version antigua, limitada a pociones. El 401 incluye
            # Frozen White Bear / Speedy Horse / Mooing Calf y sus variantes.
            ses._lyceum_exchange = GRUPO_GREEN
            ses.enviar(struct.pack('<HI', 0x0151, GRUPO_GREEN), struct.pack('<H', 0x0012)+dialogos.FIN)
            ses.dlg_ent = None
        elif opcion in (513640, 513641, 513662):
            try:
                mid = confirmar(ses, 'green_buff' if opcion == 513640 else 'green_stamp')
                if mid:
                    mostrar(ses, [({20428: 513658, 20429: 513659, 20430: 513657}.get(mid, 513660))],
                            [513640, 513641, 513653])
            except Rechazo as e:
                mostrar(ses, [e.mensaje], [513640, 513641, 513653])
        else:
            return False
    return True


def straw_drop_monstruo(stage, monstruo):
    # Monstruo de combate no define .nivel en los spawns normales. No tratar
    # esa ausencia como nivel cero: el NPC type identifica su fila oficial.
    nivel = int(getattr(monstruo, 'nivel', 0) or 0)
    if nivel <= 0:
        r = xml_rows('monster.xml').get(int(monstruo.npc_type)) or {}
        nivel = int(r.get('等級') or 0)
    return straw_drop(stage, nivel)


def straw_drop(stage, nivel):
    """Chance de evento aparte del loot normal; sin mapas privados ni nivel del jugador."""
    import configuracion
    r = xml_rows('stage.xml').get(int(stage))
    if (int(nivel or 0) < 21 or not r or r.get('動態空間') == '是'
            or r.get('分配類型') or r.get('平行空間')):
        return []
    return [(STRAW, 1)] if random.random() < configuracion.STRAW_DROP_PROBABILIDAD else []


def canjear(ses, receta_id, veces):
    """Solo nuestros grupos: validar espacio y materiales antes del commit.

    True indica que la receta fue atendida (incluso si se rechazo). El resto
    conserva su manejador existente; no cambia otros sistemas de canje.
    """
    import app, clases, inventario
    row = xml_rows('exchange.xml').get(int(receta_id)) or {}
    grupo = int(row.get('群組') or 0)
    if grupo not in (280, 348, GRUPO_GREEN, 526, 527, 528):
        return False
    def fallo(texto):
        ses.enviar(clases.aviso(texto, tipo=7, msg_id=clases.MSG_TEXTO))
        return True
    if (ses.personaje.stage != 41 or getattr(ses, 'muerto', False)
            or getattr(ses, '_lyceum_exchange', None) != grupo):
        return fallo('Open this exchange at its NPC first.')
    if grupo==280 and not __import__('olympus').cerca(ses,'Olly'):
        return fallo('Return to Olly to exchange Olympus Certs.')
    receta = app._obtener_receta_exchange(receta_id)
    if not receta or not receta['materiales'] or not receta['premios']:
        return fallo('Invalid exchange recipe.')
    bolsa, cantidades = dict(ses.inventario), dict(app._cantidades(ses))
    tocadas, nuevas = set(), set()
    veces = max(1, min(100, int(veces)))
    for item, n in receta['materiales']:
        falta = n*veces
        for slot, it in sorted(bolsa.items()):
            if it != item or not 20 <= slot <= app._tope_bolsa(bolsa):
                continue
            hay = int(cantidades.get(slot, 1))
            tomar = min(falta, hay)
            falta -= tomar
            tocadas.add(slot)
            if tomar == hay:
                del bolsa[slot]
                cantidades.pop(slot, None)
            else:
                cantidades[slot] = hay-tomar
            if not falta:
                break
        if falta:
            return fallo("You don't have enough materials for this exchange.")
    for item, n in receta['premios']:
        apilable = inventario.es_apilable(item)
        for cantidad in ([n*veces] if apilable else [1]*(n*veces)):
            slot = next((s for s,it in bolsa.items() if apilable and it == item
                         and 20 <= s <= app._tope_bolsa(bolsa)), None)
            if slot is None:
                slot = app._ranura_libre(bolsa)
                if slot is None:
                    return fallo('Your backpack is full; no materials were consumed.')
                nuevas.add(slot)
                bolsa[slot] = item
                cantidades[slot] = 0
            cantidades[slot] = int(cantidades.get(slot, 1)) + cantidad
            tocadas.add(slot)
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            r = con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',
                            (ses.usuario, ses.personaje.char_id)).fetchone()
            if not r:
                raise RuntimeError('Exchange character not found')
            d = json.loads(r[0])
            if grupo==280 and not cuentas.inventario_equivalente(d,ses.inventario,app._cantidades(ses)):
                return fallo('Inventory changed; reconnect before exchanging. No materials were consumed.')
            d.update(inventario={str(k):v for k,v in bolsa.items()},
                     cantidades={str(k):v for k,v in cantidades.items()})
            for slot in tocadas:
                if slot in nuevas or slot not in bolsa:
                    d.setdefault('mejoras', {}).pop(str(slot), None)
            con.execute('UPDATE personajes SET datos=?, actualizado_en=CURRENT_TIMESTAMP '
                        'WHERE usuario=? AND char_id=?',
                        (json.dumps(d, ensure_ascii=False), ses.usuario, ses.personaje.char_id))
            con.commit()
        finally:
            con.close()
    ses.inventario.clear()
    ses.inventario.update(bolsa)
    app._cantidades(ses).clear()
    app._cantidades(ses).update(cantidades)
    ses.personaje.inventario, ses.personaje.cantidades = ses.inventario, app._cantidades(ses)
    for slot in tocadas:
        if slot in nuevas or slot not in bolsa:
            app._instancias(ses).pop(slot, None)
            (getattr(ses.personaje, 'mejoras', None) or {}).pop(slot, None)
    cuentas._notificar_cambio()
    ses.enviar(*app._refrescar(ses, sorted(tocadas)),
               clases.aviso('Exchange successful!', tipo=7, msg_id=clases.MSG_TEXTO))
    for item, n in receta['premios']:
        app._logros_contar(ses, 'obtiene:%d' % item, n*veces)
    return True
