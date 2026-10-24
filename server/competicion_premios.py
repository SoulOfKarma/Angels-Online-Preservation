"""Configurable result rewards with an idempotent SQLite delivery ledger.

Unknown official tables remain NULL; explicit authorized fallback is separate.
Plans are frozen at round creation. Full bags leave claims pending, and
disconnects/retries cannot duplicate gold, experience or items.
"""
import copy
import json


def informar_reclamacion(ses,stage):
    """Distinguish missing reward data from full bags or absent placement."""
    import cuentas,competiciones as c
    with cuentas._get_conn() as con:
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='competiciones_premios'").fetchone()
        rows=(con.execute('SELECT ronda,estado,plan FROM competiciones_premios WHERE char_id=? ORDER BY rowid DESC',
                          (ses.personaje.char_id,)).fetchall() if exists else [])
        for rid,state,raw_plan in rows:
            record=con.execute('SELECT datos FROM competiciones_resultados WHERE ronda=?',(rid,)).fetchone()
            if not record:continue
            r=json.loads(record[0]);member=c._miembro(r,ses)
            if r['stage']!=stage or not member or not member.get('competidor',not member['espectador']):continue
            rank=r.get('clasificacion',[])
            place=rank.index(str(ses.personaje.char_id))+1 if str(ses.personaje.char_id) in rank else 0
            if state=='sin_tabla':
                c.aviso(ses,'Your final place: %d. The reward table for your category is not configured; no reward has been marked as claimed.' % place)
            elif state=='entregado':
                c.aviso(ses,'You have already claimed this round\'s reward.')
                __import__('competicion_dialogos').mostrar(ses,stage,7781)
            elif state=='pendiente':
                c.aviso(ses,'Your reward is pending. Check free bag space and reconnect if your inventory is out of sync.')
                import app
                plan=json.loads(raw_plan) or {}
                free=sum(s not in ses.inventario for s in range(20,app._tope_bolsa(ses.inventario)+1))
                if free<len(plan.get('items',[])):
                    __import__('competicion_dialogos').mostrar(ses,stage,7762)
            elif state=='caducado':
                c.aviso(ses,'The four-hour Arena reward claim period has expired.')
                __import__('competicion_dialogos').mostrar(ses,stage,7775)
            else:
                c.aviso(ses,'There is no eligible reward for this round.')
                __import__('competicion_dialogos').mostrar(ses,stage,7781)
            return
    c.aviso(ses,'There is no final Arena placement to claim at this Clerk.')
    __import__('competicion_dialogos').mostrar(ses,stage,7781)


def validar_holy_exp(cfg):
    if not cfg:
        return
    if not isinstance(cfg,dict) or not 1<=int(cfg.get('puntos_tope',0))<=100000:
        raise ValueError('Invalid Holy EXP score cap')
    for key in ('exp_base_ppm','exp_victoria_ppm','exp_puntos_ppm',
                'skill_base_ppm','skill_victoria_ppm','skill_puntos_ppm'):
        if not 0<=int(cfg.get(key,0))<=1000000:
            raise ValueError('Invalid Holy EXP proportion')


def _holy_exp(r, miembro):
    """Explicit server compatibility policy, not a recovered official formula."""
    import combate
    cfg = r.get('holy_exp_config') or {}
    if not cfg.get('habilitado'):
        return None
    if not miembro.get('presente_al_cierre',False):
        return None
    points = max(0,min(int(miembro.get('score',0)),int(cfg['puntos_tope'])))
    victory = int(bool(points and r.get('ganador')==miembro['equipo']))
    def proportion(prefix):
        return (int(cfg.get(prefix+'_base_ppm',0))+victory*int(cfg.get(prefix+'_victoria_ppm',0))
                +points*int(cfg.get(prefix+'_puntos_ppm',0))//int(cfg['puntos_tope']))
    level = int(miembro['nivel'])
    gap = max(0,combate.exp_para_nivel(level+1)-combate.exp_para_nivel(level))
    return dict(exp=gap*proportion('exp')//1000000,skill_exp_ppm=proportion('skill'),
                skill_exp=0,oro=0,creditos=0,items=[],fuente=cfg.get('fuente','compatibilidad'))


def validar(rows, holy=False):
    if rows is None:
        return
    if not isinstance(rows,list):
        raise ValueError('Competition reward table must be a list or null')
    for row in rows:
        requeridos = {'nivel_min','nivel_max'} | ({'resultado'} if holy else {'puesto_min','puesto_max'})
        if not isinstance(row,dict) or not requeridos <= row.keys():
            raise ValueError('Incomplete competition reward row')
        if not 1 <= int(row['nivel_min']) <= int(row['nivel_max']):
            raise ValueError('Invalid reward level range')
        if holy:
            if row.get('resultado') not in ('ganador','perdedor','empate'):
                raise ValueError('Invalid Holy reward outcome')
        elif not 1 <= int(row['puesto_min']) <= int(row['puesto_max']):
            raise ValueError('Invalid Arena reward rank')
        if any(int(row.get(k,0)) < 0 for k in ('exp','oro','creditos','skill_exp','skill_exp_ppm')):
            raise ValueError('Negative competition reward')
        for item in row.get('items',[]):
            if not isinstance(item,dict) or not {'id','cantidad'} <= item.keys():
                raise ValueError('Incomplete competition item reward')
            if int(item['id']) <= 0 or not 1 <= int(item['cantidad']) <= 999:
                raise ValueError('Invalid competition item')
            if item.get('duracion_segundos'):
                raise ValueError('Timed certificate table not verified; refusing a permanent substitute')


def seleccionar(r, cid, miembro):
    if r.get('prueba') and not r.get('premios_en_pruebas'):
        return None, 'prueba'
    if r.get('motivo') in ('gm', 'gm stop', 'cancelled', 'empty round', 'no survivors'):
        return None, 'cancelado'
    if not miembro.get('competidor', not miembro['espectador']) or miembro.get('sin_puesto'):
        return None, 'observador'
    if sum(m.get('competidor', not m['espectador']) for m in r['miembros'].values()) < 2:
        return None, 'sin_competencia'
    rows = r.get('premios_config') or []
    if r['stage'] == 112:
        resultado = ('empate' if not r.get('ganador') else
                     'ganador' if miembro['equipo'] == r['ganador'] else 'perdedor')
        puesto = None
    else:
        ranking = r.get('clasificacion', [])
        if cid not in ranking:
            return None, 'sin_puesto'
        puesto, resultado = ranking.index(cid)+1, None
    matches = [row for row in rows if row['nivel_min'] <= miembro['nivel'] <= row['nivel_max']
               and (row.get('resultado') == resultado if r['stage'] == 112 else
                    row['puesto_min'] <= puesto <= row['puesto_max'])]
    if not matches and not rows and r['stage']==112:
        propio = _holy_exp(r,miembro)
        if propio:
            return propio,'pendiente'
        if (r.get('holy_exp_config') or {}).get('habilitado') and not miembro.get('presente_al_cierre'):
            return None,'ausente_al_cierre'
    if len(matches) != 1:
        return None, 'sin_tabla'  # Ambiguous rows also fail closed.
    row = matches[0]
    plan = {k:int(row.get(k, 0)) for k in ('exp','oro','creditos','skill_exp','skill_exp_ppm')}
    plan['items'] = copy.deepcopy(row.get('items', []))
    if any(v < 0 for k,v in plan.items() if k != 'items'):
        raise ValueError('Negative competition reward')
    for item in plan['items']:
        if int(item['id']) <= 0 or not 1 <= int(item['cantidad']) <= 999:
            raise ValueError('Invalid competition item reward')
        if item.get('duracion_segundos'):
            raise ValueError('Timed reward requires the verified certificate/exchange table; not a permanent substitute')
    return plan, 'pendiente'


def preparar(con, r):
    con.execute('CREATE TABLE IF NOT EXISTS competiciones_premios '
                '(ronda TEXT, char_id INTEGER, estado TEXT, plan TEXT, '
                'PRIMARY KEY(ronda,char_id))')
    for cid, m in r['miembros'].items():
        plan, estado = seleccionar(r, cid, m)
        compat=r.get('arena_premio_compat')
        if estado=='sin_tabla' and not r.get('premios_config') and compat:
            row=__import__('competicion_identidad').fila(con,cid,m)
            if row:
                plan=__import__('arena_premios_compat').plan(r,cid,m,json.loads(row[2]),compat)
                if plan:estado='pendiente'
        if plan:
            # Freeze each skill amount against its curve at result creation,
            # not against whatever level it has when retrying the delivery.
            import clases
            row = __import__('competicion_identidad').fila(con,cid,m)
            if not row:
                continue
            plan['usuario'] = row[0]
            plan['stage'] = r['stage']
            skills = json.loads(row[2]).get('habilidades',[]) if row else []
            plan['skill_rewards'] = [[int(sid),int(plan.get('skill_exp',0))+
                clases.exp_requerida_skill(int(lv),int(sid))*int(plan.get('skill_exp_ppm',0))//1000000]
                for sid,lv,_ in skills]
        con.execute('INSERT OR IGNORE INTO competiciones_premios VALUES (?,?,?,?)',
                    (r['id'], int(cid), estado, json.dumps(plan)))


def entregar(ses, automatico=False, stage=None):
    """Deliver only committed plans, in the same transaction as the claim."""
    import app
    import combate
    import competiciones as c
    import cuentas
    from producer_orders import apply_delivery
    p = getattr(ses, 'personaje', None)
    if not p or not getattr(ses, 'usuario', None) or getattr(ses, 'mapa_cargando', False):
        return 0
    c._cargar()
    entregadas = 0
    compat_entregada = False
    exp_entregada, skills_entregadas = 0, {}
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            # This also handles databases created before any round has ended.
            con.execute('CREATE TABLE IF NOT EXISTS competiciones_premios '
                        '(ronda TEXT, char_id INTEGER, estado TEXT, plan TEXT, PRIMARY KEY(ronda,char_id))')
            states="('pendiente','sin_tabla')" if not automatico and stage==240 else "('pendiente')"
            claims = con.execute("SELECT ronda,plan,estado FROM competiciones_premios WHERE char_id=? AND estado IN "+states,
                                 (p.char_id,)).fetchall()
            if not claims:
                con.rollback()
                return 0
            row = con.execute('SELECT datos FROM personajes WHERE char_id=? AND usuario=?',
                              (p.char_id,ses.usuario)).fetchone()
            if not row:
                con.rollback()
                return 0
            data = json.loads(row[0])
            if data.get('habilidades',[]) != [list(x) for x in (p.habilidades or [])]:
                con.rollback()
                return 0
            if not cuentas.inventario_equivalente(data,ses.inventario,app._cantidades(ses)):
                con.rollback()
                return 0
            for key in ('exp','nivel','oro','creditos'):
                if key in data and int(data[key]) != int(getattr(p,key,0)):
                    con.rollback()
                    return 0  # Do not overwrite unsaved combat progress.
            touched = set()
            for rid, raw, state in claims:
                plan = json.loads(raw)
                if state=='sin_tabla':
                    # Explicitly authorized fallback can repair this owner's
                    # unclaimed401+ result, never a paid/delivered/cancelled one.
                    if automatico or stage!=240:continue
                    record=con.execute('SELECT datos FROM competiciones_resultados WHERE ronda=?',(rid,)).fetchone()
                    if not record:continue
                    r=json.loads(record[0]);member=c._miembro(r,ses)
                    if not member or r['stage']!=stage or r.get('premios_config'):continue
                    _,eligibility=seleccionar(r,str(p.char_id),member)
                    if eligibility!='sin_tabla':continue
                    config=c.config_eventos().get('arena_premio_compat')
                    plan=__import__('arena_premios_compat').plan(r,str(p.char_id),member,data,config)
                    if not plan:continue
                    plan.update(usuario=ses.usuario,stage=stage,skill_rewards=[])
                    con.execute("UPDATE competiciones_premios SET estado='pendiente',plan=? WHERE ronda=? AND char_id=? AND estado='sin_tabla'",
                                (json.dumps(plan),rid,p.char_id))
                if plan.get('usuario') and plan['usuario'].casefold() != ses.usuario.casefold():
                    continue
                if not plan.get('usuario'):
                    # Legacy claims with ambiguous IDs cannot be safely delivered.
                    if con.execute('SELECT COUNT(*) FROM personajes WHERE char_id=?',(p.char_id,)).fetchone()[0] != 1:
                        continue
                if automatico and plan.get('stage') in c.ARENAS:
                    continue
                if stage in c.ARENAS and plan.get('stage') in c.ARENAS and plan['stage']!=stage:
                    continue
                if plan.get('reclamar_hasta',float('inf'))<=c.time.time():
                    con.execute("UPDATE competiciones_premios SET estado='caducado' WHERE ronda=? AND char_id=? AND estado='pendiente'",(rid,p.char_id))
                    continue
                before = copy.deepcopy(data)
                changed = set()
                try:
                    data, _ = apply_delivery(data, [], plan, level_curve=combate.exp_para_nivel if plan['exp'] else None,
                                             level_cap=combate.nivel_maximo(), rank_curve=combate.rango_de_creditos)
                    import clases
                    awards = dict(plan.get('skill_rewards',[]))
                    skills = []
                    for sid,level,points in data.get('habilidades',[]):
                        amount = int(awards.get(int(sid),0))
                        if amount:
                            points += amount
                            cap = min(combate.nivel_maximo(),int(data['nivel'])+(11 if int(sid) in range(20,32) else 0))
                            while level<cap and points>=max(1,clases.exp_requerida_skill(level,sid)):
                                points -= max(1,clases.exp_requerida_skill(level,sid))
                                level += 1
                            points = min(points,max(1,clases.exp_requerida_skill(level,sid)))
                        skills.append([sid,level,points])
                    data['habilidades'] = skills
                    for item in plan['items']:
                        bag = data.setdefault('inventario',{})
                        slot = next((s for s in range(20, app._tope_bolsa({int(k):v for k,v in bag.items()})+1)
                                     if str(s) not in bag), None)
                        if slot is None:
                            raise ValueError('Full bag')
                        bag[str(slot)] = int(item['id'])
                        data.setdefault('cantidades',{})[str(slot)] = int(item['cantidad'])
                        data.setdefault('mejoras',{}).pop(str(slot),None)
                        if item.get('caduca_en'):
                            data['mejoras'][str(slot)]={'arena_premio_fin':item['caduca_en'],
                                'arena_premio_item':int(item['id']),'arena_premio_ronda':rid}
                        changed.add(slot)
                except ValueError:
                    data = before
                    continue  # A full bag never marks a claim as delivered.
                touched.update(changed)
                exp_entregada += int(plan.get('exp',0))
                for sid,amount in plan.get('skill_rewards',[]):
                    skills_entregadas[sid] = skills_entregadas.get(sid,0)+amount
                con.execute("UPDATE competiciones_premios SET estado='entregado' WHERE ronda=? AND char_id=? AND estado='pendiente'",
                            (rid,p.char_id))
                entregadas += 1
                compat_entregada = compat_entregada or bool(plan.get('compatibilidad'))
            con.execute('UPDATE personajes SET datos=? WHERE char_id=? AND usuario=?',
                        (json.dumps(data),p.char_id,ses.usuario))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    if entregadas:
        for key in ('exp','nivel','oro','creditos','rango','hp_max','mp_max','habilidades'):
            if key in data:
                setattr(p,key,data[key])
        ses.oro = p.oro
        for slot in touched:
            ses.inventario[slot] = data['inventario'][str(slot)]
            app._cantidades(ses)[slot] = data['cantidades'][str(slot)]
            app._instancias(ses)[slot] = __import__('inventario').instancia_nueva()
            meta=data.get('mejoras',{}).get(str(slot))
            if meta:p.mejoras[slot]=copy.deepcopy(meta)
            else:p.mejoras.pop(slot,None)
        p.inventario = ses.inventario
        ses.enviar(*app._refrescar(ses,touched,con_oro=True), app._stats_ses(ses))
        import clases
        ses.enviar(clases.arbol(p.habilidades or []))
        if exp_entregada:
            ses.enviar(clases.aviso(str(exp_entregada),tipo=0,msg_id=clases.MSG_EXP))
        for sid,amount in skills_entregadas.items():
            if amount:
                ses.enviar(clases.aviso_doble(clases.MSG_SKILL_EXP,clases.nombre(sid),str(amount)))
        actual, siguiente = combate.exp_para_barra(p.nivel,p.exp)
        import struct
        ses.enviar(struct.pack('<HIB',0x001D,p.entity_id,4)+struct.pack('<BQ',29,p.nivel)
                   +struct.pack('<BQ',30,combate.exp_para_nivel(p.nivel))
                   +struct.pack('<BQ',31,siguiente)+struct.pack('<BQ',32,actual))
        c.aviso(ses,'Competition rewards delivered (%d claims).' % entregadas)
        if compat_entregada:
            c.aviso(ses,'Provisional 401+ Arena prize: original Lv280 equipment; expires 6 days and 10 hours after the event.')
        cuentas._notificar_cambio()
    return entregadas
