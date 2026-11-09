import pathlib

# 1. TRASPASO_CODEX_PORT_RUST.md (CRLF)
p_traspaso = pathlib.Path(r'docs/TRASPASO_CODEX_PORT_RUST.md')
t_traspaso = p_traspaso.read_bytes().decode('utf-8')

nueva_seccion = '''

## ESTADO AL PARAR (31/10/2026 - Antigravity)

### Hito completado: Movimiento y equipamiento de ranuras especiales (0x0012) y barra (0x0044)

1. **Ranura 558 (Pet Equipment):**
   - Validacion estricta con `ao_juego::mascotas::error_equipar_mascota`: exige que la mascota tenga >= 50 estrellas (5.0 estrellas), este viva (`hp > 0`) y no este invocada fuera (`!fuera`). En caso contrario, rechaza con su `aviso` especifico ("Only pets with 5 stars or higher can be equipped", "Please recall this pet before equipping it", "The pet is dead") y refresca casillas.
   - Vinculacion automatica al equipar mediante `ao_juego::inventario::vincular_equipo`.
   - Llamada a `tras_cambio_de_equipo`, recalculando `bonos_de_equipo` -> `verdes_pet(558)` y emitiendo `0x0042` y apariencia.

2. **Ranura 376 (House Deed):**
   - Arrastrar deed (escritura de casa) a 376 ejecuta el cambio de escritura / ampliacion de casa (`mover_deed_a_376`).
   - Comprobaciones exactas a Python: si ya es del mismo tamano, si el jugador esta dentro de la casa (stage 500), o si los muebles colocados exceden la capacidad de la casa destino.
   - Impide vaciar directamente la casilla 376 arrastrandola a vacio (la casa nunca se queda sin escritura).
   - Arrastrar deed a las casillas 377..496 emite aviso `"House deeds are not furniture: use it (or drop it on the house slot) to change the size of your house."`.

3. **Ranuras 377..=476 (Bolsa de Muebles):**
   - Proteccion contra extraccion a mochila regular si el mueble esta registrado o vinculado (`protegido_mueble`).
   - Arrastrar mueble de mochila regular (<377) a bolsa de muebles (377..476) registra el mueble en la primera casilla libre disponible, consume 1 de cantidad, lo vincula (`vincular_equipo`) y emite `"Decoration registered in your Furniture bag. It can now be placed and cannot be sold."`.
   - Movimiento e intercambio libre dentro del rango 377..=476.

4. **Ranuras 477..=496 (House Pets y MobGen):**
   - Validaciones de casa: exige estar en stage 500, ser el dueno de la casa y no estar en modo decoracion.
   - Ranuras 477..486: exige mascota y `dst < 477 + ranuras_mascotas_validas(nivel)`.
   - Ranuras 487..496: exige huevo de monstruo y `dst < 487 + ranuras_mobgen_validas(nivel)`.
   - Retirada a mochila regular permitida.

5. **Ranuras 559..=598 (Pet Amplify):**
   - Comprueba que la casilla este desbloqueada (`dst - 559 < abiertas`); si no, emite `"This slot is locked!"` con tipo 7.
   - Comprueba que el item sea una mascota; si no, emite `"Please insert a pet!"` con tipo 7.
   - Tras mover o retirar mascota de Amplify, invoca `amplify.refrescar(&mut d.ses.jugador, &rec.catalogo, &rec.tablas)`, actualiza `stats_amplify`, emite el paquete `0x0179` y `stats_sesion` (`0x0042`), y persiste inventario.

6. **Opcode 0x0044 (Barra de accesos rapidos / Hotbar):**
   - Despacho en `mundo.rs`: asigna tecla rapida `[slot, tipo, mid]`. Si `mid == 0`, limpia la casilla con `0`.
   - Persistencia en base de datos SQLite mediante `guardados::actualizar_personaje` y `guardados::barra`.

### Validacion de cierre completada

- **Base integral 62: 62/62 comparadores OK y TODO IDENTICO, exit 0** con `powershell -ExecutionPolicy Bypass -File tools/validar_todo.ps1 -Rapido`.
- **Suite TCP dual `tools/probar_ranuras_especiales.py`:** 19/19 pasos identicos en Python y Rust comparando paquetes y estado en base de datos (`Ranuras especiales TCP: bytes y estados comparados IDENTICOS`).
- **Cargo clippy estricto:** `cargo clippy --manifest-path rust/Cargo.toml --release --workspace --all-targets -- -D warnings` finalizado con 0 advertencias.
- **Cargo test:** `cargo test --manifest-path rust/Cargo.toml --release --workspace` pasando los 17 tests unitarios del workspace con 0 fallos.

### Proximo hito

Intercambio directo entre jugadores (Trade / Exchange: opcodes `0x0019`, `0x001A`, `0x001B`, etc.) con confirmacion dual atomica, o servicios de misiones y tiendas restantes.

Sin commit/push, sin escrituras en `data/cuentas.db` real o cliente.
'''

t_traspaso_updated = t_traspaso + nueva_seccion.replace('\r\n', '\n').replace('\n', '\r\n')
p_traspaso.write_bytes(t_traspaso_updated.encode('utf-8'))
print('TRASPASO_CODEX_PORT_RUST.md actualizado con CRLF')

# 2. PORT_RUST.md (LF)
p_port = pathlib.Path(r'docs/PORT_RUST.md')
t_port = p_port.read_bytes().decode('utf-8')
nota_port = '''

### Hito completado: Ranuras especiales (0x0012) y barra (0x0044) (31/10/2026)
- Desbloqueo completo de ranuras especiales en `mover_objeto` (0x0012): ranura 558 (pet equipada con validacion de 5 estrellas, vida y no invocada; bono 1/5 de verdes), ranura 376 (house deeds con cambio de casa o rechazo si esta dentro o exceden muebles), ranuras 377..476 (bolsa de muebles protegida, registro desde mochila y swaps internos), ranuras 477..496 (house pets y mobgen segun nivel de casa), y ranuras 559..598 (pet amplify con validacion de casillas abiertas, emision de 0x0179 y 0x0042 con stats_amplify).
- Opcode 0x0044: asignacion y borrado de teclas rapidas en la barra de accesos (F1..F8, 1..8) y persistencia en SQLite (`guardados::barra`).
- Validacion: 62/62 comparadores rapidos identicos, 19 pasos TCP duales identicos en `tools/probar_ranuras_especiales.py`, clippy y tests del workspace con 0 advertencias y 0 fallos.
'''
t_port_updated = (t_port + nota_port).replace('\r\n', '\n')
p_port.write_bytes(t_port_updated.encode('utf-8'))
print('PORT_RUST.md actualizado con LF')

