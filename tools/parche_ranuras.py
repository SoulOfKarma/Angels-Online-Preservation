"""Parches y utilidades para el hito de ranuras especiales y barra 0x0044."""
import pathlib

def aplicar():
    # 1. guardados.rs: pub fn barra
    p_guardados = pathlib.Path(r'rust/ao-juego/src/guardados.rs')
    t_guardados = p_guardados.read_bytes()
    marker = b'pub fn quests(p: &mut Map<String, Value>, quests: &[(i64, i64)]) {\r\n    let l = quests.iter().map(|(q, s)| Value::Array(vec![(*q).into(), (*s).into()])).collect();\r\n    p.insert("quests".into(), Value::Array(l));\r\n}'
    barra_fn = b'\r\n\r\n/// `guardar_barra` (el `if not usuario` lo mira quien llama).\r\npub fn barra(p: &mut Map<String, Value>, barra: &[Value]) {\r\n    p.insert("barra".into(), Value::Array(barra.to_vec()));\r\n}'
    if marker in t_guardados and b'pub fn barra' not in t_guardados:
        t_guardados = t_guardados.replace(marker, marker + barra_fn)
        p_guardados.write_bytes(t_guardados)
        print('guardados.rs: barra anadida')
    else:
        print('guardados.rs: ya presente o marker no coincide')

    # 2. mascotas.rs: error_equipar_mascota, RANURA_EQUIPO_MASCOTA, ESTRELLAS_MINIMAS_EQUIPAR
    p_mascotas = pathlib.Path(r'rust/ao-juego/src/mascotas.rs')
    t_mascotas = p_mascotas.read_bytes()
    if b'pub const RANURA_EQUIPO_MASCOTA' not in t_mascotas:
        pet_consts = (
            b'\r\n\r\npub const RANURA_EQUIPO_MASCOTA: i64 = 558;\r\n'
            b'pub const ESTRELLAS_MINIMAS_EQUIPAR: i64 = 50;\r\n\r\n'
            b'pub fn error_equipar_mascota(ficha: Option<&Ficha>) -> Option<(&\'static str, i64)> {\r\n'
            b'    let Some(f) = ficha else {\r\n'
            b'        return Some(("Pet data is unavailable.", 0));\r\n'
            b'    };\r\n'
            b'    if f.get("fuera").is_some_and(py::verdadero) {\r\n'
            b'        return Some(("Please recall this pet before equipping it.", 0));\r\n'
            b'    }\r\n'
            b'    let hp = f.get("hp").and_then(py::entero).unwrap_or(0);\r\n'
            b'    if hp <= 0 {\r\n'
            b'        return Some(("The pet is dead.", 0));\r\n'
            b'    }\r\n'
            b'    let estrellas = f.get("estrellas").and_then(py::entero).unwrap_or(0);\r\n'
            b'    if estrellas < ESTRELLAS_MINIMAS_EQUIPAR {\r\n'
            b'        return Some(("Only pets with 5 stars or higher can be equipped.", 0));\r\n'
            b'    }\r\n'
            b'    None\r\n'
            b'}\r\n'
        )
        t_mascotas += pet_consts
        p_mascotas.write_bytes(t_mascotas)
        print('mascotas.rs: error_equipar_mascota anadido')

    # 3. casas.rs: ranuras_mascotas_validas, ranuras_mobgen_validas
    p_casas = pathlib.Path(r'rust/ao-juego/src/casas.rs')
    t_casas = p_casas.read_bytes()
    if b'pub fn ranuras_mascotas_validas' not in t_casas:
        casas_fn = (
            b'\r\npub fn ranuras_mascotas_validas(nivel: i64) -> i64 {\r\n'
            b'    if nivel >= 14 { 6 }\r\n'
            b'    else if nivel >= 12 { 5 }\r\n'
            b'    else if nivel >= 9 { 4 }\r\n'
            b'    else if nivel >= 7 { 3 }\r\n'
            b'    else if nivel >= 4 { 2 }\r\n'
            b'    else { 1 }\r\n'
            b'}\r\n\r\n'
            b'pub fn ranuras_mobgen_validas(nivel: i64) -> i64 {\r\n'
            b'    if nivel >= 13 { 3 }\r\n'
            b'    else if nivel >= 8 { 2 }\r\n'
            b'    else { 1 }\r\n'
            b'}\r\n'
        )
        t_casas += casas_fn
        p_casas.write_bytes(t_casas)
        print('casas.rs: ranuras_mascotas_validas y ranuras_mobgen_validas anadidos')

if __name__ == '__main__':
    aplicar()

