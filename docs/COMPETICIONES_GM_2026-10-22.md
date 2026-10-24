# Arena / Holy Battlefield: implementacion en curso

Actualizacion vigente: [runtime, pases y EXP propia autorizada](HOLY_RUNTIME_Y_PASES_2026-10-22.md).
Holy SI entrega EXP y skill EXP configurables en las pruebas nuevas; esa
formula es propia, no oficial IGG. Arena usa supervivencia por defecto.
Las limitaciones de premios oficiales de abajo no significan que Holy siga
sin recompensa: se refieren a tablas oficiales/objetos no recuperados.

Actualizacion posterior: [pruebas GM, eliminatorias y logros](ARENA_HOLY_LOGROS_Y_PRUEBAS_2026-10-22.md).
La entrega actual incorpora el motor de logros, observadores ocultos, chat de
equipo y un ledger de premios configurables. Las tablas oficiales completas y
el canje de certificados temporales siguen siendo datos/funciones no recuperados.

No declarar esta entrega como sistema oficial completo. Karma solicito
completar premios y edificios, con premios oficiales inicialmente y despues
configurables. Los edificios avanzaron; la tabla de premios IGG para niveles
altos y su entrega siguen sin resolverse. No se sustituyen por premios de
servidores privados ni por extrapolaciones presentadas como oficiales.

## Seguridad de despliegue

`server/plantillas/competiciones_config.json` mantiene `modo_pruebas: true`.
Las rondas GM anuncian que son pruebas, pero por solicitud de Karma ahora
cobran la entrada normal: gold en Arena, piedra/pase vigente en Holy.
`cobrar_entrada_en_pruebas: false` permite una prueba expresamente gratuita.
No entregan premios sin tabla verificada. El reloj cierra rondas y mantiene cristales, pero no
abre torneos automaticos. Poner `modo_pruebas: false` rechaza la apertura;
no permite activar produccion con premios incompletos. Los campos de premios
alimentan ahora un motor de entrega atomica para premios permanentes y EXP,
oro/creditos. Permanecen null porque no se recupero una tabla oficial moderna;
no se convierten certificados temporales en premios permanentes.

La logica de tasas/piedras y horarios se prueba en bases SQLite temporales,
inyectando el modo competitivo solo en las pruebas. No modifica cuentas reales.

## Comandos GM de prueba

Reiniciar el servidor para cargar los cambios. No se reinicio ninguna sesion
activa desde estas herramientas; falta validacion visual en el cliente.

| Comando | Efecto |
| --- | --- |
| `/aastart 30 410 0` | Arena del rango de nivel real 410, batalla inmediata de 30 min |
| `/aastart 30 410 15` | Misma Arena, 15 min de inscripcion antes de combatir |
| `/aastop 410` | Finaliza solo la Arena de ese rango |
| `/aa status` | Estado de los tres mapas Arena |
| `/hbstart 60 0` | Holy Battlefield inmediato, 60 min |
| `/hbstart 60 15` | Holy con 15 min de inscripcion |
| `/hbstop` | Finaliza solo Holy Battlefield |
| `/hb status` | Estado de Holy |
| `/aa lobby` / `/hb lobby` | Viaje al Sign-up Office |
| `/aa enter` / `/hb enter` | Inscripcion/entrada normal desde el lobby; desde otro mapa primero lleva al lobby |
| `/aa watch` / `/hb watch` | Entrada como observador |
| `/aa begin` / `/hb begin` | Termina el registro y comienza la batalla abierta |
| `/aa finish` / `/hb finish` | Resuelve la prueba con el estado actual; Arena no inventa campeon si siguen varios vivos |

`/aa` acepta un nivel opcional en estas acciones. Se recomiendan dos clientes,
registro de 2 minutos, entrada de ambos y despues `begin`. `stop` cancela:
no concede victorias. Las pruebas SI dan logros por defecto (`logros_en_pruebas`),
incluyen ahora la EXP propia de Holy (`premios_en_pruebas: true`).
No se inventan objetos de Arena.

El inicio nunca teletransporta al GM. Los jugadores entran desde los clerks
del Sign-up Office (114). Arena: 159 / 239 / 240 segun nivel; Holy: 112.
No son los mapas de Totem War ni el Outpost Battlefield.

## Horarios auditados

La matriz completa de niveles, dias y tasas esta en
[PLV_Y_COMPETICIONES_2026-10-22.md](PLV_Y_COMPETICIONES_2026-10-22.md).
Se prefieren los textos del cliente IGG vigente: Holy viernes/domingo
12:00 y 21:00, Arena 19:30/19:31/19:32 segun rango, registro 15 min antes.
La interpretacion actual es hora local del servidor; no afirmar que la zona
horaria del XML este comprobada. La pagina historica de IGG usa otros horarios
y rangos mas antiguos, por lo que no se mezclan sus horas con el XML moderno.
Totem War conserva miercoles 21:00 y sabado 14:00, 120 min, sin modificaciones.

## Implementado y probado

- Cuatro clerks originales, direccion 6 con rotacion. Sin Exit Guide falso.
  Tornado de retorno (23,29), indicado por Karma.
- Rondas y resultados SQLite separados de Totem War. Registro/coste e ingreso
  en una transaccion; reentrada sin doble cobro; rechazo de estado obsoleto.
- PvP propio: aliados de Holy y espectadores protegidos. Muerte de Arena a
  espectador; Holy revive en su zona. Sin perdida de EXP ni premios de TW.
  Los combos pendientes no alcanzan la vida nueva tras reaparecer.
- Holy: cristales, entrega al angel propio, victoria a 20 o por tiempo,
  traslado entre aliados, caducidad de porte y retorno del cristal caido.
- Datos generados desde el MPC: 50 posibles estatuas y 40 guardianes de las
  20 puertas. El estado inicial restaurado tiene diez estatuas y puertas
  1/6/7/10 por bando. Materiales y reconstruccion se guardan juntos.
- Aportes parciales, limite de 25 estatuas, respawn por grupos de cinco,
  bloqueo de paso enemigo por puertas vivas y apertura al caer un guardian.
  Sin regeneracion automatica ni botin/EXP de monstruo normal.
- Conversion de materiales con 87 recetas originales de order.xml.
- Puntos personales de construccion, bajas, edificios y cristales. La division
  proporcional de puntos de puerta es una adaptacion, no una captura oficial.
- Marcador S2C 0x013B y TEAMID propiedad 120/1: formas derivadas de REA
  5F3D70, 6692A0, 5FFE10. Falta verificar numeracion visual y anillos en juego.
- Pases: fecha persistente, prioridad al pase vigente y limpieza de caducados.
  En ejemplares nuevos, plazo desde obtencion; antiguos sin fecha, primer
  ingreso competitivo. No renovar por reentrada ni traslado al banco personal.
  Un stack comparte vencimiento; agregar unidades no extiende su fecha.

## Pendiente real, no oculto por el modo de prueba

- Tablas oficiales completas de premios/eleccion, certificados y expiracion
  de equipo premiado. El ledger de entrega contra duplicados ya esta implementado;
  sin tabla verificada no se dan premios por defecto.
- Los siete campos de la guia historica no se mezclan con el mapa moderno.
  Ahora hay eliminatorias en los tags 100..105, con cuenta previa y rivales por
  llave. Asignacion, byes y doble eliminacion por tiempo son compatibilidad
  documentada/configurable, no una captura del servidor oficial. Los castigos
  historicos de dano por tiempo no se inventan para este formato.
- Mineria propia de Holy y servicios de apoyo que no aparecen en este MPC.
  Alex/Ally tienen su teletransporte aleatorio original; los especialistas
  de construccion y conversion funcionan. Los guardianes son objetivos
  inmoviles: sus datos XML tienen ATK 0; no se inventa una represalia.
- Rankings integrados con los tableros de las ciudades. El espectador ya se
  oculta sin publicar sus mascotas/invocaciones y el canal Battle de Holy
  entrega mensajes solo a su equipo; observadores no pueden combatir/chat publico.
- Olympus y transferencia de faccion Census son tareas separadas pendientes.

## Evidencia de premios y bloqueo

El cliente contiene certificados y equipo temporal de Arena hasta el rango
280+, incluido el equipo 66298..66320 y badges 66330..66332. Eso prueba que
existen los objetos, pero NO demuestra el lote exacto por puesto del nivel
401+. Los nodos modernos de map114 delegan GIVE_ARENAPRIZE (83) sin parametros;
la logica de entrega pertenecia al servidor. No inferir un lote completo solo
porque las descripciones de los objetos dicen Angel Arena.

La [guia original de Arena de IGG](https://ao.igg.com/act/house/arena.php)
confirma certificados con cuatro horas de validez y eliminatorias; sus rangos
son antiguos. La [pagina original de Holy de IGG](https://ao.igg.com/act/glory/)
conserva presentacion y horario antiguo, no una tabla verificable de nivel 410.
La [guia oficial japonesa de Holy](https://alo-nhn.ujj.co.jp/playguide/gamesystem/pvp_ss.php)
confirma edificios/puntos y publica EXP solo hasta 210; es otra region, no
una prueba de la recompensa del 410 de IGG. No extrapolarla en produccion.

Las tablas locales expprize.xml/bufprize.xml no se asignaron a Holy sin
demostrar su consumidor; pueden pertenecer a otros eventos. Las bases de
contenido inspeccionadas tampoco aportaron una tabla Arena/Holy identificada.
No se encontro un ejecutable del servidor oficial que contenga la formula.

Herramienta de auditoria: `python tools/audit_competition_sources.py 114 1000143`.
Generacion del dataset de Holy: mismo script, `112 --holy-data` (salida JSON).

## Verificacion

Pruebas nuevas: `tools/test_competiciones.py` y `tools/test_holy_battlefield.py`.
Cubren transacciones/rollback, reentrada, muertes/combos, cristales, edificios,
estado tras recarga, mapas y comandos. Tambien hay regresiones de TW, ligas,
servicios de Lyceum, PLV, Aliua e instancias. El resultado final de la suite se
registra en la entrega, sin confundir pruebas aisladas con validacion en juego.
Ultima ejecucion combinada: **147 passed**, un aviso existente de asyncio
en test_totem_war. `py_compile` de los modulos modificados tambien pasa.
