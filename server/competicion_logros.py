"""Official achievement.xml rules, with transactional per-round deduplication.

Counters are independent from Totem War. A persisted snapshot allows retries,
offline results and server restarts without duplicating wins or contributions.
"""
import json

HB = {
    '勝場次數': ('hb:win', False),
    '單場獲得積分': ('hb:score:best', True),
    '累積獲得積分': ('hb:score', False),
    '單場搶奪水晶數': ('hb:cristales:best', True),
    '累積搶奪水晶數': ('hb:cristales', False),
    '單場擊破城門數': ('hb:guard:best', True),
    '累積擊破城門數': ('hb:guard', False),
    '單場擊破雕像數': ('hb:idol:best', True),
    '累積擊破雕像數': ('hb:idol', False),
    '單場搭建城門': ('hb:build_guard:best', True),
    '累積搭建城門': ('hb:build_guard', False),
    '單場搭建雕像': ('hb:build_idol:best', True),
    '累積搭建雕像': ('hb:build_idol', False),
}
METRICAS = ('score', 'cristales', 'guard', 'idol', 'build_guard', 'build_idol')


def medir(fila, cont):
    regla, parametro = fila.get('regla'), str(fila.get('param1', ''))
    if regla not in ('聖域戰場規則', '戰天使擂台'):
        return None
    meta = int(fila.get('param2') or 0)
    if regla == '聖域戰場規則' and parametro in HB:
        return int(cont.get(HB[parametro][0], 0)), meta
    if regla == '戰天使擂台':
        if parametro.startswith('單週入圍'):
            puesto = int(cont.get('aa:best_rank', 0))
            return int(0 < puesto <= meta), 1
        key = {'累計入圍次數': 'aa:qualified', '累計奪冠次數': 'aa:win'}.get(parametro)
        if key:
            return int(cont.get(key, 0)), meta
    return None


def aplicar(con, ronda):
    """Must run inside the SAME transaction as the round/building mutation."""
    import logros
    con.execute('CREATE TABLE IF NOT EXISTS competiciones_logros '
                '(ronda TEXT, char_id INTEGER, datos TEXT NOT NULL, PRIMARY KEY(ronda,char_id))')
    if not ronda.get('logros_habilitados', True):
        return []
    notificaciones = []
    clasificacion = ronda.get('clasificacion', [])
    valido = (ronda.get('cerrada') and ronda.get('motivo') not in ('gm stop', 'gm', 'cancelled')
              and sum(bool(m.get('competidor', not m['espectador']))
                      for m in ronda['miembros'].values()) >= 2)
    for cid, miembro in ronda['miembros'].items():
        if not miembro.get('competidor', not miembro['espectador']):
            continue
        fila = __import__('competicion_identidad').fila(con,cid,miembro)
        if not fila:
            continue
        usuario,ranura,raw = fila
        data = json.loads(raw)
        anterior = con.execute('SELECT datos FROM competiciones_logros WHERE ronda=? AND char_id=?',
                               (ronda['id'], int(cid))).fetchone()
        antes = json.loads(anterior[0]) if anterior else {}
        actual = {k: int(miembro.get(k, 0)) for k in METRICAS} if ronda['stage'] == 112 else {}
        actual['win'] = int(bool(valido) and (
            miembro['equipo'] == ronda.get('ganador') if ronda['stage'] == 112
            else ronda.get('motivo') == 'last survivor' and bool(clasificacion) and clasificacion[0] == cid))
        if ronda['stage'] != 112 and valido and cid in clasificacion:
            actual['rank'] = clasificacion.index(cid)+1
            actual['qualified'] = int(actual['rank'] <= 32)
        if anterior and actual == antes:
            continue
        cont = dict(data.get('logros_cont') or {})
        prefijo = 'hb:' if ronda['stage'] == 112 else 'aa:'
        for key, cantidad in actual.items():
            if key == 'rank':
                previo = int(cont.get('aa:best_rank', 0))
                cont['aa:best_rank'] = min(previo or cantidad, cantidad)
                continue
            cont[prefijo+key] = int(cont.get(prefijo+key, 0)) + max(0, cantidad-antes.get(key, 0))
            if ronda['stage'] == 112 and key in METRICAS:
                base = miembro.get('segmento_base', {}).get(key, 0)
                cont[prefijo+key+':best'] = max(int(cont.get(prefijo+key+':best', 0)), cantidad-base)
        conseguidos = set(int(x) for x in (data.get('logros') or []))
        nuevos = [f['id'] for f in logros.tabla() if f['id'] not in conseguidos
                  and (valor := medir(f, cont)) is not None and valor[1] > 0 and valor[0] >= valor[1]]
        data.update(logros_cont=cont, logros=sorted(conseguidos | set(nuevos)))
        con.execute('UPDATE personajes SET datos=? WHERE usuario=? AND ranura=? AND char_id=?',
                    (json.dumps(data),usuario,ranura,int(cid)))
        con.execute('INSERT OR REPLACE INTO competiciones_logros VALUES (?,?,?)',
                    (ronda['id'], int(cid), json.dumps(actual)))
        notificaciones.append((usuario,int(cid), cont, data['logros'], nuevos))
    return notificaciones


def publicar(actualizaciones):
    import app
    import clases
    import logros
    sesiones = {(s.usuario.casefold(),s.personaje.char_id): s for s in app._tw_sesiones() if getattr(s, 'personaje', None)}
    for usuario,cid, cont, conseguidos, nuevos in actualizaciones:
        ses = sesiones.get((usuario.casefold(),cid))
        if not ses:
            continue
        p = ses.personaje
        # Load unrelated live counters before merging, never replace Supreme/etc.
        app._logros_datos(ses)
        p.logros_cont.update({k:v for k,v in cont.items() if k.startswith(('aa:', 'hb:'))})
        previos = set(logros.titulos_de(p.logros))
        p.logros = sorted(set(p.logros or []) | set(conseguidos))
        for lid in nuevos:
            f = logros.de_id(lid)
            ses.enviar(clases.aviso('Achievement completed: [%s] (+%d points)' %
                                   (f['nombre'], f.get('puntos', 0)), tipo=0))
        for titulo in set(logros.titulos_de(p.logros))-previos:
            ses.enviar(logros.paquete_titulo_nuevo(p.entity_id, titulo))
            apariencia = getattr(p,'apariencia',None) or [0]
            bc = clases.chat_super_broadcast(0,p.nombre,
                '%s has obtained the title [%s]!' % (p.nombre,logros.nombre_titulo(titulo)),
                int(apariencia[0]) & 1)
            for visor in sesiones.values():
                visor.enviar(bc)
        if nuevos and not getattr(ses, 'mapa_cargando', False):
            p._logros_ctx = dict(getattr(p,'_logros_ctx',None) or {}, cont=p.logros_cont)
            ses.enviar(logros.paquete(p, ctx={'cont': p.logros_cont}))
