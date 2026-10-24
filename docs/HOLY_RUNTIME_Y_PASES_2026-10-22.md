# Holy / Arena: correcciones de las pruebas de Karma

Revision del23 de octubre: HOLY_PUERTAS_COLORES_CRISTAL_2026-10-23.md corrige el TEAMID120 de esta nota y el manejo de las puertas. El protocolo actual es001D38/1 para jugadores y0013/63 para companeros.

Revision posterior: [dialogos medidos y bloqueo real de inventario](DIALOGOS_COMPETICIONES_PROXY_2026-10-22.md).
Corrige la composicion7607+7596 de esta nota: el rechazo real es solo7607;
los horarios siguen accesibles por la opcion informativa. Incluye las tarifas
4M/8M confirmadas por Karma y la persistencia general de holy_pass_fin.

Reiniciar el servidor y reconectar para cargar Python/JSON. No se reiniciaron
sesiones ni se modificaron rondas/cuentas reales desde las herramientas.
Las rondas abiertas conservan su configuracion anterior: detenerlas y abrir
otras para probar estos defaults. Esto no es una certificacion visual del cliente.

## Hallazgos y cambios

- Colision real de entidades: la salida `71112001` compartia ID con el cristal
  naranja. Las salidas pasan a otra banda; hay una prueba de unicidad de TODOS
  los spawns de Holy, incluidos cristales, guardianes, puertas y minas.
- Las dos salidas60001 se conservan en `(311,8)` y `(23,284)`.
  Se conectan ademas las doce zonas60384 del evento92 original de map112;
  CHANGE_MAP(114,3). Se puede salir caminando por ellas. Los tornados tambien
  admiten clic cercano. No hay teletransporte por un clic remoto.
- Los tags101..110 eran zonas de minas, no resurrecciones. Se retira esa
  asignacion incorrecta. Se usan tags de base7/8 y del frente de estatuas
  120/125/130/135 y145/150/155/160. El avance cada cinco estatuas es una
  politica de compatibilidad sobre puntos reales del mapa, NO una tabla de
  resurreccion del servidor oficial recuperada. Se requiere validacion visual.
- Se conectan las60 minas originales, material248..257, sprite y coordenadas
  del MPC. Usan recoleccion normal con herramienta, distancia, tiempos,
  agotamiento y probabilidades de material.xml: Raw/Quality Building Stone
  8534/8535. Observadores, muertos y rondas terminadas no pueden recolectar.
- Se conservan las90 estructuras y sus HP del XML:50 estatuas y40 guardianes.
  Diez estatuas y puertas1/6/7/10 al abrir. Destruir cualquier guardian de una
  pareja quita toda su puerta; los aliados cruzan, los enemigos no.
  Guardianes y estatuas reciben TEAMID. El XML3902/3926 tiene ataque fisico0,
  AI162 y velocidad0: no se inventa un ataque de monstruo normal para ellos.
- La reconstruccion sigue siendo por Building Material8536, con aportes
  parciales persistentes y consumo atomico. Statue Master construye la siguiente
  estatua destruida (2 materiales); Home/Front Labor Leader reconstruyen
  puertas1..5/6..10 con su coste original. No hay curacion gratis de estructuras
  vivas. Material Maker convierte50 Raw en1 material, o1 Quality en2.
  Se restituyen las paginas informativas que explican estos servicios.
- Cuando Holy esta cerrado, el clerk muestra7607 (fuera de registro) y7596
  (horarios), con retrato69. No manda el generico de Arena por chat.
  Son textos originales concatenados; no se afirma que sea una captura IGG.
- Al viajar se cierra y descarta el dialogo anterior. Al salir de Holy se
  limpia TEAMID y se ocultan ambos paneles013B ANTES de CHANGE_MAP, no solo
  despues de cargar el lobby. Tampoco se mantienen sus paneles en Arena.
- Holy asigna Jabaly/naranja1 o Raphael/azul2 al azar cuando ambos tienen el
  mismo peso; prioriza equilibrar numero y suma de niveles. La asignacion se
  guarda y la reentrada no sortea otro bando ni cobra otra piedra.
- No se activa la propiedad22 de Totem War como indicador competitivo.
  Holy usa TEAMID120/1; Arena no tiene bando y usa supervivencia por defecto.
  Todos los competidores de Arena comparten plataforma2; no se dispersan
  entre plataformas de espectadores. Eliminatorias quedan opcionales.
- Un cristal propio caido puede devolverse sin duplicar puntos; no puede
  entregarse el enemigo mientras el propio esta caido o robado. El portador
  recibe el efecto3141 del XML (vulnerabilidad fisica/magica30%, cinco minutos),
  sin cobrar MP por este efecto automatico; se retira al entregar, morir,
  pasar el cristal, salir, agotarse el plazo o cerrar la batalla.

## EXP provisional autorizada por Karma (NO oficial IGG)

Configuracion: `server/plantillas/competiciones_config.json`, objeto `holy_exp`.
El usuario autorizo una formula propia configurable mientras se recupera la
oficial. No se usa la formula de otro servidor privado como si fuera oficial.
La guia [oficial de IGG](https://ao.igg.com/act/glory/) sigue siendo una fuente
de contexto, no evidencia de estos porcentajes. Los horarios modernos siguen
tomados de7596 del cliente, en hora local del servidor.

Con los defaults actuales:

| Recompensa | Participacion | Hasta500 puntos | Victoria con puntos | Maximo |
| --- | --- | --- | --- | --- |
| EXP personaje | 5% | +5% proporcional | +5% | 15% del nivel |
| EXP de cada habilidad equipada | 25% | +50% proporcional | +25% | 100% de su nivel |

Porcentajes en millon: `50000`=5%, `250000`=25%, `1000000`=100%.
Se aplica la curva real de level.xml, no la EXP acumulada total del personaje.
Ganar con cero puntos no da el extra de victoria. No hay bonus global de
tasas aplicado por segunda vez. El plan se congela por ronda y las cantidades
de habilidad se congelan al finalizar, antes de reintentos de entrega.
Se respetan topes de nivel y de ramas productoras.

Se necesitan dos competidores reales; espectadores, cancelaciones y jugadores
ausentes del mapa al cierre no reciben esta EXP. La entrega es atomica e
idempotente con el ledger: desconectar/reintentar no duplica EXP ni habilidades.
Los logros originales siguen usando sus propios contadores, no porcentajes nuevos.
Una tabla explicita `premios_holy` prevalece sobre la formula; `holy_exp.habilitado`
false la desactiva. Las tablas tambien aceptan `skill_exp` y `skill_exp_ppm`.

Al terminar se guarda el resultado, se entrega el premio y se anuncia por chat
la cuenta10,9,...,0; a0 se vuelve al Sign-up Office. `hbstop` cancela y vuelve
inmediatamente, sin premios. Reconectar durante la cuenta no reinicia el plazo.
Si hay progreso local pendiente de guardar, la entrega reintenta sin sobrescribirlo.

## Piedras temporales

-16762 ->16764:30 dias. -16763 ->16765:60 dias.
El XML de16765 declara129600 minutos (90 dias) pese a llamarse60 Days;
la correccion de servidor usa60 dias, documentada explicitamente, sin editar
el XML del cliente ni acortar ejemplares que ya tengan fecha de vencimiento.
- Desellado atomico: caja, pase y fecha absoluta se guardan juntos. Una mochila
  llena no consume el sello; dos piedras abiertas por separado no comparten reloj.
- El timestamp viaja en entry+47, flag de minutos desactivado en+58; no se toca
  el campo de longitud+51. Se envia en inventario inicial, refrescos, movimientos
  y banco. REA previo del tooltip sub_5C3710 verifica que el cliente resta la
  hora del servidor al timestamp absoluto, no que espere minutos restantes.
- El plazo empieza al abrir, corre desconectado y en banco, no se refresca al
  entrar al evento; se prioriza sobre la piedra de consumo unico. No se admite
  una caja sellada como pase. Los ejemplares antiguos sin fecha siguen
  activandose en su primera inscripcion por compatibilidad.

## Prueba de los clerks y diagnostico de la captura

Los tres menus reales se prueban con C2S0005 y000B, no solo llamando funciones.
Lectura de la DB durante el reporte: solo habia ronda159 para60..89; no habia
rondas239 ni240. Eso explica por que personajes303/410/434 no encontraban su
tramo abierto, incluso usando su clerk. No se altero esa DB.

```text
/aastart 5 303 15
/aastart 5 434 15
/aa status
```

Abre dos pruebas separadas (300..319 y401+),5min de batalla y15 de registro.
Mid-Tier:303; High-Tier:410/434. Cada uno entra pagando gold. Para otro nivel,
usar su nivel real como segundo parametro; PLV10 significa nivel real410.
`/aastart 5` usa el nivel real del GM y15min de registro.
`/aa begin 303` y `/aa begin 434` adelantan sus inicios por separado.
`/hbstart 5 15`, inscribir al menos dos personajes con piedra, `/hb begin`.
La configuracion se congela al abrir: una ronda antigua no cambia de formato.

## Evidencia y verificacion

- Fuente reproducible: `tools/audit_competition_sources.py 112 --holy-data`,
  map112 UPDATE9, map114 UPDATE21 y XML mas reciente por tabla.
- REA de esta revision:005ff200 (propiedad22),0074a5b0/5d0 y005ffe10
  (TEAMID y paneles de Holy), evidencia en `docs/rea_evidence/1792703*`.
- Regresiones nuevas en `tools/test_holy_runtime_regressions.py`: menus reales,
  IDs unicos, salidas, minas, equipos, limpieza UI, desellado atomico, formatos
  de caducidad, EXP/skill EXP, reintentos y cuenta de cierre.
- Bateria ampliada final:324 pruebas pasan (runtime, Outpost, competiciones,
  Holy, NPC, carga de mapa, PLV/Aliua, ligas/TW, instancias, pets y servicios
  de casa). Una advertencia asyncio preexistente en test_totem_war. Tambien
  pasan py_compile y git diff --check de los archivos editados de esta revision.
- No se atribuye a REA el codigo del servidor IGG: el cliente no contiene su
  formula de recompensas ni toda su maquina de estados. Sigue pendiente la
  validacion visual de esta revision con los clientes del usuario.
