"""Native clerk dialogue IDs/actions, with server-owned admission transactions.

Closed responses are measured in the user's Celestia/Play proxy captures.
Confirmation/success nodes are from map114; their event handlers must never
consume a second fee through the generic map interpreter.
"""
def mostrar(ses,stage,mid,options=(),actions=(),intent=None):
    import dialogos
    portrait = 69 if stage==112 else 71
    packet = dialogos.armar_linea(mid,portrait,list(options),acciones=list(actions))
    guion = [packet[2:]]
    ses.dlg_ent,ses.dlg_val,ses.dlg_guion,ses.dlg_paso = ses.personaje.entity_id,portrait,guion,1
    actions = list(actions)+[0]*len(options)
    ses.dlg_mapa = {'stage':114,'opciones':list(zip(options,actions)), 'guion':guion} if options else None
    ses._competicion_dialogo = dict(intent,guion=guion) if intent else None
    ses.enviar(packet)


def _rechazar(ses,stage,exc):
    import competiciones as c
    if getattr(exc,'dialogo',None):
        mostrar(ses,stage,exc.dialogo)
    else:
        # A real persistence conflict is not an official gameplay rejection.
        # It must remain explicit, never masquerade as a closed event.
        c.aviso(ses,exc)


def _validar(ses,stage,watch=False,reentry=False):
    import app, competiciones as c
    p,r = ses.personaje,c.ronda(stage)
    closed = 7607 if stage==112 else 7577
    if c.fase(r)=='cerrada':
        raise c.Rechazo('Registration is closed.',closed)
    member = c._miembro(r,ses)
    if reentry and not member:
        raise c.Rechazo('Not registered.',7612)
    if member:
        if stage==112 and watch and not member['espectador']:
            raise c.Rechazo('Already registered as a competitor.',7610)
        return
    if not watch and not r['min']<=p.nivel<=r['max']:
        raise c.Rechazo('Real level outside this round.',7575)
    if not watch and c.fase(r)!='registro' and not r.get('ingreso_tardio'):
        raise c.Rechazo('Registration has ended.',closed)
    if watch or (r.get('prueba') and not r.get('cobrar_entrada_en_pruebas',False)):
        return
    if stage in c.ARENAS:
        if int(getattr(ses,'oro',p.oro))<c.tramo(p.nivel)[6]:
            raise c.Rechazo('Not enough gold.',7576)
    else:
        import time
        now,meta = time.time(),p.mejoras or {}
        bag = [(s,it) for s,it in ses.inventario.items() if 20<=s<=app._tope_bolsa(ses.inventario)]
        live = any(it in c.PASES and (meta.get(s) or {}).get('holy_pass_fin',now+1)>now for s,it in bag)
        stone = any(it in c.PIEDRAS and app._cantidades(ses).get(s,1)>0 for s,it in bag)
        if not live and not stone:
            raise c.Rechazo('Battlefield Cursed Stone required.',7605)


def _resultado(ses,stage,watch=False,reentry=False):
    import competiciones as c
    _validar(ses,stage,watch,reentry)
    mid = (7611 if reentry else 7609 if watch else 7604) if stage==112 else (7580 if watch else 7574)
    mostrar(ses,stage,mid,intent={'stage':stage,'watch':watch,'fase':'viajar'})


def opcion(ses,opt):
    import competiciones as c
    if not ses.personaje or ses.personaje.stage!=114:
        return False
    stage = getattr(ses,'_competicion_clerk',None)
    if stage not in c.MAPAS:
        return False
    pending = getattr(ses,'_competicion_dialogo',None)
    pending = pending if pending and pending.get('guion') is getattr(ses,'dlg_guion',None) else None
    try:
        if pending:
            if opt in (7573,7603):
                c.cerrar_dialogo(ses)
                return True
            if pending['fase']=='confirmar' and opt in (7572,7579,7601,7602):
                _resultado(ses,stage,pending['watch'])
                return True
        joins = (7583,7585) if stage==112 else (7552,)
        watches = (7584,) if stage==112 else (7553,)
        if opt not in joins+watches:
            return False
        watch,reentry = opt in watches,opt==7585
        _validar(ses,stage,watch,reentry)
        if reentry or (stage==112 and c._miembro(c.ronda(stage),ses) and not watch):
            _resultado(ses,stage,watch,reentry=True)
        elif watch and stage==112:
            mostrar(ses,stage,7608,(7601,7602,7603),(1000039,1000040,0),
                    {'stage':stage,'watch':True,'fase':'confirmar'})
        else:
            #7753/7754 hard-code inflated amounts in this English XML.
            # Reuse the real neutral confirmation7571, never show a false fee.
            mid = 7571 if stage==112 else 7578 if watch else 7752 if stage==159 else 7571
            yes = 7579 if watch else 7572
            no = 7603 if stage==112 else 7573
            action = (1000019 if stage==159 else 1000141 if stage==239 else 1000167) if watch else (
                1000032 if stage==112 else 1000017 if stage==159 else 1000133 if stage==239 else 1000159)
            mostrar(ses,stage,mid,(yes,no),(action,0),
                    {'stage':stage,'watch':watch,'fase':'confirmar'})
            if not watch and stage in c.ARENAS:
                r = c.ronda(stage)
                free = c._miembro(r,ses) or (r.get('prueba') and not r.get('cobrar_entrada_en_pruebas',False))
                fee = 0 if free else c.tramo(ses.personaje.nivel)[6]
                c.aviso(ses,'Registration fee: %s gold.' % format(fee,','))
    except c.Rechazo as exc:
        _rechazar(ses,stage,exc)
    return True


def continuar(ses,valor):
    """Only the acknowledgement of the matching success page admits/charges."""
    import competiciones as c
    pending = getattr(ses,'_competicion_dialogo',None)
    if (not pending or pending.get('guion') is not getattr(ses,'dlg_guion',None)
            or pending.get('fase')!='viajar' or valor!=1):
        return False
    ses._competicion_dialogo = None
    if ses.personaje.stage!=114 or getattr(ses,'mapa_cargando',False):
        return True
    try:
        c.entrada(ses,pending['stage'],espectador=pending['watch'])
    except c.Rechazo as exc:
        _rechazar(ses,pending['stage'],exc)
    return True
