"""Aplica los cambios en rust/ao-login/src/mundo.rs para el soporte completo y exacto de
ranuras especiales (558, 376, 377..476, 477..496, 559..598) y barra 0x0044.
"""
import pathlib

def aplicar():
    p_mundo = pathlib.Path(r'rust/ao-login/src/mundo.rs')
    t = p_mundo.read_text(encoding='utf-8')

    # Despachador de 0x0044
    target_disp = "(0x0043, Some(d)) => gremios_runtime::procesar_comando_gremio(&mundo, &est, d, &mut c, &cuerpo),"
    disp_add = "\n                        (0x0044, Some(d)) => asignar_barra(&est, d, &cuerpo),"
    if "(0x0044, Some(d)) =>" not in t:
        assert target_disp in t, "target_disp no encontrado en mundo.rs"
        t = t.replace(target_disp, target_disp + disp_add)

    # Helpers asignar_barra y mover_deed_a_376
    fn_helpers = """/// 0x0044: Asignacion de hotkey en la barra (F1..F8, 1..8)
fn asignar_barra(est: &Estado, d: &mut Dentro, cuerpo: &[u8]) {
    if cuerpo.len() < 7 {
        return;
    }
    let slot = cuerpo[1] as usize;
    let tipo = cuerpo[2];
    let mid = u32::from_le_bytes([cuerpo[3], cuerpo[4], cuerpo[5], cuerpo[6]]) as i64;
    while d.mundo.barra.len() <= slot {
        d.mundo.barra.push(ao_datos::json::Value::from(0));
    }
    d.mundo.barra[slot] = if mid != 0 {
        ao_datos::json::Value::Array(vec![
            ao_datos::json::Value::from(tipo),
            ao_datos::json::Value::from(mid),
        ])
    } else {
        ao_datos::json::Value::from(0)
    };
    if let Ok(mut con) = est.base.conexion() {
        let _ = ao_juego::guardados::actualizar_personaje(
            &mut con,
            &d.usuario,
            d.ses.jugador.char_id,
            |f| {
                ao_juego::guardados::barra(f, &d.mundo.barra);
            },
        );
    }
    eprintln!(
        "barra slot {slot}: {} {mid}",
        if tipo == 2 { "objeto" } else { "hechizo" }
    );
}

#[allow(clippy::too_many_arguments)]
fn mover_deed_a_376(
    mundo: &Mundo2,
    comp: &mut Compartido,
    est: &Estado,
    _id: u64,
    d: &mut Dentro,
    org: i64,
    item_id: i64,
    t: f64,
    c: &mut Conexion,
) {
    let dia = hoy();
    let cid = d.ses.jugador.char_id;
    let nom = d.ses.jugador.nombre.clone();
    let raw = d.ses.jugador.datos.get("casa").and_then(Value::as_object).cloned();
    let Ok(casa) = comp.casas.obtener_o_crear(
        &mundo.rec.casas,
        cid,
        &Value::String(nom),
        10115,
        raw.as_ref(),
        &dia,
        t as i64,
    ) else {
        return;
    };
    if casa.deed_id == item_id {
        if d.ses.jugador.bolsa.items.get(&376) == Some(&item_id) || org == 376 {
            let mut pk = vec![aviso("This is already the size of your house.")];
            pk.extend(refrescar(mundo, comp, &mut d.ses.jugador, &[org], t));
            c.enviar(&pk);
            return;
        }
        let j = &mut d.ses.jugador;
        j.bolsa.items.shift_remove(&org);
        j.bolsa.cantidades.shift_remove(&ao_juego::botin::ClaveCantidad::Numero(org));
        j.bolsa.items.insert(376, item_id);
        let pk = refrescar(mundo, comp, j, &[org, 376], t);
        c.enviar(&pk);
        guardar_bolsa(est, d);
        return;
    }
    if d.ses.jugador.stage == 500 {
        let mut pk = vec![aviso("Leave the house before changing its deed.")];
        pk.extend(refrescar(mundo, comp, &mut d.ses.jugador, &[org, 376], t));
        c.enviar(&pk);
        return;
    }
    let cap_max = match item_id {
        10115 => 35,
        10116 => 60,
        10117 => 100,
        17934 => 120,
        17935 => 140,
        17936 => 160,
        17937 => 180,
        20076 => 180,
        _ => 35,
    };
    let puestos = casa.placed_furniture.iter().filter(|f| {
        let id = f.get("item_id").and_then(ao_juego::py::entero).unwrap_or(0);
        !mundo.rec.casas.es_escena_item(id) && !mundo.rec.casas.es_estilo_exterior_item(id)
    }).count() as i64;
    if puestos > cap_max {
        let mut pk = vec![aviso("Remove furniture before switching to this smaller house.")];
        pk.extend(refrescar(mundo, comp, &mut d.ses.jugador, &[org, 376], t));
        c.enviar(&pk);
        return;
    }
    let old_deed = casa.deed_id;
    casa.deed_id = item_id;
    let serializada = casa.serializar();
    let j = &mut d.ses.jugador;
    j.datos.insert("casa".into(), Value::Object(serializada.clone()));
    if org != 376 {
        if old_deed != 0 && old_deed != item_id {
            j.bolsa.items.insert(org, old_deed);
        } else {
            j.bolsa.items.shift_remove(&org);
            j.bolsa.cantidades.shift_remove(&ao_juego::botin::ClaveCantidad::Numero(org));
        }
    }
    j.bolsa.items.insert(376, item_id);
    let pk = refrescar(mundo, comp, j, &[org, 376], t);
    c.enviar(&pk);
    if let Ok(mut con) = est.base.conexion() {
        let _ = ao_juego::guardados::actualizar_personaje(&mut con, &d.usuario, d.ses.jugador.char_id, |f| {
            ao_juego::guardados::casa(f, &serializada);
        });
    }
    guardar_bolsa(est, d);
}

"""
    idx_barra = t.find("/// 0x0044: Asignacion de hotkey en la barra")
    idx_mover = t.find("/// 0x0012 `[u16 origen][u16 destino]`")
    if idx_barra != -1 and idx_mover != -1 and idx_barra < idx_mover:
        t = t[:idx_barra] + fn_helpers + t[idx_mover:]
    elif "fn asignar_barra(" not in t:
        target_mover = "/// 0x0012 `[u16 origen][u16 destino]`: mover o intercambiar casillas.\nfn mover_objeto("
        t = t.replace(target_mover, fn_helpers + target_mover)

    # mover_objeto
    idx_start = t.find("fn mover_objeto(")
    idx_end = t.find("// ---------------------------------------------------------------------------\n// Sala, presencia y social")
    assert idx_start != -1 and idx_end != -1, "delimitadores de mover_objeto no encontrados"

    nuevo_mover_objeto = """fn mover_objeto(
    mundo: &Mundo2,
    est: &Estado,
    id: u64,
    d: &mut Dentro,
    cuerpo: &[u8],
    c: &mut Conexion,
) {
    use ao_juego::bonos::es_equipo;
    if cuerpo.len() < 4 {
        return;
    }
    let rec = &mundo.rec;
    let t = ahora();
    let org = u16::from_le_bytes([cuerpo[0], cuerpo[1]]) as i64;
    let dst = u16::from_le_bytes([cuerpo[2], cuerpo[3]]) as i64;
    let Some(&it_org) = d.ses.jugador.bolsa.items.get(&org) else {
        eprintln!("mover {org} -> {dst}: la ranura {org} esta vacia");
        return;
    };
    let mut guard = mundo.comp.lock().unwrap_or_else(|e| e.into_inner());
    let comp = &mut *guard;
    let es_mueble = |r: i64| (377..=476).contains(&r);
    let protegido_mueble = |rec: &Recursos, j: &ao_juego::premiar::Jugador, slot: i64| -> bool {
        let Some(&item) = j.bolsa.items.get(&slot) else { return false };
        if rec.casas.item_a_mueble(item).is_none() { return false; }
        let vin = j.mejoras.as_ref()
            .and_then(|m| m.get(&clave(slot)))
            .and_then(|v| v.get("vinculacion"))
            .is_some_and(ao_juego::py::verdadero);
        es_mueble(slot) || vin
    };
    if (protegido_mueble(rec, &d.ses.jugador, org) && !es_mueble(dst))
        || (protegido_mueble(rec, &d.ses.jugador, dst) && !es_mueble(org))
    {
        let pk = refrescar(mundo, comp, &mut d.ses.jugador, &[org, dst], t);
        c.enviar(&pk);
        return;
    }
    if es_mueble(dst) && !es_mueble(org) && rec.casas.item_a_mueble(it_org).is_some() {
        if es_mueble(org) {
            c.enviar(&[aviso("This decoration is registered. Place it from your Furniture bag.")]);
            return;
        }
        if d.muerto {
            return;
        }
        if !(20..=TOPE_CON_MOCHILA).contains(&org) {
            return;
        }
        let libre = (377..=476).find(|s| !d.ses.jugador.bolsa.items.contains_key(s));
        let Some(dest) = libre else {
            c.enviar(&[aviso("Your Furniture bag is full. The item remains in your backpack.")]);
            return;
        };
        let j = &mut d.ses.jugador;
        let q = cant(j, org);
        if q > 1 {
            j.bolsa.cantidades.insert(ao_juego::botin::ClaveCantidad::Numero(org), q - 1);
        } else {
            j.bolsa.items.shift_remove(&org);
            j.bolsa.cantidades.shift_remove(&ao_juego::botin::ClaveCantidad::Numero(org));
        }
        j.bolsa.items.insert(dest, it_org);
        j.bolsa.cantidades.shift_remove(&ao_juego::botin::ClaveCantidad::Numero(dest));
        mover_inst(rec, j, org, dest, t);
        let cid = j.char_id;
        let mej = j.mejoras.get_or_insert_with(Default::default);
        let mut estado = mej.get(&clave(dest)).and_then(Value::as_object).cloned().unwrap_or_default();
        ao_juego::inventario::vincular_equipo(&rec.items.de(it_org), it_org, cid, &mut estado);
        mej.insert(clave(dest), Value::Object(estado));
        let mut pk = refrescar(mundo, comp, j, &[org, dest], t);
        pk.push(aviso("Decoration registered in your Furniture bag. It can now be placed and cannot be sold."));
        c.enviar(&pk);
        drop(guard);
        guardar_bolsa(est, d);
        return;
    }
    for (o_pet, d_pet) in [(org, dst), (dst, org)] {
        if d_pet != ao_juego::mascotas::RANURA_EQUIPO_MASCOTA || !d.ses.jugador.bolsa.items.contains_key(&o_pet) {
            continue;
        }
        let it_pet = d.ses.jugador.bolsa.items[&o_pet];
        if !rec.catalogo.es_mascota(it_pet) {
            let mut pk = vec![aviso("Only pets can be equipped here.")];
            pk.extend(refrescar(mundo, comp, &mut d.ses.jugador, &[org, dst], t));
            c.enviar(&pk);
            return;
        }
        let ficha = d.ses.jugador.mascotas.as_ref()
            .and_then(|m| m.get(&o_pet.to_string()));
        if let Some((err, _)) = ao_juego::mascotas::error_equipar_mascota(ficha) {
            let mut pk = vec![aviso(err)];
            pk.extend(refrescar(mundo, comp, &mut d.ses.jugador, &[org, dst], t));
            c.enviar(&pk);
            return;
        }
    }
    let deed_org = ao_juego::casas::es_deed_item(it_org) || rec.objetos.es_ranura_valida(it_org, 376);
    if dst == ao_juego::casas::SLOT_DEED && org != dst {
        if deed_org {
            mover_deed_a_376(mundo, comp, est, id, d, org, it_org, t, c);
        } else {
            let pk = refrescar(mundo, comp, &mut d.ses.jugador, &[org, dst], t);
            c.enviar(&pk);
        }
        return;
    }
    if org == ao_juego::casas::SLOT_DEED {
        let pk = refrescar(mundo, comp, &mut d.ses.jugador, &[org, dst], t);
        c.enviar(&pk);
        return;
    }
    if deed_org && (ao_juego::casas::SLOT_FURN_INI..=ao_juego::casas::SLOT_MOB_FIN).contains(&dst) {
        let mut pk = vec![aviso("House deeds are not furniture: use it (or drop it on the house slot) to change the size of your house.")];
        pk.extend(refrescar(mundo, comp, &mut d.ses.jugador, &[org, dst], t));
        c.enviar(&pk);
        return;
    }
    if (477..=496).contains(&dst) {
        let dia = hoy();
        let c_slots = comp.casas.obtener_o_crear(
            &rec.casas,
            d.ses.jugador.char_id,
            &Value::String(d.ses.jugador.nombre.clone()),
            10115,
            d.ses.jugador.datos.get("casa").and_then(Value::as_object),
            &dia,
            t as i64,
        );
        let mut valid = d.ses.jugador.stage == 500 && c_slots.as_ref().is_ok_and(|c| c.owner_id == d.ses.jugador.char_id);
        if let Ok(c_slots) = c_slots {
            if dst < 487 {
                valid = valid && rec.catalogo.es_mascota(it_org)
                    && dst < 477 + ao_juego::casas::ranuras_mascotas_validas(c_slots.level(&rec.casas));
            } else {
                let es_huevo = rec.objetos.es_ranura_valida(it_org, 487);
                valid = valid && es_huevo
                    && dst < 487 + ao_juego::casas::ranuras_mobgen_validas(c_slots.level(&rec.casas));
            }
        }
        if !valid {
            let pk = refrescar(mundo, comp, &mut d.ses.jugador, &[org, dst], t);
            c.enviar(&pk);
            return;
        }
    }
    let es_amplify_slot = |r: i64| (559..=598).contains(&r);
    let toca_amplify = es_amplify_slot(org) || es_amplify_slot(dst);
    if toca_amplify && es_amplify_slot(dst) {
        let abiertas = d.ses.sistemas.amplify.as_ref().map_or(0, |a| a.atributos.len());
        let es_pet = rec.catalogo.es_mascota(it_org);
        if dst - 559 >= abiertas as i64 || !es_pet {
            let txt = if es_pet { "This slot is locked!" } else { "Please insert a pet!" };
            let mut pk = vec![aviso(txt)];
            pk.extend(refrescar(mundo, comp, &mut d.ses.jugador, &[org, dst], t));
            c.enviar(&pk);
            return;
        }
    }
    if !rec.objetos.es_ranura_valida(it_org, dst) {
        eprintln!("mover {org} -> {dst}: ranura no valida para item {it_org}");
        let pk = refrescar(mundo, comp, &mut d.ses.jugador, &[org], t);
        c.enviar(&pk);
        return;
    }
    let j = &d.ses.jugador;
    if dst == 4 && rec.objetos.es_arma_dual(it_org) && !j.habilidades.iter().any(|h| h.id == 16) {
        let mut pk = vec![aviso("Requires Finesse skill to dual-wield weapons.")];
        pk.extend(refrescar(mundo, comp, &mut d.ses.jugador, &[org], t));
        c.enviar(&pk);
        return;
    }
    let cid = j.char_id;
    let estado_de = |j: &ao_juego::premiar::Jugador, r: i64| {
        j.mejoras
            .as_ref()
            .and_then(|m| m.get(&clave(r)))
            .and_then(Value::as_object)
            .cloned()
    };
    if es_equipo(dst)
        && !rec
            .objetos
            .puede_equipar(it_org, cid, estado_de(j, org).as_ref())
    {
        let mut pk = vec![aviso("Unable to equip the equipment.")];
        pk.extend(refrescar(mundo, comp, &mut d.ses.jugador, &[org], t));
        c.enviar(&pk);
        return;
    }
    // La otra mano, si no es compatible, vuelve a la mochila.
    let mut extra = vec![];
    for (mano, otra) in [(3, 4), (4, 3)] {
        let j = &d.ses.jugador;
        let Some(&it_otra) = j.bolsa.items.get(&otra) else {
            continue;
        };
        let compatibles = if mano == 3 {
            rec.objetos.compatibles_manos(it_org, it_otra)
        } else {
            rec.objetos.compatibles_manos(it_otra, it_org)
        };
        if dst != mano || org == otra || compatibles {
            continue;
        }
        let Some(libre) = ranura_libre(&j.bolsa.items) else {
            let mut pk = vec![aviso("Your backpack is full.")];
            pk.extend(refrescar(mundo, comp, &mut d.ses.jugador, &[org], t));
            c.enviar(&pk);
            return;
        };
        let j = &mut d.ses.jugador;
        let it = j.bolsa.items.shift_remove(&otra).unwrap();
        j.bolsa.items.insert(libre, it);
        let q = j
            .bolsa
            .cantidades
            .shift_remove(&ao_juego::botin::ClaveCantidad::Numero(otra))
            .unwrap_or(1);
        if q > 1 {
            j.bolsa
                .cantidades
                .insert(ao_juego::botin::ClaveCantidad::Numero(libre), q);
        }
        mover_inst(rec, j, otra, libre, t);
        extra.extend([otra, libre]);
    }
    let j = &mut d.ses.jugador;
    if j.bolsa.items.get(&dst) == Some(&0) {
        j.bolsa.items.shift_remove(&dst);
    }
    let equipo = es_equipo(org) || es_equipo(dst);
    let mut salida;
    if let Some(&it_dst) = j.bolsa.items.get(&dst) {
        // Intercambio entre casillas ocupadas.
        if !rec.objetos.es_ranura_valida(it_dst, org) {
            let pk = refrescar(mundo, comp, &mut d.ses.jugador, &[org, dst], t);
            c.enviar(&pk);
            return;
        }
        if es_equipo(org)
            && !rec
                .objetos
                .puede_equipar(it_dst, cid, estado_de(j, dst).as_ref())
        {
            let mut pk = vec![aviso("Unable to equip the equipment.")];
            pk.extend(refrescar(mundo, comp, &mut d.ses.jugador, &[org, dst], t));
            c.enviar(&pk);
            return;
        }
        j.bolsa.items.insert(org, it_dst);
        j.bolsa.items.insert(dst, it_org);
        let (co, cd) = (cant(j, org), cant(j, dst));
        j.bolsa
            .cantidades
            .insert(ao_juego::botin::ClaveCantidad::Numero(org), cd);
        j.bolsa
            .cantidades
            .insert(ao_juego::botin::ClaveCantidad::Numero(dst), co);
        mover_inst(rec, j, org, 0xFFFF, t);
        mover_inst(rec, j, dst, org, t);
        mover_inst(rec, j, 0xFFFF, dst, t);
        for r_eq in [dst, org] {
            if es_equipo(r_eq) {
                if let Some(&it_eq) = j.bolsa.items.get(&r_eq) {
                    let mej = j.mejoras.get_or_insert_with(Default::default);
                    let mut estado = mej.get(&clave(r_eq)).and_then(Value::as_object).cloned().unwrap_or_default();
                    if ao_juego::inventario::vincular_equipo(&rec.items.de(it_eq), it_eq, cid, &mut estado) {
                        mej.insert(clave(r_eq), Value::Object(estado));
                    }
                }
            }
        }
        mover_mascotas(j, &[(org, dst), (dst, org)]);
        // Las dos casillas en UN 0x001B (destino y origen), como el real.
        let mut uno = 0x001Bu16.to_le_bytes().to_vec();
        uno.extend(2u32.to_le_bytes());
        for r in [dst, org] {
            for p in refrescar(mundo, comp, &mut d.ses.jugador, &[r], t) {
                if p.len() > 6 && p[..2] == 0x001Bu16.to_le_bytes() {
                    uno.extend(&p[6..]);
                }
            }
        }
        salida = vec![ao_juego::inventario::acuse_movimiento(org), uno];
        if !extra.is_empty() {
            salida.extend(refrescar(mundo, comp, &mut d.ses.jugador, &extra, t));
        }
        eprintln!("swap ranuras {org} ({it_org}) <-> {dst} ({it_dst})");
    } else {
        let it = j.bolsa.items.shift_remove(&org).unwrap();
        j.bolsa.items.insert(dst, it);
        let q = j
            .bolsa
            .cantidades
            .shift_remove(&ao_juego::botin::ClaveCantidad::Numero(org))
            .unwrap_or(1);
        j.bolsa
            .cantidades
            .insert(ao_juego::botin::ClaveCantidad::Numero(dst), q);
        mover_inst(rec, j, org, dst, t);
        mover_mascotas(j, &[(org, dst)]);
        if es_equipo(dst) {
            let mej = j.mejoras.get_or_insert_with(Default::default);
            let mut estado = mej.get(&clave(dst)).and_then(Value::as_object).cloned().unwrap_or_default();
            if ao_juego::inventario::vincular_equipo(&rec.items.de(it), it, cid, &mut estado) {
                mej.insert(clave(dst), Value::Object(estado));
            }
        }
        salida = vec![ao_juego::inventario::acuse_movimiento(org)];
        let mut rs = vec![org, dst];
        rs.extend(&extra);
        salida.extend(refrescar(mundo, comp, &mut d.ses.jugador, &rs, t));
        eprintln!(
            "item {it}: ranura {org} -> {dst}{}",
            if equipo { "  (cambia el equipo)" } else { "" }
        );
    }
    if equipo {
        tras_cambio_de_equipo(mundo, comp, id, d, &mut salida, t);
    }
    if toca_amplify {
        if let Some(amp) = &mut d.ses.sistemas.amplify {
            amp.refrescar(&mut d.ses.jugador, &rec.catalogo, &rec.tablas);
            if let Ok(p_amp) = amp.paquete() {
                salida.push(p_amp);
            }
            if let Ok(st) = ef::stats_ses(
                &rec.fuentes,
                &rec.catalogo,
                &rec.estadisticas,
                &mut d.ses.jugador,
                t,
            ) {
                salida.push(st);
            }
        }
    }
    c.enviar(&salida);
    drop(guard);
    guardar_bolsa(est, d);
}
"""
    t = t[:idx_start] + nuevo_mover_objeto + t[idx_end:]
    p_mundo.write_text(t, encoding='utf-8')
    print("mundo.rs: actualizado con vinculaciones exactas")

if __name__ == '__main__':
    aplicar()
