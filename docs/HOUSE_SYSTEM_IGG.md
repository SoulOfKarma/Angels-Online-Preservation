# Estado técnico del House System IGG

> Núcleo de casa, entrada, edición y persistencia: implementado. Las fórmulas
> de entrenamiento de pets, Ball Tickets, mercenarios, martillos y Egg Machine
> siguen pendientes de capturas originales; no se consideran completas.

## 1. Visión General del Sistema
El **House System** usa el espacio paralelo **Stage 500** (`map\default.mpc`; el cliente incluye `house001..020` y `house031..050`). El núcleo permite poseer, exhibir, visitar y decorar una casa. Los subsistemas avanzados se documentan aquí como objetivos de reconstrucción cuando todavía no existe evidencia suficiente.

---

## 2. Mapas y Escenarios
- **Stage 500 (Interior de la Casa)**: Mapa instanciado para cada jugador. Carga el escenario base `map\default.mpc` o el escenario personalizado de categoría 10 (`屋外景觀` / Escena Exterior) indicado en el opcode `0x000C` a través de `house_table_id`.
- **Mapas de Exhibición Exterior**:
  - `41`: Angel Lyceum
  - `3`: Palm Base
  - `26`: Iron Castle
  - `29`: Aurora City
  - `38`: Dark City
  - `88`: Breeze Woods

---

## 3. Escrituras (Deeds), Tamaños y Capacidad
Cada casa posee un nivel de tamaño (`0..6`) determinado por la escritura (`房屋`) en posesión o equipada:

| Item ID | Nombre de Escritura | Nivel Tamaño | Modelo Exterior | Capacidad de Muebles |
|---|---|---|---|---|
| **10115** | Cottage | 0 | 7807 | 35 |
| **10116** | Delicate House | 1 | 7806 | 60 |
| **10117** | Romantic Villa | 2 | 7805 | 100 |
| **17934** | Luxurious Villa | 3 | 7848 | 120 |
| **17935** | Large Luxurious Villa | 4 | 7849 | 140 |
| **17936** | Large House | 5 | 7850 | 160 |
| **17937** | Super Big House | 6 | 7851 | 180 |
| **20076** | Cottage (Alt) | 0 | 7807 | 35 |

---

## 4. Niveles de Magia y Umbrales
El nivel de la casa (`1..15`) se calcula según la suma total de puntos de decoración (`擺設分數`) de todos los muebles colocados dentro de la casa:

| Nivel | Puntos Mínimos de Magia | Ranuras Mascotas | Ranuras Monstruos |
|---|---|---|---|
| **1** | 0 | 0 | 0 |
| **2** | 500 | 0 | 0 |
| **3** | 900 | 1 | 0 |
| **4** | 1.500 | 1 | 0 |
| **5** | 2.700 | 2 | 0 |
| **6** | 4.500 | 2 | 1 |
| **7** | 9.000 | 3 | 1 |
| **8** | 15.000 | 3 | 1 |
| **9** | 27.000 | 4 | 1 |
| **10** | 40.000 | 4 | 2 |
| **11** | 48.000 | 4 | 2 |
| **12** | 56.000 | 5 | 2 |
| **13** | 64.000 | 5 | 3 |
| **14** | 72.000 | 6 | 3 |
| **15** | 84.000 | 6 | 3 |

---

## 5. Protocolo de Red: Paquetes y Estructuras

### 5.1. Paquetes S2C (Servidor a Cliente)
- **`S2C 0x000C` (`pkt_cambiar_mapa_house`)**:
  - Longitud: 30 bytes
  - Estructura: `<HIIIIIIIB`
  - Campos: `opcode=0x000C, stage_id=500, 0, 0, 0, 0, 0, house_table_id:u32 (+24), house_size_level:u8 (+28)`
- **`S2C 0x0140` (`pkt_outdoor_house`)**:
  - Longitud: 65 bytes
  - Estructura: `<HIIii16sBBIHHBB17sBB`
  - Spawnea el objeto exterior interactivo de la casa en el mapa abierto.
- **`S2C 0x0142` (`pkt_open_close_state`)**:
  - Longitud: 3 bytes (`<HB`)
  - Indica si la casa exterior está abierta (1) o cerrada (0).
- **`S2C 0x0143` (`pkt_indoor_furniture_obj`)**:
  - Spawnea un mueble individual en el interior de la casa.
- **`S2C 0x013E` (`pkt_enter_furnish_mode` / `pkt_leave_furnish_mode`)**:
  - Activa o desactiva la interfaz de decoración del cliente y sincroniza la lista de muebles editables.
- **`S2C 0x013F` (`pkt_visit_furniture_sync`)**:
  - Sincroniza al visitante todos los muebles colocados y sus estados de rotación y posición.
- **`S2C 0x0144` (`pkt_pet_slot_wnd`)**:
  - Estructura: `<HBBI`
  - Abre la ventana de incubación/cuidados de mascotas según el nivel de la casa.
- **`S2C 0x0145` (`pkt_mobgen_slot_wnd`)**:
  - Estructura: `<HBB`
  - Abre la incubadora de huevos de monstruos.
- **`S2C 0x0146` (`pkt_open_cast_vote`)**:
  - Abre el cuadro para votar y dejar una nota al propietario.
- **`S2C 0x0147` (`pkt_view_vote_notes`)**:
  - Muestra las notas del libro de visitas de forma paginada.
- **`S2C 0x0148` (`pkt_request_password`)**:
  - Solicita al visitante la clave para ingresar a una casa privada protegida.
- **`S2C 0x0149` (`pkt_house_info`)**:
  - Longitud: 38 bytes
  - Estructura: `<HIIIIHHIIIBHB`
  - Campos: nivel, magia actual, magia siguiente, magia previa, bonus %, limpieza, votos totales, votos hoy, visitas totales, votos restantes del jugador hoy, ranking mundial, flag de fiesta de baile (disco ball).
- **`S2C 0x014A` (`pkt_house_name`)**:
  - `<H16s` actualiza el cartel con el nombre de la casa. El tamaño está confirmado por `sub_5EFE80` del cliente IGG, que copia exactamente 16 bytes desde `packet+2`.
- **`S2C 0x014B` (`pkt_hitparade_data`)**:
  - Envía la tabla de clasificación de popularidad, visitas, limpieza y magia.
- **`S2C 0x014C` (`pkt_billboard_data`)**:
  - Envía el ranking de los 10 mejores hogares.

### 5.2. Paquetes C2S (Cliente a Servidor)
- **`0x0136` (`furnishhouse`)**: Entra al modo de decoración; cuerpo `u32` con el ID de la escritura de casa. Confirmado en captura Global del 2026-10-16.
- **`0x0137` (`registryhouse`)**: Abre la casa en la posición actual del jugador en mapas autorizados.
- **`0x0138` (`leavefurnish` / `leavehouse`)**: Sale del editor o del interior según el estado actual; cuerpo vacío. Confirmado en captura Global del 2026-10-16.
- **`0x0139` (`closehouse`)**: Retira la casa exterior del mapa; cuerpo vacío. Confirmado en captura Global del 2026-10-16.
- **`0x013A` (`tryentryhouse`)**: Intentar ingresar a una casa (verificando contraseña si existe).
- **`0x013B` (`savefurniture`)**: Guarda la nueva distribución. La captura Global usa cabecera de 37 bytes (`u32 count` + bloque nombre/opciones de 33 bytes) seguida de registros de 24 bytes; por compatibilidad también se acepta la variante IGG de cabecera de 21 bytes.
- **`0x013C` (`checkhouseoption`)**: Actualiza las opciones y permisos de la casa.
- **`0x013D` (`furniturerecycle`)**: Reciclaje de 5 muebles en la Máquina de Huevos (11184).
- **`0x013E` (`sethousepetradio`)**: Guarda la configuración de cuidados de mascotas.
- **`0x013F` (`trycastvote`)**: Emite un voto y un mensaje en el libro de visitas.
- **`0x0140` (`votenotechangepage`)**: Cambia de página en el visor de mensajes.
- **`0x0141` / `0x0142`**: Teletransporte directo a casas de otros jugadores desde mensajes o ranking.
- **`0x002F` (`cmd=41` HitParade, `cmd=42` Billboard)**: Petición de tablas de ranking.

---

## 6. Condiciones y Acciones de Eventos (`eventdef.xml`)

### Condiciones Integradas:
- **`58 HOUSE_IS_OWNER`**: Comprueba si el personaje actual es el dueño de la casa.
- **`59 HOUSE_LEVEL(cmp, lv)`**: Compara el nivel de decoración de la casa.
- **`60 DISCO_PARTY(active)`**: Comprueba si hay una fiesta de baile activa.
- **`61 COMPOUND_BUFF()`**: Determina si el jugador es elegible para la bendición diaria de Maid Eilian.
- **`62 HOUSE_HAVE_VOTE`**: Comprueba si el jugador aún tiene votos disponibles hoy para esta casa.
- **`63 HOUSE_NEATNESS(cmp, val)`**: Compara el valor de limpieza actual.
- **`64 HOUSE_OWNER_AT_HOME`**: Comprueba si el dueño se encuentra actualmente dentro del hogar.
- **`65 HOUSE_OWNER_PARTNER`**: Comprueba si el visitante es el cónyuge / pareja del dueño.
- **`70 HOUSE_SIZE(cmp, sz)`**: Compara el tamaño de la casa.

### Acciones Integradas:
- **`89 LEAVE_HOUSE`**: Teletransporta de regreso al punto y mapa exterior desde donde se ingresó.
- **`90 SET_BUFF_TIME`**: Otorga la bendición diaria de producción y experiencia de la sirvienta.
- **`91 OPEN_HOUSE_PET`**: Abre la ventana de slots de mascotas (`slots 477..486`).
- **`92 OPEN_HOUSE_MOBGEN`**: Abre la ventana de slots de incubación de monstruos (`slots 487..496`).
- **`93 CLEAR_HOUSE`**: Consume jabón o polvo limpiador y restaura la limpieza de la casa.
- **`94 OPEN_HOUSE_CASTVOTE`**: Abre la ventana de votación.
- **`95 HOUSE_VIEW_VOTENOTE`**: Abre el libro de visitas.
- **`96 HITPARADE_HOUSE`**: Abre la tabla de clasificación mundial.

---

## 7. Objetos Consumibles y Reciclaje

Estado de seguridad: los jabones tienen efecto persistente. Ball Tickets,
Furniture Hammers, Party Candy y Furniture Egg Machine se reconocen, pero no
se consumen mientras sus duraciones, bonos y tablas originales sigan sin
verificar. La implementación anterior usaba valores aleatorios y podía gastar
objetos sin aplicar un resultado real.
1. **Jabones y Polvos Limpiadores**:
   - `10626`: Soap Powder (+100 Limpieza)
   - `10603`: Liquid Soap (+200 Limpieza)
   - `15163`: Super Liquid Soap (+500 Limpieza)
   - `20077`: Magic Soap (+1000 Limpieza, limpieza máxima)
2. **Tickets de Fiesta (Ball Tickets)**:
   - `9953`, `20078`, `15235`, `15236`, `16598`, `28867`: Inician una fiesta de baile en la casa por 1 hora, otorgando bonus de experiencia a los presentes.
3. **Martillos Mágicos (11114..11121)**:
   - Recalculan y aumentan los puntos mágicos de muebles seleccionados en la mochila.
4. **Caramelos de Fiesta (Party Candy 10569..10580)**:
   - Dulces consumibles durante los bailes de casa.
5. **Máquina de Huevos de Muebles (11184)**:
   - Permite reciclar 5 muebles colocados en la interfaz para obtener un nuevo mueble aleatorio con puntuación basada en los reciclados.

---

## 8. Persistencia Atómica
Los datos se guardan en `personajes.datos -> casa`. Al confirmar decoración,
casa e inventario se escriben dentro de una única transacción SQLite; ante un
fallo también se revierte el estado en memoria:
- `cuentas.guardar_casa(usuario, char_id, casa)`
- `cuentas.guardar_casa_e_inventario(usuario, char_id, casa, inventario, ...)`
- `cuentas.guardar_sistemas(usuario, char_id, p)`
- `cuentas.personaje_de(...)` carga el contenedor completo de `CasaData`.

