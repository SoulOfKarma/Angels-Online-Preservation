# Sistema de ligas: estado y pendientes

Actualizado el 19 de octubre de 2026. Este documento distingue lo implementado
y probado automáticamente de lo que todavía necesita pruebas con clientes o
investigación. No describe Super BC ni Broadcasting.

## Base implementada

- Los League Clerk de las cuatro ciudades apuntan al diálogo 5776. La creación
  exige nivel 25, rango de personaje 3 y 60.000 de oro, como indica el diálogo
  5778. La creación y el cobro se guardan en una sola transacción.
- Invitaciones, aceptación, miembros, rangos, permisos, cartel y transferencia
  de liderazgo están implementados. Se comprueba que las acciones sobre un
  miembro afecten a la misma liga; la transferencia se guarda atómicamente.
- El paquete de información `0x0055` se ajustó al diseño que copia el cliente;
  las contribuciones llegan mediante `0x004B`. El canal de liga es 5 y el de
  equipo es 4, de acuerdo con el cliente examinado por Claude.
- La contribución consume materiales según la última versión local de
  `setting/eng/guild_contrib.xml` (UPDATE17), por ID de fila y lotes, y guarda
  inventario, reputación y subida automática de nivel en una transacción.
  Los umbrales se leen de `update26/setting/level.xml`, campo `社團`:
  0 / 10.000 / 25.000 / 67.500 / 140.000 / 300.500 / 600.000 /
  1.500.000 / 3.750.000 / 9.375.000, niveles 1 a 10.
- El almacén de liga usa `0x0059`. Los permisos de retirar oro y objetos son
  independientes; los movimientos se guardan atómicamente y preservan mejoras
  y datos de mascota. No permite guardar mascotas invocadas ni disolver una
  liga con bienes en el almacén.
- Farm: petición C2S `0x014C`, requisito de nivel 6 comprobado por el servidor,
  stage 501, llegada desde TAG 255 de `farm.mpc`, sala y presencia por liga.
  Se guarda el regreso en SQLite; el tornado original de `(97,8)` devuelve
  al punto de partida. Si un jugador deja de pertenecer a una liga habilitada,
  la siguiente petición lo devuelve afuera. El mapa aparece en el lector de
  MPC y en las plantillas de login. **Esto implementa acceso y salida;
- Cultivos de granja: siembra (`farm.plantar`, comando `/plant`), riego C2S `0x014D`,
  abono C2S `0x014E` y cosecha C2S `0x014F`, lectura de `crops.xml`, asignación de
  coordenadas exactas por TAG de parcela (1..200), persistencia en SQLite
  (`liga_granja_cultivos`), paquetes nativos de EXP y entrega de la cosecha en
  la mochila del jugador. Población automática al cargar el stage 501.
- Propiedad de territorios y Totem War base: tabla `gremio_territorios`, condiciones
  28 `HAVE_GUILD_REGION`, 76 `SPEC_MAP_OWN_GUILD(tw_stage)` y 82 `GUILD_MEMBER_TIME(segundos)`,
  comandos GM `/settw <tw_stage> <guild_id>` y `/tw list`.
- Heaven General: diálogos 5920 en las cuatro ciudades, tienda de insignias 71
  (3735..3748), validación de 3 días de antigüedad en la liga (condición 82) y propiedad
  de territorio (condición 28), entrega diaria de cofres (3776..3783, 9255..9258,
  13409..13412) junto con el sello diario 3754 en ranuras ocultas, y acción 50
  `GOTO_GUILD_REGION` teletransportando al Área I (stage 50).
- Servicios de mapas privados (stages 50, 100, 117, 377): Governor árbol 5940,
  `OPEN_BANK 0` (banco personal), `OPEN_BANK 1` (almacén de liga), entrega de
  Regression Scroll (item 3734) y uso del scroll con regreso al Área I privada.
  Tornados de mapas privados regresan con GOTO_GUILD_REGION.
- Terra Keeper en mapas abiertos (stages 8, 9, 11, 12, 15, 16, 17, 21): árbol 5936,
  menú de áreas con acción 37 `CHANGE_PARA_MAP(stage, paralelo, tag=1)` validando
  propiedad del campo de batalla respectivo.
- Canales de chat de Liga y Equipo: soporte para prefijos de texto directo `@`,
  `/g `, `/guild `, `/l `, `/league ` (canal 5) y `#`, `/t `, `/team `, `/p `,
  `/party ` (canal 4), además del selector UI 0x0126.
- Sincronización en login: se llama a `gremios.al_entrar_jugador` y `equipos.al_cambiar_de_mapa`
  en la conexión inicial (`opcode == 0x0002` sin `entity_id`), garantizando que la
  información de liga y grupo aparezca de inmediato sin requerir cambio de mapa.

Las pruebas usan bases de datos temporales. Ejecutar:

```text
python -m unittest tools.test_banco_liga_transacciones tools.test_guilds_and_teams tools.test_ligas_servicios -v
python tools/test_banco_liga.py
```

## Pendientes

1. Probar visualmente con dos clientes la interacción simultánea en juego.
2. Totem War: combate masivo entre jugadores, generadores de guardianes/fortalezas
   (9847..9855) y ciclo de adjudicación automática al terminar la guerra de 2 horas.

Herramientas de consulta reproducible, sin modificar el cliente:

```text
python tools/auditar_ligas.py --heaven
python tools/auditar_ligas.py --farm
python tools/inspeccionar_protocolo_ligas.py
```

La última herramienta requiere `pefile`, `capstone` y el ejecutable local
`G:\REA\binarios\play_angel_unpacked.exe`.
