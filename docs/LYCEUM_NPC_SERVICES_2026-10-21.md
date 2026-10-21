# Astrologer, Login Rewarder y Green Angel

## Alcance

Servicios de Angel Lyceum (stage 41). No modifica BC/Super BC, captura de
pets, farm ni tasas normales de loot. Requiere reiniciar el servidor y volver
a entrar al mapa para ver los nuevos NPC y el giro.

Implementacion: `server/lyceum_services.py`, conexiones puntuales en
`app.py`, `dialogos.py`, `configuracion.py`, `logros.py` y spawns en
`plantillas/lyceum.json`. Se conservan las modificaciones preexistentes.

## Evidencia del cliente y decisiones de reconstruccion

Se leen las revisiones vigentes de los XML mediante `house_services.xml_rows`.
No se modifican PAK, ejecutables, cuentas reales ni registros de cuotas reales.
Los paquetes reutilizados son los de dialogo, estado de buff y canje que ya
implementa el servidor; no se agregan animaciones supuestas.

### Astrologer

- `npc.xml`: NPC 14701, sprite 40422. La otra variante 24580 no reemplaza
  automaticamente a la que ya usa este mapa.
- `msg.xml` 142501..142533: saludo, informacion, confirmaciones, resultados.
  Antes se abria 142535 ("Horoscope Topics") con una opcion japonesa sin servicio.
- Cinco lecturas por personaje/dia: gratis, 1M, 2.5M y 5M AG; la quinta
  consume un Astro Crystal 54852, no AG. Persistencia por fecha local del
  servidor en `personajes.datos.astrologer`; reconectar no restablece usos.
- `magic.xml` 14533..14568: doce signos, tres intensidades, 43.200 segundos.
  Reemplaza solo la familia Astro, sin acumular signos ni borrar otros bufos.
  Stats, carga, movimiento, EXP, Skill EXP y velocidad de recoleccion se
  conectan a los consumidores reales. La velocidad de fabricacion se aplica
  al sistema de fabricacion de casa actualmente implementado.
- Las cantidades se leen del XML, no del ejemplo del dialogo. Por ejemplo:
  Gemini III +100% EXP y Pisces III +300% Skill EXP (2x y 4x respectivamente).
- Logros "obtener hechizo" usan `buff:<id>`; cristal usa `usa:54852`.
- Direccion 7, la misma del Gaoler Angel junto a el (entidad 15). El giro
  sale en el spawn y un rotate explicito, no mediante un efecto de magia.
  Correccion tras la prueba: el camino de Lyceum reenviaba el `hex` guardado
  e ignoraba la direccion del JSON. Ahora aplica el byte 33 tambien a ese
  paquete. Astrologer permanece en (144,107), mirando abajo/derecha (7),
  hacia la flecha del usuario; no se desplaza su posicion.

**Probabilidades no oficiales:** no se encontro la tabla del sorteo en los
XML extraidos. Signos equiprobables; pesos I/II/III configurables: normal
`(1,1,1)`, cristal `(1,1,4)`, para reflejar su descripcion de mayor chance
de intensidad III. Estos valores son reconstruccion, no porcentajes medidos
del servidor oficial. El coste/limite/duracion si estan documentados en XML.

### Login Rewarder

- `npc.xml`: 24549, sprite 40003. Entidad local libre 412.
- Situado en (141,106), a la izquierda de Astrologer (144,107), siguiendo
  la referencia del usuario; **no se presenta esa posicion como extraida**.
  Tras los intentos (141,108) y (141,110), que se alejaban del punto marcado
  por interpretar al reves el eje Y, se usa (141,106), coordenada indicada
  por el usuario y mostrada en su minimapa. Astrologer y Gaoler no se desplazan.
- `msg.xml` 515006..515014: menu y explicaciones.
- `exchange.xml`: grupos 526/527/528 para Online Reward Scroll 66361,
  Premium Login Scroll 66362 y Supreme Login Scroll 66363, respectivamente.
- S2C0151 abre las recetas; C2S0148/0160 ejecuta un canje validado.
  Los grupos de estos NPC requieren haber abierto el grupo correspondiente.
  Materiales y todos los premios se planifican antes de consumir: mochila
  llena, material insuficiente o fallo SQL no consumen pergaminos. Se permiten
  multiples montones y reutilizar una casilla liberada por el material.
- El sistema de dias conectados/minutos y entrega de pergaminos ya existia
  en `bonos.py` y Event Overview (acciones 54/72/53); no se reemplaza ni se
  otorgan pergaminos gratis al hablar con el NPC.

### Green Angel

- `npc.xml`: 14907, sprite 40002. Entidad local libre 413.
- (215,74), posicion escrita en la descripcion de Straw Pollutant 60469;
  Scroll Seller esta en (212,81).
- **No** es el Straw de mision 301. Se usa Straw Pollutant 60469.
- `msg.xml` 513638..513663: requisitos, premios y menu. Caida desde enemigos
  o recursos de nivel >=21 en mapas normales, no desde el nivel del jugador.
  Se excluyen mapas dinamicos, privados o con distribucion de instancias
  segun `stage.xml`; en recoleccion se consulta `material.xml.等級限制`.
  La tirada de Straw es adicional al loot y solo tras recoleccion exitosa.
  Correccion tras el log de las 14:55: `combate.Monstruo` no guarda `.nivel`
  en los spawns normales; usar `getattr(m, 'nivel', 0)` bloqueaba todas esas
  bajas. `straw_drop_monstruo` consulta ahora `monster.xml` por NPC type como
  fallback. Reproduccion: Crystal Marsh 336, Drac 20754 y Drax 20755, ambos
  nivel 310. Se mantiene la chance, no se aumenta a 100% ni se cambian stats.
- **Tasa provisional 50%** en `STRAW_DROP_PROBABILIDAD`, independiente del
  multiplicador general de drops. Elegida tras confirmar el usuario que la
  caida era alta. No se encontro un porcentaje oficial en los datos publicos.
- 30 Straw: Go Green 20428/20429/20430, por nivel <=99 / 100..209 / >=210.
  Un dia, sin acumular intensidades; valores y duracion de `magic.xml`.
- 100 Straw: contador de sello oculto 60470, no un objeto visible en mochila.
  Activa los logros Earth-Saver 3603..3607 y titulos existentes mediante su
  evaluador normal, conservando el contador al reconectar.
- Catalogo completo: grupo **401**, 18 recetas 15328..15345: pociones,
  cervezas rojas/azules y nueve monturas. Se sustituye el grupo antiguo 348
  que solo mostraba tres canjes de pociones. La anterior exclusion del 401
  por considerarlo estacional fue una suposicion sin evidencia de fechas;
  se retira tras confirmar el usuario que faltaban estas monturas.
  Frozen White Bear: 1800 Straw; Speedy Horse: 1400; Mooing Calf: 1000.
  Cada especie tiene ATK, Defense y Agility; no se inventan variantes magica
  o neutra. ATK incluye ataque fisico y magico segun el propio item.xml.
  El grupo 401 usa tambien el canje atomico y la guardia de mochila llena.

## Persistencia y validacion

Coste, inventario, contador y buff se guardan en una transaccion SQLite sobre
el personaje exacto; la sesion cambia despues del commit. Confirmacion de
Astrologer ligada a fecha y numero de lectura para impedir repeticion o cobro
de una tarifa distinta al cambiar de dia. Solo se aceptan opciones visibles
en el dialogo activo. No se reinician cuotas ni se editan cuentas de prueba reales.

Prueba nueva: `python tools/test_lyceum_services.py` (25 casos), con SQLite
temporal. Incluye dispatcher de confirmacion/replay, tarifas y quinto cristal,
insuficientes, fallo SQL, reemplazo/persistencia de bufos, cortes 99/100/209/210,
sellos/logros, filtros de drop, recoleccion real, menus, paquetes de spawn/giro,
resolucion de nombres y canjes con mochila llena. Incluye los nueve premios
de montura y sus costes, canje real de oso, Drac/Drax de combate sin atributo
de nivel y el flujo real `login.poblar(41)` con giro posterior al spawn.

Regresiones ejecutadas: Farm 13, servicios de ligas 10, mundo/ligas 25 y
Past the Time/recompensas 5: OK. `git diff --check`: OK.

`tools/test_skills_and_buffs.py` pasa clasificacion y paquetes, pero su
assert de critico base espera 6 y obtiene 5. Se reprodujo el mismo fallo
cargando `inventario.py` de HEAD: no se corrigio ese test ni el critico como
parte de estos NPC.

**Limite de verificacion:** pruebas de servidor, XML y paquetes; falta la
prueba visual en el cliente de posicion, retrato y orientacion. Los pesos del
horoscopo y la tasa de Straw siguen siendo configuracion provisional.
