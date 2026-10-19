# Resumen de Estado y Tareas Pendientes: Ligas, Granja, Territorios y Totem War

**Fecha:** 19 de Octubre de 2026  
**Proyecto:** Angels Online Server Emulator (Python 3.10)  
**Destinatario:** Claude / Antigravity / Equipo de desarrollo  
**Propósito:** Traspaso técnico del estado actual de los sistemas de Liga (Guild), Granja (Farm Stage 501), Territorios Privados, NPCs asociados y lo que queda pendiente para completar el ciclo de Totem War e Instancias.

---

## 1. Arquitectura y Archivos Clave

| Módulo / Archivo | Responsabilidad Principal |
| :--- | :--- |
| `server/app.py` | Enrutamiento de paquetes C2S/S2C, ciclo de vida de sesiones, chat (prefijos `@`, `#`), comandos GM, y dispatchers de granja (`0x014C`..`0x014F`) y almacén (`0x0059`). |
| `server/gremios.py` | Lógica de negocio de ligas: creación, rangos, permisos, umbrales de reputación (`level.xml`), materiales de contribución (`guild_contrib.xml`), almacén y paquetes S2C (`0x0055`, `0x0056`, `0x0058`). |
| `server/granja_liga.py` | Aislamiento de instancia para la granja (stage 501) por `guild_id`, ciclos de cultivo (siembra, riego, abono, cosecha), validación de nivel 6 y guardado de coordenadas de retorno. |
| `server/eventos.py` | Intérprete de eventos y condiciones de scripts NPC (condiciones 28, 76, 82 y acciones 22, 24, 34, 37, 50). |
| `server/eventos_mundo.py` | Implementación de las acciones del mundo (`GOTO_GUILD_REGION`, `OPEN_BANK`, cambios a mapas paralelos). |
| `server/cuentas.py` | Persistencia SQLite (`data/cuentas.db`): tablas `gremios`, `gremio_miembros`, `gremio_almacen`, `gremio_territorios`, `liga_granja_cultivos`, `liga_farm_retorno`. |
| `server/gm.py` | Parser de comandos GM y ejecución de operaciones administrativas (`/level`, `/guildlevel`, `/plant`, `/farm`, etc.). |

---

## 2. Lo que YA está Implementado y Verificado (100% Funcional)

### A. Sistema de Ligas (Guild / League)
1. **Creación en las 4 Ciudades**:
   * Los 4 `League Clerk` (NPCs) enrutan al árbol de diálogo `5776`.
   * Validación estricta: Nivel 25+, Rango de personaje 3+, 60.000 de oro.
   * Envía acción 20 (`0x001D`) para abrir la ventana de creación de liga y cierra diálogo limpiamente.
2. **Sincronización en Login**:
   * Al conectar el personaje (`opcode 0x0002` sin `entity_id`), se disparan de inmediato `gremios.al_entrar_jugador(ses, mundos)` y `equipos.al_cambiar_de_mapa(ses)`.
   * Entrega inmediata de paquetes `0x0055` (`paquete_datos_gremio`), `0x0058` (miembros) y `0x0056` (cartel/anuncio).
3. **Apariencia Visual (`0x0001` en `presencia.py`)**:
   * Byte 113: ID de logotipo de la liga.
   * Byte 114: Nombre ASCIIZ de la liga flotando sobre la cabeza del personaje.
4. **Almacén / Banco de Liga (`0x0059`)**:
   * Árbol de diálogo con acción `OPEN_BANK 1` abre el almacén del gremio; `OPEN_BANK 0` abre el banco personal (`0x004E`).
   * Permisos independientes: `GUILD_PERM_WITHDRAW_ITEM = 1`, `GUILD_PERM_WITHDRAW_MONEY = 2`.
   * Transacciones atómicas en SQLite (`cuentas.db_mover_banco_gremio`), preservando mejoras de equipo y metadatos de mascotas.
5. **Rangos y Reputación**:
   * Umbrales leídos de `update26/setting/level.xml` (campo `社團`):
     `0 / 10.000 / 25.000 / 67.500 / 140.000 / 300.500 / 600.000 / 1.500.000 / 3.750.000 / 9.375.000` (Niveles 1 a 10).
   * Contribución de materiales mediante C2S `0x004B` usando `setting/eng/guild_contrib.xml`.
6. **Canales de Chat**:
   * Prefijos de texto enrutados directamente:
     * Liga (Canal 5): `@mensaje`, `/g `, `/guild `, `/l `, `/league `.
     * Grupo / Team (Canal 4): `#mensaje`, `/t `, `/team `, `/p `, `/party `.
     * Comercio (Canal 10): `$ ` o `/trade ` (consume Broadcasting 2002).

### B. Granja de Liga (Guild Farm - Stage 501)
1. **Acceso e Instanciación**:
   * Petición nativa del cliente: C2S `0x014C` (botón *"Visit the Farm"* de la UI de liga) y comando `/farm enter`.
   * Requisito verificado por servidor: `nivel_gremio >= 6`.
   * Instancia privada por clan: cada liga tiene su propia sala `(501, 'league', guild_id)`.
   * Entrada en TAG 255 de `farm.mpc`. Guardado automático del mapa y coordenadas previas en `liga_farm_retorno`.
   * Salida mediante el tornado original en coordenadas `(97, 8)` (objeto 60001), devolviendo al personaje al punto exacto de donde partió.
2. **Ciclo de Cultivos**:
   * Siembra: `farm.plantar(ses, plot_id, crop_id)` o comando `/plant <crop_id> [plot_id 1..200]`.
   * Opcodes C2S implementados:
     * `0x014D`: Regar (`regar`) -> incrementa contador de agua y actualiza estado visual.
     * `0x014E`: Abonar (`abonar`) -> incrementa contador de fertilizante.
     * `0x014F`: Cosechar (`cosechar`) -> valida madurez, entrega cosechas según `crops.xml`, otorga EXP de personaje (`_cb.exp_paquete`) y EXP de habilidad (`_cb.skill_exp_paquete`), y limpia la parcela.
   * Población automática de cultivos al cargar el stage 501.

### C. Territorios y NPCs de Totem War
1. **Condiciones y Acciones de Diálogos**:
   * Condición 28 (`HAVE_GUILD_REGION`): Comprueba si la liga del jugador posee algún territorio.
   * Condición 76 (`SPEC_MAP_OWN_GUILD(tw_stage)`): Comprueba posesión de un campo específico (ej. 205 para Thorn Wasteland).
   * Condición 82 (`GUILD_MEMBER_TIME`): Exige 3 días de antigüedad (259.200 segundos) para reclamar premios.
   * Acción 50 (`GOTO_GUILD_REGION`): Teletransporta al Área I privada (stage 50).
   * Acción 37 (`CHANGE_PARA_MAP`): Mueve al jugador a la versión de territorio privado validando posesión.
2. **NPCs Operativos**:
   * **Heaven General** (árbol 5920 en las 4 ciudades):
     * Tienda 71 de insignias de clan (items 3735..3748).
     * Entrega diaria de cajas de combate o producción (3776..3783, 9255..9258, 13409..13412) + token oculto 3754.
     * Teletransporte a territorio del clan (`GOTO_GUILD_REGION`).
   * **Terra Keeper** (árbol 5936 en mapas exteriores y Thorn Wasteland stage 16):
     * Opciones para entrar a Área I (stage 50), Área II (stage 100), Área III (stage 117) y Área IV (stage 377).
     * Thorn Wasteland permite acceso selectivo a Territorios III y IV.
   * **Governor** (árbol 5940 en mapas de territorio):
     * Servicios de banco personal y almacén de liga.
     * Entrega de *Regression Scroll* (item 3734) y retorno con el scroll a la base privada.
3. **Gestión de Territorios (GM)**:
   * `/settw <tw_stage 200..207> <guild_id>`: Asigna un territorio inmediatamente a un clan.
   * `/tw list`: Muestra los territorios asignados y su antigüedad.

### D. Comandos GM Separados y Seguros
* **Nivel de Personaje**: `/level <1..471>`, `/lvl <1..471>`, `/levelall <1..471>`.
* **Nivel de Clan**: `/guildlevel <1..10>`, `/glevel <1..10>`, `/guild level <1..10>`, `/guildrank <1..10>`.
* **Reputación de Clan**: `/guildrep <cantidad>`, `/grep <cantidad>`.
* **Granja**: `/plant <crop_id> [plot_id]`, `/farm enter`.
* **Territorios**: `/settw <stage> <guild_id>`, `/tw list`.
* **Protección de Prefijos**: Se corrigió el bug de parsing de offsets `(0, 1, 2, 4)`. Si el byte previo es ASCII imprimible, el parser no corta letras intermedias, evitando colisiones entre `glevel` y `level`.

---

## 3. Lo que FALTA por Implementar (Pendientes Prioritarios)

### Prioridad 1: Batalla de Totem War en Vivo (Asedio Masivo)
Actualmente, los territorios se asignan estáticamente o vía `/settw`. Para completar el sistema oficial de Totem War falta el ciclo de combate en vivo:
1. **Temporizador Semanal del Evento**:
   * Programar ventana de 2 horas (ej. sábados/domingos).
   * Al iniciar, emitir broadcast global del servidor anunciando el inicio de Totem War.
2. **Spawn de Tótems y Fortalezas**:
   * En los mapas de batalla TW (stages 200 a 207), spawnear las entidades de Tótem correspondientes (IDs de NPC 9847..9855).
   * Configurar atributos: 50.000.000 HP, defensas altas según `monster.xml` / `totem.xml`.
3. **Reglas de Combate PvP en Escenarios TW**:
   * Habilitar ataque entre miembros de distintos clanes sin costo de PK / infamia dentro de los mapas 200..207 mientras dure la guerra.
   * Desactivar zonas seguras en los alrededores de los tótems.
4. **Registro de Daño y Adjudicación**:
   * Acumular daño por clan en cada entidad de tótem.
   * Si el tótem es destruido o cuando termina el cronómetro de 2 horas, el clan con mayor daño o último golpe (según la regla del juego) se adjudica la fila en `gremio_territorios`.
   * Enviar broadcast global con el clan ganador y actualizar inmediatamente los accesos de Terra Keeper y Heaven General.

### Prioridad 2: Mejoras de la Granja de Liga (Farm Stage 501)
1. **NPC Tienda de Semillas / Supervisor de Granja**:
   * Agregar diálogo y tienda al NPC granjero dentro de `farm.mpc` para comprar semillas de `crops.xml` con oro o con puntos de contribución de gremio, sin necesidad de usar el comando `/plant`.
2. **Ciclo de Crecimiento Asíncrono (Growth Ticker)**:
   * Crear una tarea periódica en segundo plano (`asyncio.create_task`) que revise `liga_granja_cultivos` y haga avanzar el estado de las plantas (`fase_crecimiento`) según el tiempo real transcurrido (`生長週期` de `crops.xml`), requiriendo que los miembros rieguen y abonen periódicamente para que no se marchiten.
3. **Plagas y Maleza (Pest / Weed Events)**:
   * Posibilidad de que aparezcan eventos aleatorios de maleza o insectos en las parcelas, que reduzcan la calidad de la cosecha si no se atienden.

### Prioridad 3: Funcionalidades Menores de Liga
1. **Subida de Logo / Emblema Personalizado de Clan**:
   * El cliente permite subir un BMP/PNG de 16x16 o 24x24 para el logo de liga. El servidor de archivos escucha en el puerto 21238 con opcode `0x0000` (actualmente devuelve avatars y fotos de personaje). Implementar la recepción y almacenamiento del logo de liga en disco (`data/guild_logos/<guild_id>.png`).
2. **Actualización de Miembros en Tiempo Real**:
   * Cuando un nuevo miembro entra a la liga o cambia de rango, difundir `0x0058` inmediatamente a todos los miembros online para que la lista de miembros se refresque en vivo sin requerir relog.

### Prioridad 4: Instancias y Mazmorras
* Las 17 instancias ya tienen plantillas JSON generadas y operan en mapas paralelos con sus bosses y drops garantizados.
* Si el usuario detecta algún script específico de boss con mecánicas de fases (ej. Leviathan's Bedroom o Gulp Room 4), revisar sus eventos en `eventos.py` y `eventos_mundo.py`.

---

## 4. Notas Técnicas y Restricciones del Entorno

1. **Python 3.10**:
   * No usar escapes de unicode `\uXXXX` dentro de llaves en f-strings (`f"{...}"`); causa `SyntaxError`. Declarar la variable de texto fuera y pasarla al f-string.
2. **SQLite en Windows**:
   * Conexiones abiertas con WAL (`PRAGMA journal_mode = WAL;`). Cerrar siempre conexiones explícitamente (`con.close()`), de lo contrario los bloqueos de archivo impiden reemplazar o borrar bases de datos.
3. **Comandos de Chat del Cliente**:
   * El cliente de Angels Online **se come la barra `/`** antes de enviar texto al servidor (envía `level 410\x00`, `glevel 6\x00`, `item 9969\x00`).
   * Toda palabra reservada nueva DEBE registrarse en `PALABRAS_GM` en `server/app.py` y en `_CMDS` en `server/gm.py`.
4. **Batería de Pruebas Automatizadas**:
   * Ejecutar para validar cambios sin romper nada:
     ```bash
     python -m unittest tools/test_ligas_servicios.py tools/test_guilds_and_teams.py tools/test_banco_liga_transacciones.py tools/test_comandos_gm.py -v
     ```
   * Todas las 24 pruebas unitarias pasan limpiamente en 3.5 segundos.

