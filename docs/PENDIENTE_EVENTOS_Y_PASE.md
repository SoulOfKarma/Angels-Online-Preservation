# Pendiente: ventana de eventos, Angel Pass y Pet Amplify

Plan para la próxima sesión (escrito el 21/10/2026). Todo esto existe en el
cliente y el servidor no lo trata: las ventanas se abren, pero ningún botón hace
nada. No hay capturas del oficial, así que casi todo sale con **REA** y los
datos de `extracted_paks/`.

## Método (el mismo que con la fusión y los logros)

1. **Script Lua de la ventana** (`extracted_paks/*/script/<nombre>.l`). Volcar
   las funciones con el lector de bytecode Lua 5.1 que se usó para `fuse.l`
   (estaba en el scratchpad como `luadump.py`; si ya no está, rehacerlo: ~120
   líneas, lee constantes e instrucciones de cada función). Así se ve a qué
   `game.xxx` llama cada botón y con qué argumentos.
2. **La función nativa de cada `game.xxx`**: buscar la cadena con
   `mcp__rea__search_strings`, hacer `xrefs` de la cadena para llegar a la tabla
   de registro Lua (pares `[ptr nombre][ptr función]`), leer los bytes y
   descompilar la función. Ahí sale el **C2S** (buscar `FUN_004c0ec0(n)` +
   `*local = opcode`) o el `FUN_00614da0(accion, valor)`, que es el
   **c2s 0x0016 [accion][u32]**.
3. **La respuesta**: buscar quién escribe los campos que lee la ventana. Muchas
   respuestas van por el **0x001D [u32 entidad][u8 n] n x [u8 código][u32 a][u32 b]**:
   el código es `(hueco - 0x4408) / 16` en la tabla de `FUN_005fbdd0`. Para
   encontrarlo: `xrefs` de la función que procesa la respuesta → los bytes
   anteriores llevan `add edx, <hueco>`.
4. Tabla de S2C conocida: `docs/tabla_s2c.md`.

## 1. Online Bonus (el más fácil, empezar por aquí)

- Datos: `setting/onlinegift.xml`, 12 filas `<在線獎勵 編號 在線分鐘 道具1 數量1 ...>`.
  En la captura: 0, 10, 20, 30, 40 y 60 minutos (Might Angel's Aura, pergaminos...).
- Script: `onlinereward.l`.
- Falta: el C2S del botón "Receive" y el S2C que le dice al cliente los minutos
  acumulados y qué filas ya se reclamaron (el `!` rojo del botón).
- Servidor: llevar los minutos conectados del día por personaje (ya hay un tick
  de tiempo conectado en `casas.avanzar_tiempo_conectado`), guardar lo reclamado
  y reiniciar a medianoche.

## 2. Exchange

- Datos: `setting/exchange.xml` (22.700 recetas: `群組`, `獎賞N`, `材料N`) y
  `setting/eng/exchangegroup.xml` (las 8 tiendas de la ventana: Winter's Hymn
  Treasures, Winter Holiday PD, Thanksgiving Feast Event, Royal Attendant PD,
  Ride and Robots, Enhanced Pestle and Ride, Runestone, Attribute Lucky Hammer;
  cada una con su `群組`).
- Script: `exchange.l`.
- El servidor YA usa `exchange.xml` en algunos NPC (`app.py` ~904,
  `dialogos.py` ~3153 "WND_EXCHANGE"): reaprovechar ese canje.
- Falta: qué manda el botón "Go to" (probablemente abre la ventana de canje del
  grupo) y el C2S de canjear.

## 3. Login Bonus

- Script: `loginreward.l`. No hay xml con las recompensas a la vista: buscar de
  dónde saca el cliente las filas (2/5/7/14/28 días en la captura: cofres,
  pergaminos...). Puede ser otro xml de `setting/` o venir del servidor.
- Contador de días: ya existe `p.logros_dias` (días distintos conectado, se
  apunta al entrar; ver `app._logros_datos`). Reutilizarlo.
- "10 months Total Log In Reward": revisar si es acumulado o por temporada.

## 4. Angel Pass (battle pass)

- Datos: `setting/battlepass.xml` (temporada: 開始時間 / 結束時間 / 任務結束時間,
  開通道具ID 79892 = abrir el pase de pago, 升級道具ID 79893 = comprar nivel,
  獎勵群組ID, grupos de tareas diarias), `battlepassprize.xml` (250 filas:
  nivel, experiencia, premio gratis y de pago) y `battlepasstask.xml` (95
  tareas: 規則 "打怪類" matar monstruos..., experiencia, parámetros).
- Script: `battlepass.l`.
- La temporada del xml acabó en 2025: por eso la ventana pone "Null" y 0/0.
  Decidir: ignorar las fechas o definir una temporada propia en el servidor.
- Falta: el S2C con nivel, experiencia y premios reclamados; los C2S de
  "Claim Reward", "Purchase Premium Pass" y "Purchase Lv".
- Las tareas se pueden contar con los mismos ganchos que los logros
  (`app._logros_contar`, muertes de monstruos en `_logros_muerte`).

## 5. Pet Amplify

- No hay xml propio. El "Pet Amplify Hammer" está en `item5..9.xml`; textos en
  `msg.xml` / `string.xml` (buscar "Amplify").
- Ventana: 8 páginas de 4 huecos que se desbloquean con 5 martillos cada uno,
  bonos a Max HP/MP, ATK, DEF, Spell ATK/DEF, Rigor y Agilidad con su "Current
  Max", pestaña "Special Bonus".
- Todo con REA: buscar las cadenas de la ventana (`Pet Amplify`,
  `Unlock Slot`...) y seguir hasta el C2S y el formato de los datos.
- Los bonos deberían sumarse donde se calculan las stats de la mascota
  (`mascotas.bonos_de_ficha` / `hp_eff`).

## 6. Event News (local)

- Lo pidió el usuario: algo local, sin servidor externo.
- Probablemente el cliente baja la página por HTTP; el servidor ya levanta un
  HTTP de noticias para el START.EXE (`cliente_local`, puerto 8280). Ver con REA
  qué URL o qué paquete usa la pestaña y servir ahí una página propia (novedades
  del servidor, eventos activos).

## Otros pendientes sueltos

- **Mercenario de la casa**: ahora sale el más fuerte con nivel <= el del
  jugador (`house_services.mercenary_for`). La ayuda del juego dice que el nivel
  de la CASA lo hace más fuerte ("Mercenary: Level 1/2..."). Falta decidir cómo
  combinarlo.
- **Logros sin vigilar (~1.100)**: mazmorras contadas, Holy Battle, puestos,
  minijuegos, adivinación, matrimonio, amigos, Final Tower, Angel Arena, equipo
  de mascota. NPC觸發 (297) no se puede: los scripts de mapa no usan la acción de
  dar logros.
- **Fly Book / Summon Book**: sin captura de qué manda el cliente al pinchar el
  retrato; se acepta char_id o entidad. Probar en el juego y mirar el log.
- **Títulos nuevos**: solo llegan con el 0x0002 (al entrar o cambiar de mapa);
  por REA no hay paquete para añadir uno suelto.
