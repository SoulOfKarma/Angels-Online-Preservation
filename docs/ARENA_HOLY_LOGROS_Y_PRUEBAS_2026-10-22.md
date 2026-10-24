# Angel Arena / Holy: controles de prueba, logros y REA

Nota posterior: [correcciones de Holy, piedras y EXP configurable](HOLY_RUNTIME_Y_PASES_2026-10-22.md).
Prevalece sobre los defaults anteriores: Arena ahora es todos contra todos;
eliminatorias siguen opcionales. Holy entrega EXP/skill EXP propias autorizadas,
no importes oficiales. Retorno al lobby con cuenta de10 a0. Los objetos y
tablas oficiales aun desconocidos no se sustituyen ni se dan por recuperados.

## Probar con dos clientes

Reiniciar el servidor para cargar Python/JSON; reconectar. No se reiniciaron
sesiones activas automaticamente ni se ejecutaron torneos sobre cuentas reales.
Los comandos requieren los permisos GM existentes, no se abre una puerta nueva.

Arena para personajes de nivel real 410 (PLV 10 sigue siendo nivel real 410):

```text
/aastart 30 410 2
/aa enter
```

Si no estabas en Sign-up Office, `enter` primero te lleva al lobby. Despues
de cargar el mapa, repetir `/aa enter`. Los jugadores sin GM pueden entrar
con el High-Tier Clerk. Cuando ambos esten inscritos:

```text
/aa begin 410
/aa status
```

Holy, sin restriccion de nivel:

```text
/hbstart 60 2
/hb enter
/hb begin
/hb status
```

El registro por defecto es de **15 minutos en ambos eventos**: `/hbstart 60`
y `/aastart 30 410` omiten el parametro de registro. Se anuncia la apertura,
despues cuando quedan 10, 5 y 1 minuto, y al iniciar el combate. Todos usan
el mismo cartel global que `/notice`. Los avisos quedan registrados por ronda
para no repetirse tras recargar; un tick atrasado no reproduce avisos vencidos.
Si se configura un registro mayor, se avisa cada 5 minutos restantes y al
ultimo minuto; con los 2 minutos de los ejemplos solo corresponde el aviso de 1.
`begin` adelanta el inicio sin lanzar los recordatorios que se saltaron.

Mismo recorrido de lobby/entrada. Por solicitud de Karma, las rondas GM tambien
usan entrada normal: Arena cobra gold del juego segun nivel; Holy exige la
Battlefield Cursed Stone. Se conserva prioridad del pase vigente, consumo
de una sola piedra si no hay pase y reentrada sin doble cobro.
`cobrar_entrada_en_pruebas: true` es el valor por defecto; puede ponerse false
antes de abrir una ronda para una prueba expresamente gratuita. La politica
queda guardada en la ronda; las rondas antiguas no cambian de precio a mitad.
Esto NO habilita premios sin verificar ni la apertura automatica.

`/aa watch` y `/hb watch`: observadores. `/aa lobby` y `/hb lobby`: lobby.
`/aa finish [nivel]` / `/hb finish`: resolver una prueba, no falsear resultados.
Arena no concede campeon a varios supervivientes por forzar el cierre;
Holy usa los cristales reales (empate no concede victoria). `/aastop [nivel]`
y `/hbstop` cancelan sin victoria. Inicio con registro 0 mantiene compatibilidad
de entrada GM inmediata, pero las llaves se cierran al primer tick: para dos
clientes es preferible el registro de 2 minutos y `begin`.

## Lo implementado en esta actualizacion

- Eliminatorias persistentes de Arena, hasta 64 participantes: los conjuntos
  de llegada originales 100..105 tienen 32/16/8/4/2/1 posiciones. Los textos
  8067..8089 describen observacion de final, 4, 8 y 16. Se asignan rivales por
  llave; nadie puede atacar otra llave, al publico ni durante la cuenta previa.
- `formato_arena`, `arena_ronda_segundos` y `arena_cuenta_segundos` se guardan
  en cada ronda. El total de tiempo limita cada fase. Asignacion/byes y doble
  eliminacion al agotar tiempo son reglas de compatibilidad, no codigo del
  servidor IGG recuperado. No se inventa ganador por HP, nivel ni azar.
- Preparacion en Waterfall. Desconectar durante registro no elimina si vuelves
  antes de empezar; volver despues del inicio solo permite observar. Salir de
  la batalla elimina sin posicion. Reubicaciones internas usan 0x0003, evitando
  encadenar cargas de mapa al morir o pasar a otra llave.
- Los tornados de Arena abren el menu original 8067. El observador puede
  cambiar de plataforma; el competidor solo puede retirarse, no escapar de su
  llave mediante un menu de observacion. Holy conserva sus salidas al lobby.
- Observacion asimetrica: el publico ve la batalla, pero no aparece ante los
  participantes ni publica movimientos/equipo/mascotas/invocaciones. No puede
  lanzar curaciones/buffs ni hablar por chat publico/Battle.
- Holy conserva estatuas, guardianes, reconstruccion con aportes parciales,
  conversion original de materiales, cristales y equipos separados de TW.
  Las acciones de construir/destruir ahora tienen contadores separados por tipo.
- Canal nativo Battle C2S 0x0133 de Holy y `/hbteam texto`: solo equipo propio,
  tambien durante preparacion; no enemigo, observador ni gente de otros mapas.

## Achievements reales, no IDs inventados

Fuente local `achievement.xml` -> `server/plantillas/logros.json`:

| Regla | Contadores conectados |
| --- | --- |
| Holy, 131..242 | Victorias; puntos, cristales, puertas/estatuas destruidas y construidas; acumulado y mejor sesion |
| Arena, 243..247 | Clasificacion top 32/16/8/4/2 |
| Arena, 248..253 | Numero de clasificaciones |
| Arena, 254..260 | Campeon acumulado |

Los umbrales, puntos y titulos salen de cada fila original. Se conserva la
entrega normal de titulo y Super BC, y se actualiza 0x0155. Los logros se
pueden conseguir en pruebas GM (`logros_en_pruebas: true`). No hace falta
un comando que los regale: hay que cumplir la accion/resultado.

`competiciones_logros` guarda un snapshot por ronda/personaje en la misma
transaccion que el resultado o la construccion. Reintentar o recargar no duplica
contribuciones ni victorias; los resultados offline tambien quedan guardados.
Al abandonar Holy se reinicia el tramo de contadores de una sola sesion,
sin perder acumulados ni achievements ya desbloqueados. Observadores no suman.
Cancelar no da victoria; una sola persona no genera un campeon de logro.

## REA realizada

Sesion local REA/Ghidra sobre `G:/Angel.exe`, SHA-256:
`7c1f8cc16e2032081dc15ccc1a67de668803f62d8252ab570d1f4724c162d6e9b`.
No se ejecuto el cliente. Evidencias locales crudas en `docs/rea_evidence/`
(directorio ignorado por Git); se conserva aqui el resultado reproducible:

- `FUN_005f3d70`: lee ocho bytes desde +2..+9 y un DWORD en +10; llama a
  `FUN_006692a0`. Confirma el paquete S2C 0x013B de 14 bytes incluido opcode.
- `FUN_006692a0`: primer byte habilita/oculta marcador; cuarto byte habilita
  estadisticas personales; transmite los restantes valores a los widgets.
- `FUN_00669000`: renderiza los campos 4..7 en dos digitos y el 8 en cinco;
  selecciona recursos de color segun TEAMID (+0x2f0 igual 1/2).
- `FUN_005ffe10`: propiedad TEAMID con subpropiedad 1 actualiza ese WORD;
  subpropiedades 2..8 actualizan marcador y 9 cambia estado/UI.
- Busquedas `arena`, `expprize|bufprize` no aportaron una tabla de premios
  dentro del ejecutable. Las cadenas de Battle Pass pertenecen a otro sistema:
  no se utilizan para rellenar Arena/Holy.
- XML de map114: GIVE_ARENAPRIZE, accion 83, sin parametros en nodos
  1000103/1000143/1000169. No revela el lote de premios que entregaba el servidor.

## Premios configurables: capacidad y limite real

`premios_arena` y `premios_holy` admiten filas por rango de nivel real y por
puesto (Arena) o resultado ganador/perdedor/empate (Holy). Cada fila admite
`exp`, `oro`, `creditos` e `items` (`id`, `cantidad`). Se valida al abrir la
ronda y se congela su tabla: cambiar JSON a mitad de evento no altera su premio.

El ledger `competiciones_premios` entrega planes verificados automaticamente
por el reloj y permite reintento en el clerk. Entrega y cambio a `entregado`
son una transaccion. Bolsa llena o inventario desincronizado dejan pendiente;
reconectar no duplica y se conservan datos ajenos al premio.

Por defecto las tablas siguen null y `premios_en_pruebas` es false. El estado
`sin_tabla` no se presenta como una entrega exitosa. No se extrapola la formula
de EXP de otra region ni se inventa un lote 401+. Tampoco se cambia la validez
de certificados por objetos permanentes: una fila temporal sin canje verificado
se rechaza al abrir, no despues de cobrar al jugador. Esos datos y el canje
temporal NO estan reconstruidos; produccion automatica sigue protegida.

La [guia historica IGG de Arena](https://ao.igg.com/act/house/arena.php)
documenta registro 15 minutos antes, observadores y certificados de cuatro
horas. Sus siete areas/rangos no son la descripcion del mapa moderno; no se
mezclan con las llaves 32..2 del cliente actual.
La [presentacion IGG de Holy](https://ao.igg.com/act/glory/) no ofrece una tabla
moderna completa. Horarios del cliente moderno permanecen en el documento
[PLV y competiciones](PLV_Y_COMPETICIONES_2026-10-22.md); su zona horaria oficial
no se deduce del XML. Los comandos GM usan minutos relativos, independientes
de esa incertidumbre.

## Verificacion

`tools/test_competition_completion.py`: eliminatorias, cuenta previa, rivales,
resultados, logros offline/reintento, sesion de Holy, menu de observacion,
chat de equipo y ledger de premios. Ademas se ejecutan las regresiones previas.
No equivale a una validacion visual con dos clientes: esa prueba queda para
el servidor reiniciado con estos comandos.

La bateria dirigida (eventos, mapas, PLV/Aliua, ligas, TW y mascotas) pasa.
Ultima ejecucion combinada: **249 passed**, un aviso existente de asyncio.
Las 17 pruebas nuevas de finalizacion tambien pasan tras la ultima proteccion
de carga de mapa; compilacion de los modulos y `git diff --check` sin errores.
La ampliacion a la suite antigua de casas encontro cinco fallos que tambien
se reprodujeron con `app.py` de HEAD y una SQLite temporal inicializada:
jabon 10626 (2500/500), alias Trade `@`, dos expectativas de efectos de
captura (36/19) y entrega de canales privados a un mock sin equipo/liga.
No se cambiaron esos sistemas para hacer pasar pruebas ajenas a esta entrega.
