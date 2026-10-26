# Servidor local para Angels Online

\*[English](README.md) · **Español\***

Reconstrucción del protocolo de red de **Angels Online** (IGG, cerrado en
febrero de 2026, cliente 8.5.1.0) y un servidor que lo habla, hecho por ingeniería inversa del
cliente y de capturas de tráfico.

No es un emulador completo. Es el **protocolo documentado** y un servidor que
llega hasta donde llega: se crea un personaje, se hace el tutorial, se elige
clase, se pelea, se sube de nivel y se compra y vende en las tiendas. Lo que
falta está listado abajo, sin adornos.

Cada afirmación sobre el protocolo tiene una medición detrás. Donde algo es
una suposición, lo dice.

---

Servicios sociales, Album nativo, Angel Elementary y League War conectados.
[Funcionamiento, comandos GM, premios comprobados y limites pendientes](docs/SOCIAL_ALBUM_QUIZ_GVG_2026-10-25.md).
[Correcciones de GvG, persistencia social, Alone y produccion](docs/GVG_SOCIAL_PRODUCTION_FIXES_2026-10-25.md).
[Recetas al instante, comando /recipes, ordenes y salida de Wolay](docs/PRODUCTION_FRIENDS_WOLAY_2026-10-25.md).
[Ordenes de recoleccion, recursos, Nightmare Cave y Love Broadcasting](docs/GATHERING_NIGHTMARE_LOVE_2026-10-26.md).

## Estado real

Olympus: Olly/Ozzy, canjes, mapas 217/332 con oleadas por piso y registros de
Omos conectados a rankings. Item Mall: catalogo depurado excluyendo bolsas de evento/ligadas,
piedras 5X y objetos con icono de interrogacion rojo (9407..9416); huevos de clase (80489..80495)
ordenados al principio; compras/regalos y Store Cabinet con 1.000.000 AG iniciales. Star Blessing
incluye mejoras, 27 recetas, longitud S2C 0x017F y correspondencia matriz/cartas/almacen corregidas,
y uso atomico de Star Keys. Auto Divine llena las cartas de una en una; costes nativos,
tiradas IV/V gratis, Stardust y premios de Bingo contrastados con capturas.
Bolsas de venta verificadas de2025 en On Sale/Fashion/Bubble; Top Sale usa compras locales.
Scrolls de ciudad, marcas Mark/Maple persistentes y libros de viaje de equipo atomicos.
Clases de Produccion y Manufactura: reparado el flujo completo de recoleccion y fabricacion para Weaponsmith, Armorsmith, Tailor, Chef y Craft (Technician).
Los nodos de recursos (Mineria/Dig, Tala/Lumber, Pesca/Fishing y Cosecha/Collect) exigen la posesion de la habilidad, nivel de habilidad requerido segun el nodo (aviso nativo 356), y herramientas adecuadas o montura robot.
Las monturas robot (機甲) permiten recoleccion universal aplicando bonus de reduccion de tiempo por nivel de Drive (habilidad 25) y optimizacion de atributos por Mechanism (habilidad 24); cada extraccion exitosa otorga Skill EXP a la habilidad de recoleccion y a Drive y Mechanism si se esta montado en robot.
Manufactura nativa (0x0036/0x0037) ligada a los aparatos originales en Lyceum, las cuatro ciudades, Palm Base y casa; recetas conocidas persistentes, planos consumidos al aprender, materiales y productos atomicos.
Skill Angel permite el intercambio libre de habilidades (0x002F, contenedor 10) para productores, con calculo de class_id corregido para preservar la profesion de oficio aun llevando armas o dagas secundarias.
Al elegir cualquier clase de productor se entrega automaticamente el robot basico `Freshman Cask` (19814) en la ranura de montura, y confirmar la salida del tutorial teletransporta directamente al Angel Lyceum.
Zonas de Procesado de Material y NPCs de Produccion: restaurados los sprites, dialogos oficiales, tiendas de recetas/materiales y NPCs de canje (`Party Angel`, `Gear Clerk`, `Fashionable`) en Angel Lyceum, las cuatro ciudades de faccion (Aurora City, Dark City, Breeze Woods, Iron Castle) y Palm Base, incluyendo `Ironsmith`, `Salesmen`, `Directors`, `Clerks` y `Plan Sellers`.
El canje en Party Angel soporta el `Renewal-Lv 200 Equipment Voucher` (72058) y la apertura de las cajas `Renewal-Lv200 Light Armor`, `Heavy Armor` y `Gown` (72059..72061).
La tienda de canje de League War incluye todos los Battlefield Badges desde Lv 13 hasta Lv 28 (48017..48024, 79352..79359).
Persistencia del Album (`cuentas.py`) corregida para preservar las listas de celdas `_entries` al iniciar sesion y guardar.
Daily Events: dos juegos distintos por dia en una rotacion semanal local
configurable (42 filas por tramos), entrada automatica al tramo de nivel correspondiente,
apertura atomica simultanea de los 4 tramos de nivel, entrega periodica de EXP (escalada por nivel hasta ~2M) y Skill EXP (~100)
mediante avisos oficiales de sistema sin numeros flotantes de combate falso, aparicion y retorno por faccion en Swindle World
(Aurora 97,158; Beasts 95,51; Steel 305,52; Shadow 303,155) con sus salidas dedicadas, anuncios deslizantes superiores
tipo /notice al abrir registro, empezar combate y finalizar evento, warps de salida transitables hacia
Angel Lyceum (radio 2, con salida bajo el arco de trebol en 28,25 para Training City) y preservacion del retorno original
a la base al abrir cofres.
Comandos GM: /daily start y /daily enter. No se recuperaron los horarios ni probabilidades del servidor original.
Angel Lyceum: NPCs restaurados
Astral Angel (canje de Star Keys 393), Party Angel (cajas renewal y canje 245), Chat Bubble Exchange
(grupos 559, 570), Fashionable (recetas de vouchers) y Reissue Angel.
Party Angel aplica Archangel's Secret original durante 12 horas; Compensation Angel retirado.
[Fuentes, pruebas y limites](docs/MALL_STAR_FURNITURE_DAILY_2026-10-24.md).

Arena/Holy: controles GM de registro/entrada/inicio, Arena todos contra todos
(eliminatorias opcionales), Holy naranja/azul, minas y salidas originales,
observadores ocultos, chat de equipo y achievements originales persistentes.
[Correcciones de runtime, piedras y EXP propia configurable](docs/HOLY_RUNTIME_Y_PASES_2026-10-22.md).
[Dialogos reales del proxy y correccion de entrada con guardado real](docs/DIALOGOS_COMPETICIONES_PROXY_2026-10-22.md):
comparacion semantica de inventario, confirmacion antes de cobrar y tasas4M/8M.
[Guia de pruebas y limites de premios oficiales](docs/ARENA_HOLY_LOGROS_Y_PRUEBAS_2026-10-22.md).

Outpost 47/48: PvP permanente y portales originales restaurados. Correcciones
de Wolay, parametros de nombre, carga de mapas e invocaciones PvP/desconexion:
[detalle y pruebas](docs/OUTPOST_Y_RUNTIME_2026-10-22.md).

Supreme Power activa la etiqueta PLV sin cambiar nivel real ni ranuras.
Restaurados Blessing Angel y el dialogo de viaje de BattlefieldAngel.
Arena y Holy Battlefield tienen rondas persistentes, inscripciones, PvP propio
y comandos GM separados. Holy incluye captura de cristales. Horarios del XML
en hora local del servidor. Holy incorpora construccion persistente, estatuas
y bloqueo de puertas. Trabajo aun incompleto: sin apertura automatica y con
rondas GM con entrada normal (gold/piedra) hasta completar los premios oficiales. Los premios semanales de Olympus y las
transferencias Census siguen pendientes.
Ver [comandos, mapas y limites](docs/COMPETICIONES_GM_2026-10-22.md).
Ver [alcance y reglas originales](docs/PLV_Y_COMPETICIONES_2026-10-22.md).

Totem de Crashing Hillock en `(92,174)`, confirmado en el juego por el usuario.
Se retira el experimento de sombra sin cambiar las reglas de guerra.
Ver [posicion y restauracion visual](docs/TOTEM_SOMBRA_2026-10-21.md).

Buffs y paredes (21/10): aumentar HP/MP maximos ya no rellena los recursos;
los buffs condicionales de Meditate seleccionan sus efectos XML. Los spawns
bloqueados de monstruos ya no desactivan las colisiones del mapa.
Ver [evidencia, pruebas y limites pendientes](docs/BUFFS_MP_Y_COLISIONES_2026-10-21.md).

La quest de Aliua conserva las ranuras actuales, incluidas 7–9, y nunca
concede una decima. Ver [compatibilidad del premio](docs/ALIUA_SIN_RANURAS_EXTRA_2026-10-21.md).

Entrega de pets del 21/10: [alcance, pruebas y pendientes](docs/ENTREGA_PETS_2026-10-21.md).

Progresion de pets (21/10): corregidos el bloqueo de fusion por rangos
iniciales, las estrellas generales desincronizadas y el primer pienso de
mejora sin incremento. Los coeficientes oficiales de intensificacion siguen
pendientes; no se compensan pets existentes automaticamente.
Ver [auditoria, correcciones y pruebas](docs/PETS_ESTRELLAS_AUDITORIA_2026-10-21.md).
Combos de pet: un solo efecto de skill y todos sus golpes de dano, sin
recastear cada subgolpe. El combate del personaje no se modifica.
Equip Pet: habilitado el slot 558 para pets de 5.0+ estrellas, con bonos
verdes reales y retirada de stats al desequipar. Crecimiento por nivel y
procedencia de las reglas en [la nota de equipo y crecimiento](docs/PET_EQUIP_Y_CRECIMIENTO_2026-10-21.md).

Servicios de Lyceum (21/10): Astrologer, Login Rewarder y Green Angel,
con costes/cuotas persistentes, canjes y Straws desde nivel 21. Detalles,
pruebas y probabilidades provisionales en
[la nota de servicios NPC](docs/LYCEUM_NPC_SERVICES_2026-10-21.md).
Green Angel incluye el catalogo de monturas (grupo 401) y Login Rewarder
queda en `(141,106)`. La caida de Straws usa el nivel real de `monster.xml`.

Farm: corregidos el alcance de interaccion y el refresco tierra/planta;
las animaciones experimentales quedan desactivadas, pendientes de validar.
Ver [diagnostico y pruebas de Farm](docs/FARM_INTERACCIONES_2026-10-21.md).
Esta entrega tambien incluye los cambios previos de vales de EXP/honor,
estadisticas permanentes y alias de arranque de `app`;
ver [alcance y validacion de la entrega](docs/ENTREGA_2026-10-21.md).

**Funciona**

- Login, creación, selección y borrado de personaje, con persistencia en disco
- Entrada al mundo, movimiento, cambio de mapa y portales del suelo
- El tutorial de Angel Raphael: elegir clase, recibir el equipo y el traslado
- Inventario con **cantidades**: los consumibles se apilan, y equipar,
  desequipar y mover entre casillas se contesta casilla por casilla, como
  hace el servidor real
- **Card Book de IGG**: las 459 cartas coleccionables y los 106 sets salen de
  las tablas del último cliente de IGG. Registrar una carta auténtica consume
  exactamente una unidad, actualiza de inmediato la Card List nativa y conserva
  la colección al reconectar. Los objetos que no son cartas y los registros
  duplicados se rechazan sin consumir nada
- **Premios de sets de cartas**: los sets de «todos los premios» y «elegir uno»
  usan la petición de canje nativa del cliente. El servidor valida que el set
  esté completo y que sólo se canjee una vez; los premios y el estado del canje
  se guardan de forma atómica, por lo que una mochila llena o un fallo al guardar
  no puede entregar premios parciales ni duplicados
- El bloque extendido del inventario se sincroniza en las pestañas **Fashion,
  Card y Furniture (ranuras 167..556)**. Al mover un objeto desde una ranura alta,
  como la 280 de Card, a la mochila normal se vacía el origen con el delta
  `0x001B` nativo, evitando la instancia duplicada que cerraba el cliente
- Tiendas: comprar **varios objetos y varias unidades de una vez**, vender,
  separar un montón y destruirlo. Los precios de compra y venta salen de
  `item.xml`, y el total de una venta coincide con el capturado al oro
- Usar consumibles: las pociones y la comida devuelven HP y MP y gastan una
  unidad
- Stats calculados desde `item.xml` (el equipo suma de verdad), incluido el
  peso que se carga
- Combate: pegar y recibir, números de daño, críticos, armas duales, efectos
  de ataque, morir y revivir, botín, experiencia y experiencia de habilidad
- **Botín en todos los niveles**: ninguno de los 2.672 monstruos de las
  plantillas se queda sin soltar nada, hasta el 455 de Ultimate Arena. Hasta
  nivel ~200 con su tabla propia de `serv_drop.xml`; por encima, con el
  respaldo por tramo de nivel, porque **esos datos no existen en el cliente**
  (`serv_drop.xml` cubre el 76% del tramo 101-200, el 6,4% del 201-300 y el
  0,8% del 301-400)
- Monstruos: cadencia de ataque propia de cada uno, persecución, paseo,
  reaparición y efectos de sangrado y aturdimiento
- **Separar monstruos de NPC no depende solo del byte `klass`.** El servidor
  vivo manda algunos monstruos con la marca de NPC, el 199 — 88 spawns en
  ocho mapas, que acababan como NPC amistosos y sin IA. Lo zanjan los datos
  del propio cliente: `npc.xml` va del 1500 al 24893 y `monster.xml` del 1 al
  23860, y **no comparten ni un solo id**, así que por encima de 1500 la
  respuesta es segura. Por debajo sigue mandando el `klass`, porque `npc.xml`
  no llega ahí y los NPC antiguos del Lyceum usan números de dos y tres
  cifras que chocan con los de `monster.xml`
- **255 mapas poblados a partir de capturas**: 42.860+ monstruos, 2.350+ NPC y
  15.059 objetos de mapa, 7.671 de ellos con su recurso identificado. Cada
  monstruo, NPC y recurso sale de una captura; nada está inventado
- **Veinte mapas no salen del servidor principal, sino de un segundo
  servidor**: tres zonas enteras —**Night City Code**, **Sun Sea Maze** y
  **Cybertronica**— más dos Training Area. Es la única excepción a "todo sale
  de capturas de un servidor", y está explicada más abajo en _Las tres zonas
  que salieron de otro sitio_
- **Hay zonas enteras cerradas**, es decir con todos sus tornados cruzados y
  medidos: **Heart of Eden**, **Floating** (6 mapas), **el anillo del
  desierto** (Crescent Valley, Desert Racetrack, Ghost Village, Troop
  Outpost, Ancient Front, Fantastic Sand City, Nightmare Palace) y
  **Candyland** (7 mapas). **Atlantis está completo salvo las instancias**
  (incluida la ciudad central de **Palm Base**, poblada con sus 50 NPC y 22
  tiendas y servicios verificados), y a la cadena del bosque (de Cryptic Moon
  Swamp a Giant Wooden Stairs, 8 mapas) solo le quedan dos tornados. Más buena parte de Pharaoh, East Orient
  y los territorios de las cuatro facciones. También quedan cerradas las
  cadenas de nivel alto añadidas al final: **Arcana** (Starglow Path,
  Academia Woods, Mana Ruins, Coo Village, Ethereal Garden, Daydream Library,
  Reminiscence Cloister), **Goldenia** (de Emerald Coast a Royal Ruins, 9
  mapas), **Abyston** (Forsaken Crevasse, Specter Village, Crystal Marsh,
  Crystal Quarry, Shrouded Haven, Peril Chasm) y la cadena profunda de
  Galaxia Square a Deep Prison
- **572 portales**, 551 activos, casi todos medidos en los dos sentidos: la casilla del
  tornado sale de la captura, y también aquella donde el servidor real deja
  al jugador al cruzar. La mayoría se cruzaron **dos veces en cada sentido**,
  que es como se descubrió que algunos portales no dejan siempre en la misma
  casilla
- **Los portales que llevan a otro punto del mismo mapa** funcionan: **29**,
  repartidos en siete mapas. Solo Lost Trail tiene doce —seis pares que te
  mueven de una punta del mapa a la otra—, Horizon Archives tiene cinco y
  Branch Way tiene dos pares. **No** recargan el
  mapa — medido durante 1.401 segundos sin un solo `0x000C`. El servidor
  contesta `0x0016`, un `0x0012` de siete ceros y un `0x0003` que solo
  recoloca al personaje
- **Un portal puede traer su propio menú.** El nudo de Teddy Amusement
  pregunta «Move to which area?» y manda a uno de dos puntos del mismo mapa.
  Cada portal trae su id de mensaje y su tabla de opción a casilla, así que
  añadir uno nuevo es dato, no código
- **Otros 15 portales están anotados pero apagados**: **catorce entradas de
  instancia**, el único portal de Lost Cove que nunca se midió, y el tornado
  de Niro River a Clink Harbor — ese mapa existe en `stage.xml` pero el
  servidor vivo no tiene contenido para él. Las entradas salieron de cruzar
  los mapas y contrastarlas con el `jumpmap.xml` del propio cliente, que las
  etiqueta con **dos nombres distintos**, `Instance Entry Point` e
  `Instance Entrance`
- **El Angels GO!, el teletransporte de las Superwing**, funciona: el `0x0151`
  lleva el id de la tabla `jumpmap.xml` del propio cliente, se gasta una
  Superwing y la respuesta se bifurca, con las dos ramas medidas: un `0x0003`
  si el destino está en el mapa donde ya estás, y un `0x0007` más `0x000C` si
  es otro mapa. La tabla tiene **355 destinos** y **224 están activos**, los
  que caen en un mapa poblado; el resto se rechazan sin gastar el objeto. Un
  personaje que no pertenezca a una de las cuatro facciones no puede usarlas
  siquiera: medido con uno de nivel 12 todavía en «Heaven»
- Las cuatro ciudades de facción con su casilla de llegada, las cuatro
  medidas: Aurora City, Breeze Woods, Iron Castle y Dark City. Al elegir
  facción el juego deja al jugador al lado del Ángel de esa ciudad, a tres o
  cuatro casillas, en las cuatro
- **El flujo completo de salir del Lyceum**: el Angels' Tutor, elegir facción
  en el Graduation Palace, viajar a la ciudad, registrarse con su Ángel y que
  te devuelva al Lyceum. Funciona en **las cuatro ciudades**, cada una con su
  texto, su misión de registro y sus misiones siguientes
- Los portales entre el Lyceum y los dos playgrounds, con sus menús
- Cupid fija el punto de revivir donde estás parado
- Animación y ritmo de ataque por arma, medidos: lanza, bastón, espada, daga
  y dos armas de una mano mandan cada uno su propio par de valores
- El cooldown de cada habilidad sale de sus propios datos, aparte del ritmo
  del ataque básico
- Los magos pueden cambiar de rama de magia: se otorgan los hechizos de la
  nueva y se quitan los de la vieja
- **Sistema de magias y habilidades**: implementadas las ramas de combate y
  magia (Life, Wraith, Chaos, Earth, Curse, Meditate, Hit, Staff Hit, etc.) con
  sus hechizos iniciales, consumo de MP y asignación a la barra de acceso rápido
- **Fórmula de daño mágico y escalado**: daño base calculado según Ataque
  Mágico (SA) y multiplicador de hechizo menos Defensa Mágica (SD) efectiva,
  con bonificaciones por afinidad elemental (Fuego, Hielo, Trueno, Corrosión)
  y porcentaje de daño mágico
- **Tiempos de casteo (Cast time) y reducciones**: casteo dinámico medido de
  `content.db`, aplicando reducción de casteo plana por buffs activos (`First
Path`, `Third Spirit`, `Limit Breaker`, `Shadow Meld`, `Killer Intent`) y la
  reducción del **50% de casteo** de la pasiva `Curse Spell` (ID 5)
- **Animaciones de casteo diferenciadas**: los hechizos mágicos reproducen la
  animación propia de invocación con manos y glifo en el suelo (`0x0011` byte
  20 = 1), sin disparar animaciones de ataque físico de arma (`0x000A`)
- **Banners de subida de nivel (`0x0020`)**: animación visual con querubines y
  trompetas (banner rojo para nivel de personaje, banner azul para nivel de
  habilidad)
- **Progresión de habilidades (Skill EXP)**: subida de rango de habilidades
  (hasta nivel 300) mediante combate físico y mágico, repartiendo experiencia a
  las habilidades activas y pasivas de la clase según el daño realizado
- **Cálculo dinámico de Job / Clase**: asignación y actualización automática del
  Job ID del personaje según las habilidades equipadas en el árbol
- **Pergaminos de habilidad**: lectura y aprendizaje de habilidades desde libros
  y pergaminos en `content.db`, con persistencia completa de habilidades aprendidas
  entre sesiones y cambios de mapa (sin que se borren ni queden como `?`)
- **Sistema de Invocaciones de Wraith**: implementación completa de invocaciones de esbirros
  en las 11 familias y 55 habilidades (Death's Head / Esqueleto, Death Mummy / Momia,
  Death Leech, Azrael, Soul Eater / Devorador de Almas, Demonio I-V, Demon Summon I-V,
  Ghostly Swordsman, Putridox, Minotauro y Titán de Tierra / Golem). Incluye animación
  de cofre/portal en el suelo en la casilla objetivo (`tx, ty`), spawn de la criatura (`0x0008`),
  barra de vida dedicada (`0x0013`), vínculos bidireccionales amo-criatura (`0x3c` y `0x3d`),
  IA de combate autónoma (asiste al amo y cambia de blanco), persistencia entre mapas (`0x000D`)
  y calibración auténtica de cadencia/velocidad de ataque
- **Habilidades de Área de Efecto (AoE) en suelo y sobre sí mismo**: ejecución de hechizos
  AoE de terreno (Strong Acid Rain, Hell Flame, Frozen Trap, Fire Trap, Thunder Scope, etc.)
  en cualquier casilla del mapa sin requerir objetivo enemigo marcado, con glifos de suelo
  e impacto en (`tx, ty`) (`0x0011`)
- **Ring of Angel Wings**: teletransporte directo al checkpoint de Cupido
- **Diálogos de NPCs y Tiendas Oficiales ampliadas**: diálogos dinámicos, misiones y tiendas oficiales
  verificadas en ciudades de facción, centros regionales y mazmorras:
  - **Palm Base (Stage 88 - Atlantis)**: los 50 NPC poblados con sus diálogos exactos, retratos/sprites
    y 22 tiendas y servicios verificados (entrenadores de habilidades y diputados de magias nv 80-90,
    vendedores de arcos y armas, recetas maestras y de herrería de nivel alto, tiendas de materiales
    StuffShop, dependientes de oficios, reparación nativa de equipo, banqueros de almacén y servicios de mascotas)
  - **Lava Cave (Stage 69) y Flaming Door (Stage 70)**: recetas de herrería y artesanía nv 60-70 (Rock Smith
    y Rock Master), investigadores avanzados de armas y arcos, y entrenadores de magias (Earth Life Mage
    y ChaosWraith Mage)
  - **Once ciudades verificadas byte a byte** contra lo que manda el servidor real, con sus
    vendedores, banco, reparación y tiendas: Whitefang Village, Coo Village, Rainbow Town,
    Twinkle Town, Specter Village, Teddy Amusement, Galaxia Square, Desolate Sea, Chilly
    Village (región de Celestia) y Busy Market (región de Warring Realm)
  - **Floral Alley (Stage 398, región de Sun Sea Maze)**: única poblada **sin captura**. Los
    diálogos salen de `msg.xml` (bloque 516188-516210) y las tiendas de `shop.xml`, donde cada
    ciudad añade un par y el impar son espadas y el par magias: el `Researcher (C)` abre la 221
    (Edge Guard I) y el `Researcher (S)` la 222 (Astro Impact I), ambas de nivel 310
  - **Clank Oasis (Stage 407, Cybertronica) y Commercial Street (Stage 419, Night City Code)**:
    también sin captura, con los bloques 516648-516657 y 517063-517068 de `msg.xml`. Van por
    **stage** porque `Spell Analyst` y `Technique Analyst` se repiten en los dos mapas con
    tiendas distintas: 223/224 en Clank Oasis y 225/226 en Commercial Street
- **Past the Time Spirit y misión semanal 976**:
  - El NPC de Rainbow Town usa su sprite oficial (`40542`), retrato (`1342`), orientación sur y requisito de nivel 250. Su menú abre Chaos-Dinosaur Arena (Stage 413), Chaos-End Time (Stage 414), la tienda 659 de Time Crystals o cierra el diálogo.
  - *Nature is Crying for Help* entrega la EXP oficial por nivel (36M antes de nivel 90, 48M entre 90-94 y 72M desde nivel 95), un Weekly Quest Mark (`12611`) y 50 Honor Credits. No cobra ni entrega oro, eliminando el mensaje erróneo `Pay 29480`.
- **Sistema Integral de Mascotas (Pets al 85-90% de desarrollo)**:
  - **Invocación y Gestión de Barra**: Invocación con clic derecho en mochila, compatibilidad total con accesos rápidos F1-F12 y alternancia de múltiples mascotas. Al cambiar de mascota se despawnea y desvincula limpiamente la anterior sin dejar entidades fantasma (`0x000E`, `0x001B`, `0x015E`).
  - **Evolución y Etapas de Crecimiento**: Rompimiento del huevo automático a nivel 15 pasando a Junior Pet, y evoluciones por certificados (Medium Blood Certificate a nivel 35, Advanced Blood Certificate a nivel 55) con regeneración limpia de entidad y modelo.
  - **Alimentación y Saciedad**: Uso de `Pet Feed` (+500 de saciedad hasta 1000 máximo). Superar los 100 puntos de saciedad activa el bufo oficial `Pet's Satiation` (ID 3796) sobre el retrato de la mascota.
  - **Sistema Oficial de Estrellas (`pet_star.xml`)**: Integración completa de los 80 niveles de estrellas (0.1 a 8.0 estrellas). La mejora con `Improved Pet Feed` o `Star-up Cards` incrementa dinámicamente los bonos de todos los atributos según la tabla oficial.
  - **Tooltips Detallados de Inventario (231 bytes)**: Muestra el desglose de stats base y bono verde (`Attack 606 (444 + 162) Star Level: 0.4`), el nivel global `Star Level: 0.4` y el contador `has been intensified ( N ) times`.
  - **Ficha de Estado (`0x0065`)**: Muestra los atributos de combate efectivos resaltados en verde, valores base, 3 casillas de habilidades de mascota, resistencias elementales y estrellas.
  - **Órdenes e IA de Mascota (`0x003E` / `0x001D`)**: Compatibilidad con órdenes de Quieta (0), Seguir (1) y Atacar (2).
  - **Monstruos capturados y Poke Eggs**: la lista de especies capturables y la probabilidad base salen de `catch.xml`; las variantes de huevo modifican la probabilidad en vez de garantizar un 100%. Si falla, se consume el huevo y ese mismo spawn queda bloqueado hasta matarlo y esperar su respawn. Cada intento muestra Icy Trap; el éxito además reproduce la absorción hacia el jugador, informa el éxito, aplica stun y retira al monstruo con demora. Fire Trap no se usa nunca.
  - **Identidad fiel de la mascota capturada**: se conservan la especie, nombre, arquetipo de combate, familia de habilidades y calidad Common/Good/Rare/Awesome/Super durante el crecimiento y la evolución, sin convertirla en otra criatura ni inflar sus estrellas.
  - **Combate de compañeros visible para terceros**: los jugadores cercanos reciben ataques, habilidades, buffs, curaciones y cambios de HP de mascotas, invocaciones y mercenarios. Las habilidades físicas y mágicas usan su ruta visual correcta, incluido Dawn Shield sin el AoE ajeno de Wraith Hell Flame.
- **Sistema de SP (Holy Power / Lámparas de SP)**:
  - Acumulación de puntos de SP en combate hasta el tope (2000 SP / 4 lámparas), con persistencia completa al reconectar.
  - Ejecución de habilidades instantáneas de SP (`Earth Blessing V`, `Shark Shift V`, `Angel Protection`, etc.) con temporizadores de tics, regeneración de HP/MP y aumento de estadísticas.
- **Motor de Bufos, HoT y DoT**:
  - Gestión temporal de estados activos, ticks de regeneración de HP/MP, efectos de pociones y cartas de utilidad.
- **Sistema de Combate y Habilidades de Alto Nivel**:
  - **Combos multihit y ráfagas continuas**: soporte completo para habilidades encadenadas y ataques de ráfaga (fórmulas 36, 40 y 42, ej. *Rapidfire*, *Steel Rain*, *Victory Sword*, *Quake Spear*, *Strangle Strike*, *Windbreaker Arrow*). La animación de casteo/disparo del personaje se ejecuta **una sola vez** al inicio, mientras que los impactos subsiguientes impactan secuencialmente con intervalos naturales.
  - **Distribución de ráfagas en área y rebotes**: ráfagas de área (*Steel Rain*, *Sword of Kings*, *Quake Spear*, *Flaming Blade Rain*) distribuyen sus N impactos aleatoriamente entre los enemigos vivos del área (o concentran todos los impactos si hay un solo objetivo). *Windbreaker Arrow* genera un tornado inicial en área y luego 5 a 10 impactos de rebote (ricochets) a enemigos cercanos.
   - **Escalado de habilidades físicas y base en R.Atk**: las habilidades físicas escalan fielmente sobre el ataque de mano principal (R.Atk) y Stance Power (PESO_STANCE = 2.0) contra la defensa del objetivo. Los combos aplican una bonificación calibrada de +0.2x (1.2x por impacto) y los golpes únicos usan 1.35x, respetando la penalización oficial del 50% de daño contra jefes en *Rapidfire*.
  - **Delegación de habilidades de tier alto**: habilidades lanzadoras de arquero y largo alcance (fórmulas 63 y 7, ej. *TNT Arrow*, *Aparctias Shot*, *Toma Tornado*, *Windbreaker Arrow*) resuelven sus sub-hechizos de combate para heredar Stance Power auténtico, radio de explosión de área (5-6 casillas) y efectos secundarios (derribo/knockback, silencio, DoT elemental y ceguera/blind).
  - **Efectos secundarios de invocaciones y tótems**: tótems e invocaciones aplican sus auras y DoTs automáticos (ej. *Black Thorn Totem* aplica corrosión y lentitud), respetando la regla oficial de no coexistencia con *Guardian Star (Starchaos)*.
  - **Gestión de cuentas y borrado de personajes**: resolución de cierre/crash del cliente al borrar personajes mediante envío crudo de `0x0004`, junto con persistencia transparente en SQLite `cuentas.db`.
- **Equipamiento vinculado y Enchanted Fashion con Residual Times = 0**: validación de pertenencia por `char_id` (offset 53 del paquete `0x001B` / `sub_58B640` en `Angel.exe`). Si el jugador es el dueño del ítem, puede equiparlo libremente aunque le queden 0 usos restantes.
- **Venta a NPC de equipo S/Fine vinculado**: el cliente conserva esos premios como no comerciables entre jugadores, pero añade un precio de recompra de NPC equivalente a la mitad del precio de lista para que las armas y armaduras ligadas no se acumulen permanentemente.
- **Switch de armas (ranuras 11 y 12)**: alternancia rápida de conjuntos de armas con recálculo dinámico de estadísticas y bonos correspondientes.
- **Sistema de Mejoras de Equipo (Pestles, Enhanced Pestles y Piercing Hammers)**:
  - Soporte completo para mejorar y perforar (abrir huecos) en equipo de nivel 410+ utilizando las herramientas de tier 40 (40-Star Lucky Enhanced Pestle, 40-Star Lucky Piercing Hammer y morteros generales).
  - Engarce de gemas en huecos abiertos, martillo verde (reroll de stats adicionales leídos de `adv.xml`), probabilidades auténticas de éxito y bajada de nivel en caso de fallo.
- **Sistema de Banco y Almacén Personal (Self Storage)**:
  - Soporte completo para ingresar (`0x0038`) y retirar (`0x0039`) dinero del banco a través del diálogo nativo del cliente (*Sum*), con persistencia de `banco_oro` en SQLite `cuentas.db` y sincronización bidireccional en tiempo real.
  - Resolución limpia de click derecho: contenedor 16 (`usebankitem`) retira de la casilla del banco a la mochila, y contenedor 17 (`usecharitem`) deposita de la casilla de la mochila al banco sin desalineación ni cruce de slots.
  - Arrastre fluido de objetos entre banco y mochila (o reordenamiento dentro del banco) respetando ranuras auténticas (1..48 en banco, 20..163 en mochila).
- **Gestión de inventario robusta**: apilamiento de consumibles, actualización casilla por casilla con el `0x001B` oficial sin desincronizar la lectura del cliente.
- **Sistema de Casas y Espacio Privado IGG (Stage 500)**:
  - **Activación de Escrituras e Instancias**: comprar o usar escrituras de casa (10115..10117, 17934..17937) crea y activa residencias privadas en el Stage 500 (Stage Type 255) con persistencia en SQLite (`casas`, `casas_muebles`, `cuentas_casas_servicios`).
  - **Modo Amueblar y Decoración Libre**: alternancia de modo amueblar con `0x0136`/`0x0137` y salida segura con `0x0138`. Colocación, movimiento y guardado de muebles (ranuras 376..496) leídos de `furniture.xml`, con cálculo de puntuación decorativa y capacidad de sala.
  - **Copias independientes de muebles**: el inventario y los cambios de mapa comparten identificadores por copia. Guardar o retirar un mueble usa su identificador exacto y conserva las demás copias; las copias ocultas por el fallo anterior reaparecen al reconectar. El diseño y el inventario se guardan juntos.
  - **Tablón de Casas y Acceso de Visitas**: tablón residencial (`2625`) exterior e interior para entrar a la casa propia, visitar amigos o desconocidos con protección por contraseña (`0x0135`), firmas en el libro de visitas y registro de mensajes.
  - **Maid Eilian (`2603`)**: sprite auténtico (`40182`) y retrato (`182`) ubicada en `(44, 80)`. Proporciona información de la casa, bendiciones diarias (buffs 2292..2295 con bonos de EXP y combate), organización de bailes/fiestas y accesos a servicios sin expulsión involuntaria.
  - **Limpieza y Jabón Líquido**: seguimiento dinámico de limpieza con tope de 1000. El uso de jabón líquido (10118) restaura la limpieza; mantener $\ge 500$ otorga una bonificación de personaje (+1% hasta +10% de EXP multiplicador).
  - **Salas Privadas y Distribución Auténtica**:
    - Portal 701 situado en el umbral `(45, 78)` que conecta con las salas de utilidades.
    - **Raise-a-pet Room**: Máquina de Cuidado de Mascotas (`721`), Caja Fuerte / Almacén de Casa (`723`), Buzón de Suft (`262501`) en `(37, 25)` para pedidos de productor, y portal de retorno (`702`) al vestíbulo principal.
    - **Monster Hatching Room**: Máquina Incubadora de Monstruos (`731`) y portal de retorno (`703`), con mapa despejado fiel al cliente IGG oficial.
  - **Servicios de Casa y Pedidos de Productor**: depósito y retiro seguro en la caja fuerte (`house_services.py`), entregas automatizadas de suministros y materiales de producción en el Buzón de Suft (`producer_orders.py`), y consumo directo de Mercenary Token (`10581` -> buff 2254, 8 horas de duración).
  - **Permisos de Visitantes y Portal**: Si un jugador visita la casa de otro, el Portal 701 del umbral lo expulsa directamente al exterior sin mostrar el menú de salas privadas del dueño. Al interactuar con Maid Eilian (`2603`), el visitante no ve los menús de bendiciones o fichas, sino únicamente el diálogo oficial de votación de popularidad (`7897` con "Vote" `7898` e "I'm leaving" `7899`, o `7922` si ya votó hoy).
  - **Zonas de Exhibición Exterior y Restricciones de Colocación**:
    - La exhibición exterior de casas (`0x0137`) está estrictamente limitada a las zonas residenciales y urbanas oficiales: **Área de Casas de Ángeles** (Stage 370), las cuatro capitales de facción (**Aurora City** 3, **Dark City** 26, **Breeze Woods** 29, **Iron Castle** 38) y **Palm Base** (88). Se bloquea la colocación en exteriores no autorizados, mazmorras o dentro de edificios/domos (como el domo del Ocean Scholar `(278, 138)` en Palm Base).
    - Validación de espacio abierto y despejado: Aurora City queda estrictamente delimitada a la plaza central de adoquines amarillos (bloqueando aceras/veredas, mesas de café y edificios), Dark City incluye la exclusión del monumento central, e Iron Castle exige un margen mínimo de seguridad de 5 casillas respecto a todos los NPCs para garantizar que ninguna casa se monte encima ni interfiera con sus clics. Requiere una huella transitable de $5 \times 5$ casillas sin obstáculos (bloqueando puentes estrechos, escaleras, pasarelas elevadas, zonas de árboles densos o callejones), un margen de 6 casillas respecto a los bordes del mapa, distancia mínima de 7 casillas a portales/entradas y 4 casillas a otras casas exteriores.
    - Bloqueo de amueblar según visibilidad: la función de decorar (`0x0136`) se bloquea mientras la casa esté mostrada/visible en el exterior (`is_open`), y solo vuelve a permitirse cuando la casa no se está mostrando (tras pulsar *Take Back* / recoger casa con `0x0139`).
  - **Enrutamiento de Avisos al Chat (`tipo=7`) y Corrección de Prefijos (`0x000D`)**:
    - Las restricciones de colocación de casas, errores de amueblar y avisos de contraseña se envían con `tipo=7` y `MSG_TEXTO`, mostrando el texto limpiamente en la caja de chat inferior y suprimiendo por completo el letrero flotante amarillo en el centro de la pantalla.
  - **Banqueros de Ciudades y Voucher Angel**:
    - **Saludos Oficiales de Bancos por Ciudad**: Restaurados los diálogos oficiales de bienvenida de cada banco de facción: 5232 para Breeze Woods, 5228 para Iron Castle, 5230 para Dark City y 5225 para Aurora City.
    - **Guía del Banquero (Opción 5030)**: Muestra correctamente la explicación oficial del funcionamiento del almacén y las cajas fuertes (5034) en lugar de abrir el almacén prematuramente.
    - **Corrección de Banqueros en Breeze Woods**: Corregido el tipo de entidad (`npc_type: 1686`, sprite 40034) para los cinco cajeros del banco de Breeze Woods.
    - **Aparición Universal de Voucher Angel**: Añadido el NPC Voucher Angel (`npc_type: 14334`, `sprite: 40041`) junto a los bancos de las cuatro capitales de facción (Aurora City `[313, 150]`, Dark City `[165, 144]`, Breeze Woods `[313, 142]`, Iron Castle `[141, 136]`), en Palm Base (`[154, 76]`) y en Angel Lyceum (`[181, 98]`). Eliminada la restricción de `stage == 41` en `dialogos.py` para permitir canjear los Angelic Vouchers de 10M y 100M (Tienda 159) en todo el juego.
- **Sistema de Ligas y Gremios (Guild / League)**:
  - **Creación en las cuatro ciudades**: Los League Clerks en Aurora, Breeze, Iron y Dark enrutan al diálogo 5776, validando nivel 25+, rango de personaje 3+ y 60.000 de oro. Abre la ventana de creación nativa mediante `0x001D` acción 20.
  - **Sincronización en Login**: Los paquetes `0x0055` (`paquete_datos_gremio`), `0x0058` (lista de miembros) y `0x0056` (cartel de liga) se envían de inmediato al conectar (`0x0002`) sin requerir cambio de mapa.
  - **Nombre y Emblema Flotante (`0x0001`)**: Muestra el ID de logotipo oficial (byte 113) y el nombre ASCIIZ del clan (byte 114) flotando sobre la cabeza del personaje.
  - **Almacén de Liga (`0x0059`)**: Independiente del banco personal (`0x004E`). Control de permisos por rango (`GUILD_PERM_WITHDRAW_ITEM = 1`, `GUILD_PERM_WITHDRAW_MONEY = 2`), movimientos SQLite atómicos y conservación íntegra de mejoras y datos de mascota.
  - **Reputación y Subida de Rango**: Umbrales leídos de `update26/setting/level.xml` (0 a 9.375.000 de reputación en niveles 1 a 10). Aportación de materiales mediante C2S `0x004B` según `guild_contrib.xml`.
  - **Enrutamiento de Chat**: Enrutamiento directo al canal de liga 5 (`@`, `/g `, `/guild `, `/l `, `/league `) y al canal de grupo 4 (`#`, `/t `, `/team `, `/p `, `/party `).
  - **Administración GM**: Comandos dedicados `/guildlevel <1..10>` y `/guildrep <cantidad>`, totalmente aislados del nivel de personaje `/level <1..471>`.
- **Granja de Liga (Guild Farm - Stage 501)**:
  - **Control de Acceso**: Exige Nivel de Liga $\ge 6$ comprobado en el servidor; acceso por botón nativo de la UI (`0x014C`) o `/farm enter`.
  - **Instancias Aisladas y Retorno**: Instancia privada por clan `(501, 'league', guild_id)`. Se guardan las coordenadas de origen; el tornado original en `(97, 8)` devuelve al jugador al mapa y posición exactos de donde entró.
  - **Parcelas**: las 70 parcelas de tierra se envían como entidades `0x015D` (tierra seca, sprite 66902) en el píxel exacto de las marcas de `farm.mpc`. En la granja no hay NPCs: solo la tierra y el tornado de salida.
  - **Ciclo del cultivo**: se planta usando una semilla junto a una parcela libre (o con `/plant <crop_id> [plot_id]`); un cultivo por jugador a la vez. La planta pasa por las etapas del propio cliente: siembra (66907), brote (66906), creciendo (66904) y el sprite del `crops.xml` al madurar. Riego (C2S `0x014D`), abono (`0x014E`) y cosecha (`0x014F`) con los topes oficiales por cultivo y por día, y cosecha asegurada para quien sembró.
  - **Recompensas** (ayuda del juego, string.xml 3165/3166): regar da EXP, abonar da Skill EXP y cosechar da ambas más el producto, según los riegos y abonos que lleve el cultivo. Los importes son un porcentaje de lo que pide el nivel actual, así que siguen sirviendo a nivel alto.
- **Territorios y NPCs de Totem War**:
  - **Propiedad de Territorios**: Tabla `gremio_territorios`, comandos de asignación GM (`/settw <campo> <guild_id>`, `/tw`) y condiciones de scripts (28 `HAVE_GUILD_REGION`, 76 `SPEC_MAP_OWN_GUILD`, 82 `GUILD_MEMBER_TIME` $\ge$ 3 días).
  - **Totem War antigua (tótem en el campo)**: el tótem está en el propio campo (`0x012E`, formato sacado de una captura del oficial), siempre visible para todos y persistente al reconectar. Solo se le puede pegar durante la guerra y nunca la facción dueña; un campo neutral lo puede atacar cualquiera. Si lo rompe alguien sin liga, el campo queda neutral; una liga solo se queda el territorio si cumple los requisitos. El emblema de facción del cartel del tótem va por `0x0131`. Los campos de entrenamiento mantienen sus reglas (Sunflower Plain 7, Foggy Forest 20, Mysterious Garden 22, Megalith Plain 28).
  - **Ofrendas y niveles del tótem**: al pinchar el tótem de tu facción se abre la ventana oficial (`0x012F`); los materiales ofrecidos (`ofrendas_totem.json`) suman puntos y suben de nivel el tótem.
  - **Campos PvP**: los campos marcados son PvP todo el día, sin aviso. Las habilidades de área también golpean a los rivales. Las bajas cuentan en el marcador K.O. (`0x001D` código 25) y dan créditos; el caído queda como fantasma hasta revivir.
  - **Terra Keeper**: diálogo antiguo que muestra la liga dueña; League Manor desde el Heaven General lleva al Terra Keeper del campo.
  - **Heaven General (Árbol 5920)**: Presente en las 4 capitales; tienda 71 de insignias de clan (3735..3748), entrega diaria de cofres de combate/producción (3776..3783, 9255..9258, 13409..13412), sello diario 3754 y teletransporte a territorio (`GOTO_GUILD_REGION`).
  - **Terra Keeper (Árbol 5936) y Governor (Árbol 5940)**: Control de acceso a áreas de territorio (Área I stage 50, Área II stage 100, Área III stage 117, Área IV stage 377) y accesos especiales desde Thorn Wasteland (stage 16). El Governor provee banco personal, almacén de clan y Regression Scroll (3734).
- **Event Overview**: Online Bonus (minutos conectado del día, s2c `0x018A`) y Login Bonus (días conectado del mes, `0x016F`) con sus botones Receive (acción 72 / 54), idénticos byte a byte a lo que mandaba el servidor oficial al entrar. El "Go to" del Exchange (acción 73) abre la tienda de su grupo (`0x0151`). Event News abre una página local (`http://127.0.0.1:8280/news.htm`, noticias en `data/noticias.json`).
- **Angel Pass**: temporada Winter's Hymn Treasures, 60 niveles, tareas diarias y semanales (monstruos por raza, granja, captura, fusión, baile, tótem, login...), Claim / Purchase Lv / Purchase Premium Pass (acción 74, s2c `0x018C`-`0x0194`). El cliente elige la temporada con el reloj del PC entre las de su `battlepass.xml`; todas habían caducado, así que en `update26.pak` se alargan las fechas de esa temporada (pactado, como la medalla de rango).
- **Pet Amplify**: Unlock Slot (c2s `0x015D`, Amplify Hammers según `pet_inlay.xml`) y Re-Amplify todo / atributo / valor (`0x015C`); el `0x0179` de estado es idéntico al oficial. Falta meter la mascota en la casilla.
- **Regalos sin tabla de caída** (1.766, p. ej. Enchanted-Cozy Xmas Suitcase): se abren con la lista de su descripción ("Open to get:" da todo, "one of" da uno).
- **Títulos nuevos sin cambiar de mapa**: se reenvía el `0x0002` (su manejador no carga el mapa).
- **Ya no hace falta `extracted_paks`**: al arrancar, si falta, el servidor saca los `setting/*` vigentes de los `.pak` del cliente instalado (~250 MB, ~7 s, solo en local).
- **Reaparición del tótem y tótems de entrenamiento**: el tótem roto vuelve al segundo con un id de entidad NUEVO (el viejo seguía muerto en el cliente: tardaba en verse y salía sin barra de vida), con el tipo de monstruo de su nivel (`monster.xml` 21397 "Totem Lv 1", 300.000 HP ... 21404 "Totem Lv 8") y otra vez en nivel 1. Los cuatro campos de entrenamiento (Sunflower Plain, Foggy Forest, Mysterious Garden, Megalith Plain) muestran su tótem decorativo junto al Terra Keeper (posiciones de capturas de Celestia); nunca se le puede dañar.
- **Daño PvP**: fórmula separada de la de monstruos, al estilo AO `(ATAQUE - DEFENSA) x multiplicador`, con la defensa efectiva (con buffs) del rival y su reducción de daño de buffs y equipo (`物理/魔法傷害抵銷`). Los combos pegan todos sus golpes, las AoE de combo (Bullet Arrow, Steel Rain...) hacen su animación una vez y terminan en ~1,2 s, y los 71 hechizos marcados `不能對玩家施放` no dañan a jugadores. Ajuste global en `pvp_liga.FACTOR_PVP`.
- **Sistema de fusión (WND_FUSE)**: C2S `0x0147` `[modo][principal][asistente][poción][aleatorio]`, resultado por `0x001D` código 50 y vista previa de mascota por el código 51 (todo con REA). Consumibles (10 + 10 + poción), equipo (un atributo verde del asistente) y mascotas (hasta 3 bonos; transformación en una mascota nueva de la lista de `fuse.xml` con la Shape Fusion Potion 16074). El éxito de consumibles y equipo usa las fórmulas del propio cliente; el de mascotas, una fórmula suavizada (`fusion.EXITO_MASCOTA_*`).
- **Logros, títulos y reputación**: el `0x0155` real (7.204 bytes: bits de completado, % de progreso y puntuación) al entrar y en cada cambio de mapa; títulos en el `0x0002` (+0x6d0 los bits, +0x750 el puesto), ponérselo con la acción 49 / `0x001D` código 57, y un Super BC gratis la primera vez que se consigue un título. Se vigilan 3.248 de los 4.351 logros (nivel, habilidades, stats, monstruos, top del ranking, misiones, casas, fusión, mascotas, capturas, mejoras, objetos, muertes, Totem War, días conectado...). Reputación = suma del `聲望值` de los títulos; cada nivel de `prestige.xml` alcanzado suma sus stats fijas.
- **Escrituras y objetos de casa**: las escrituras (Cottage, Delicate House, Romantic Villa, Luxurious...) son el tamaño de la casa, nunca muebles: soltarlas en su casilla es como usarlas, no pueden ir a las casillas de muebles/mascotas/generadores, y un saneado al entrar arregla los personajes que quedaron mal. El Super Liquid Soap da 2.500 de limpieza (tope 5.000). Funcionan el Fly Book / Summon Book (ir junto a / traer a un compañero), el Spacious Iron Room (ventana de reparar), el Spacious Bank / Guild Bank y los pergaminos de revivir (`使用公式` 10).
- **Portales**: el paso pendiente del mapa anterior ya no dispara un portal en el mapa nuevo (South of Mirror Lake te dejaba en Spike Farm).
- **17 Mazmorras e Instancias Generadas**: 17 plantillas de mapa de instancia operativas en mapas paralelos con spawns de bosses y drops garantizados (bosses Chaos, Bashi's Gaze, ítems de misión).

**El cliente, personalizado**

El servidor deja el cliente local listo al arrancar, siempre con un `.bak` antes de tocar nada:

- **Estación del Angel Lyceum** (normal, navidad, halloween, sakura, verano). No está en
  `map041.mpc` como se creía, sino en `stage.xml`: un mapa de **decoración** (`裝飾地圖檔`) más
  el clima. Se cambia desde el launcher, con `/estacion` o con `MODO_ESTACION`
- **Nueve ranuras de habilidad** en vez de seis. Las tres extra se abren por **nivel 301, 351 y
  401**, sin Supreme Level ni misión, y se rellenan solas con una rama de oficio para ir a
  cambiarla con el Skill Angel. A quien no tenga sus seis de base no se le toca nada
- **Sin exclusión entre ramas**: las once reglas `互斥N` de `skill.xml` (Life↔Wraith,
  Chaos↔Earth, Meditate↔Enhance, Grapple↔Snipe y el trío Mantle/Garment/Vestment). El servidor
  nunca las comprobó; quien se negaba era el selector del cliente
- **Rank Promotion Medal** (83266), con los créditos que pide cada rango leídos de la columna
  `功勳` de `level.xml` y la banderola de rango (`0x0020` con `effect_id` 3)
- **Datos de recompra para equipo vinculado** aplicados desde `item.xml` hasta `item9.xml`, conservando
  el bloqueo de comercio entre jugadores y permitiendo vender los premios S/Fine elegibles a tiendas
- **Launcher** en español e inglés, con botones para abrir varias copias del cliente a la vez
- **Pantalla del logo de arranque** vaciada

**A medias**

- **Sistema Online / Presencia Multijugador**: los jugadores se ven entre sí en el mapa (`0x0001` oficial de 128 bytes), ven el movimiento ajeno en tiempo real (`0x0005`) y sincronizan transformaciones (`0x0013`) y acciones de combate de sus compañeros. Falta pulir la visualización completa de sets/skins de fashion en otros jugadores.
- **Sistema de Equipos / Teams**: el servidor detecta y recibe las solicitudes (`0x0017`), pero el flujo de aceptación, la barra de equipo en pantalla, compartir experiencia y la gestión de miembros (`0x0018`) está en fase de desarrollo.
- **Flag de Oro / Gold Cap**: implementado pero pendiente de testeo exhaustivo en cliente.
- Diálogos de NPC: 17 de los 52 del Lyceum tienen su texto y sus opciones, más expansión
  a vendedores regionales de habilidades.
- **Habilidades y magias**: las ramas de combate cuerpo a cuerpo, AoEs, invocaciones y magia están
  operativas (lanzamiento, costes, daño, buffs, debuffs, invocaciones y progresión). El arco ya
  pega a distancia con su básico (Basic Shot I, alcance 12); falta confirmar si se dibuja la
  flecha volando, porque el efecto solo se manda en las habilidades. La daga tiene menos pruebas.
- Hechizos: salen en F1-F3, se lanzan, dan buff y hacen daño, pero faltan
  algunos efectos visuales.
- La fórmula de daño físico y mágico ahora escala con mitigación lineal de
  defensa y atributos elementales, pero a niveles extremos (300+) o contra
  monstruos con estadísticas atípicas puede requerir ajustes finos de calibración.
- ~~Los combos se leen de `magic.xml` pero no se ejecutan~~ **resuelto**: los 475
  (376 directos por `連擊次數` y 99 encadenados por `轉嫁法術`) se ejecutan, y los
  golpes extra procesan la muerte del monstruo.
- El efecto de lentitud se registra pero no cambia la velocidad de movimiento.
- El bastón y el hacha usan la animación de ataque de la espada hasta que
  alguien capture la suya.
- Las monturas se equipan en la ranura 10 y sí dan velocidad, pero no la
  correcta: dos monturas distintas que declaran el mismo `move_speed` dan
  velocidades distintas en el servidor real, así que lo que aporta una
  montura depende de su propia instancia y eso no viaja en `item.xml`.

- **Sistema Integral de Misiones (1.489 quests)**:
  - Catálogo completo compilado desde `quest.xml` con 1.489 misiones y 662 repetibles.
  - Seguimiento dinámico de cacerías (877 objetivos de combate automáticos al matar monstruos en cualquier mapa con alias y nombres canónicos).
  - Objetivos de recolección e **Inventario Oculto de Misiones**: items comunes van a la mochila visible, mientras que tokens y credenciales de categoría `5001` (como *Work ID* 78179 o *Microcoin* 78180) van a las ranuras ocultas `497..556`. Confirmado con el desensamblado de `Angel.exe`: `sub_4A48C0` (ventana Prop) solo itera `20..94`, mientras que `sub_4A47E0` (HUD de seguimiento) y `sub_4A4720` (entrega al NPC) iteran `20..154` y `497..556`. Esto permite ver el progreso en pantalla (`1 / 1.`) y entregar la misión sin saturar ni mostrar tokens en la mochila del jugador.
  - Diálogos y flujo de NPCs corregidos: opciones alineadas con la UI original, comprobación de requisitos de nivel (ej. Mr. Fleming en Wise Institute nv. 380, Leif en Sandy Heights) y encadenamiento continuo de comandantes de ciudad.
  - Interacción y entrega con NPCs (más de 1.500 puntos de entrega y 1.100 NPCs asignadores).
  - Misiones repetibles y rotativas diarias/semanales.
  - Teletransporte automático a mapas de instancia / entrenamiento vinculados a quests.
  - Persistencia completa en base de datos SQLite y sincronización con el cliente vía paquetes `0x0021` y `0x0022`.
  - Abandono y entrega 100% seguros: desensamblado de `Angel.exe` (`sub_602BD0` / `0x004A5390`) y capturas oficiales (`mundo_180305_971213_orden.jsonl`) para enviar únicamente `0x0022` modo 2, eliminando crashes de `_invalid_parameter_noinfo` y protegiendo slots de mochila fuera de límites (> 60).

**No funciona**

- La ID Card dibuja al personaje en ropa interior, aunque el muñeco del mundo
  sí sale vestido. El `0x0179`, que era el último sospechoso, quedó
  descartado: sus ids son martillos, no ropa (más abajo).
- Los recursos no se recolectan, así que las nueve habilidades de recolección
  y producción no suben nunca.
- Faltan cinco NPC del Lyceum que nunca se capturaron.
- Las contraseñas **no se validan**: el bloque de autenticación sigue sin
  descifrar.
- La puerta del buceo está **documentada pero no se aplica**: los dos
  entrenadores, sus diálogos y las dos habilidades están capturados, pero el
  portal a los mapas submarinos deja pasar a cualquiera.
- Las instancias: nadie ha entrado en ninguna. **Hay cinco entradas
  identificadas y dejadas apagadas**: Nightmare Palace, Half-beast Hamlet,
  Giant Wooden Stairs (que tiene dos tornados al mismo sitio) y Chocolate
  Forest. Están en `portales.json` con su casilla y su entidad pero con el
  destino en null, y el servidor se las salta, así que pisarlas no hace nada.
  De Lost Region y Horrible Lost Region están capturados el diálogo de
  entrada, los dos modos y los mensajes de rechazo; sus monstruos se saben
  por la wiki, sus posiciones no. Ojo con una cosa: ese diálogo de dos modos
  **no** es como se entra a las instancias en general, la mayoría no pregunta
  nada.

---

## El catálogo de objetos

[`items.html`](items.html) es una sola página con **78.089 objetos**: todos
los del cliente, con su **id**, su nombre, su tipo, su grupo y su icono. Sale
del cliente extraído (UPDATE25) y de `corpus/content.db`, y no necesita
servidor ni conexión: se abre el archivo y se busca.

Existe porque el id es lo único que no se puede adivinar. El juego no lo
enseña por ningún lado, y lo que reparte objetos pide el id y nada más, así
que cualquiera que eche una mano con drops, tiendas o pruebas acaba pidiendo
los mismos números una y otra vez. Esto los junta en un sitio.

La página pesa unos 19 MB porque el catálogo entero viaja dentro, como un
array JSON que se filtra en el navegador. Es a propósito: aquí vale más un
archivo suelto que funciona sin nada detrás que uno más pequeño que necesite
algo levantado.

`GM_ITEM_COMMAND_FOR_AI.md` es la especificación del comando que usaría esos
ids dentro del juego, escrita para dársela a una IA. **Todavía no está
implementado**: el archivo dice qué reutilizar de `app.py` y cómo debe leerse
el comando, y el servidor no tiene nada de eso.

---

## Las tres zonas que salieron de otro sitio

Todo el resto del proyecto sale de capturas de **un solo** servidor privado.
Veinte mapas no. Salen de **un segundo servidor, con otra versión del
cliente**, y conviene saber por qué y qué implica:

- **Night City Code**, los stages 416 a 421 — Clink Harbor, Neon Sky Corridor,
  Black Market District, Commercial Street, Bling Plaza y Ultimate Arena
- **Sun Sea Maze**, los stages 397 a 402 — Floating Station, Floral Alley,
  Majestic Mansion, Warm Villa, Verdant Shrine y Seaside Grotto
- **Cybertronica**, los stages 405 a 410 — Sandy Heights, Wise Institute,
  Clank Oasis, Ironbone Works, Machinery Ruins y Steely Circuit
- **Training Area A y B**, los stages 118 y 134

Las tres zonas comparten el mismo motivo, contado aquí abajo con Night City
Code porque es donde se descubrió primero: en el servidor principal los
escenarios existen pero llegan vacíos. Seaside Grotto trajo además algo que no
estaba en ningún otro sitio, un teletransporte que no es un portal: se le
**habla** a una estatua y te mueve al otro lado del mapa. Ese mecanismo está
descrito más abajo.

### Por qué hizo falta otro servidor

El mapa estaba en los datos del cliente desde el parche 25, y un tornado de
Niro River llevaba hasta él. Pero al cruzarlo, el servidor mandaba **7
entidades y nada más**, todas NPC, todas amontonadas en la esquina (1..6,
1..5). Es la firma de un escenario **declarado pero sin poblar**: existe en la
tabla, no tiene contenido. El portal quedó medido pero desactivado, con una
nota que decía «activarlo cuando alguna versión traiga el mapa poblado».

El segundo servidor corre esa versión. Al cruzar el mismo tornado, su
servidor manda **171 entidades** repartidas por todo el mapa, con monstruos de
verdad. El mapa existe; lo que faltaba era un servidor que lo sirviera.

### Qué se tomó y qué no

Sigue valiendo la regla de siempre: **se toman los DATOS, nunca los bytes
crudos**. Aquí se pudo porque los dos hablan lo mismo donde importa: el
`0x0008` de spawn mide **63 bytes en las dos versiones**, con los campos en los
mismos sitios, y el `MOVE_REQ` también. Se decodifica con el mismo código.

Donde **no** coinciden, y hay que tenerlo presente:

- El `0x000C` de cambio de mapa llega de **20 bytes sin la cadena de IP** que
  lleva el nuestro. El stage se lee igual, en el offset 0, pero el puerto de
  destino ya no está donde lo esperamos
- Aparecen **tres mensajes que no conocemos**: `0x018A`, muy frecuente y casi
  siempre de ocho bytes; `0x006D`, con el cuerpo vacío; y `0x0142`, de un solo
  byte. Ninguno está en `proto/messages.py`

Los nombres vienen en **Big5**, no en inglés. No hubo que traducir nada a mano:
el `npc_type` es el mismo en las dos versiones y nuestro `content.db`, sacado
de los XML del cliente, ya trae el nombre inglés de cada id. Se cruza por ahí.

### Dos cosas que cambiaron en las herramientas

**`tools/separar_por_mapa.py`** (nueva). En el otro servidor cada cambio de
mapa abría conexión nueva, así que cada archivo de captura era de un solo mapa.
Aquí el `0x000C` llega **dentro de la misma sesión**: una sola conexión trajo
seis mapas seguidos. Pasársela entera a `poblar_mapa.py` metería los bichos de
un mapa en la plantilla de otro, en silencio. Esta herramienta corta por cambio
de mapa antes de poblar.

**`tools/poblar_mapa.py`** decodificaba los nombres como ASCII y con Big5
quedaban ilegibles. Ahora decodifica Big5 —que es compatible con ASCII, así que
lo anterior no cambia— y además cruza el `npc_type` contra `content.db` para
dejar el nombre en inglés.

### Lo que se aprendió de paso

**Hay pasos de mapa sin tornado.** Cinco de los trece portales de la cadena no
tienen ningún objeto dibujado: se camina hasta la casilla y se cambia de mapa,
sin que se vea nada. Está comprobado en el juego y en la captura, donde no hay
ningún objeto cerca. **Qué dispara el cambio no se sabe**; podría ser un portal
invisible. Se llamaron «cruce por borde» al principio y era una suposición
equivocada: los mapas miden 300×180 y esas casillas están a unas ocho del
borde, con entidades incluso más allá.

**Un mapa puede necesitar varias pasadas.** Commercial Street dio 71 monstruos
en el primer recorrido, 109 en el segundo y 125 en el tercero. No cambió el
mapa: una captura solo trae lo que se tuvo a la vista, y las primeras pasadas
dejaron zonas sin cubrir.

**Un teletransporte que no es un portal.** En Seaside Grotto no se pisa un
tornado: se le **habla** a una estatua. El clic llega como `0x0005`, el
servidor contesta un diálogo `0x0012` con dos opciones, el cliente manda
`0x000B` con `0a` —el índice 0, «Yes»— y después llega un `0x0003` pelado que
mueve al personaje. No hay `0x000C`, así que el mapa no se recarga. Costó dos
lecturas equivocadas: primero se culpó al `0x000F` que sale justo detrás del
diálogo, y ese aparece 95 veces por sesión porque es un latido. La vuelta no
es un clic —se pisa el tornado— y manda solo el `0x0003`, sin el `0x0016` ni
el `0x0012` que sí llevan los saltos internos de otros mapas.

### Lo que falta de esta región

El stage **422 (Secret Peak)** sigue sin poblar. Quedan además la **entrada de
instancia** de Bling Plaza, identificada por el `jumpmap.xml` —es el único de
los nueve destinos de la cadena que lleva una clase extra— y **tres tornados
de Ultimate Arena** que no dejaron pasar, probablemente por algún requisito de
misión o de nivel.

---

## Qué hace falta para levantarlo

El repo es **autosuficiente**: trae las 435 plantillas de mapa, `content.db`,
`AO.db` y las tablas derivadas del cliente. **No hace falta `extracted_paks/`**,
que no se publica porque es material con copyright de IGG.

Comprobado extrayendo `HEAD` a una carpeta limpia y ejecutándolo desde ahí. Lo
que dependía de `extracted_paks` se movió a plantillas: los cortes de crédito
de cada rango (`creditos_rango.json`), el `skill.xml` sin exclusiones
(`skill_sin_exclusion.xml.zlib`) y los mapas de decoración de las estaciones
(`mapas_estacion/*.zlib`).

El **cliente va aparte**, no en el repo.

---

## Cómo ejecutarlo

Hace falta **Python 3.10 o superior** y el cliente de Angels Online
instalado. Probado con el cliente **8.5.1.0**; las capturas de las que sale
el protocolo se tomaron con un **8.6.0.8**, y los dos hablan lo mismo.

IGG cerró el juego en febrero de 2026, así que el cliente ya no se puede
descargar de ellos. Esta es la copia con la que se desarrolla y se prueba
este proyecto:

**[Cliente de Angels Online 8.5.1.0](https://drive.google.com/file/d/13IOcTJUkX7LfsznZ8tobyu5c5MuXjpZK/view?usp=sharing)**

Es el cliente de IGG, sin modificar. Está aquí porque un protocolo que no se
puede ejecutar contra nada no sirve de mucho, y porque sin él no se puede
reproducir ninguna de las mediciones de este repositorio.

1. Apuntá el cliente a tu máquina. En su `server.xml`:

   ```xml
   <伺服器 名稱="Local" 編號="16" 選擇="100"
           ip="127.0.0.1" port="16768" 分流="2"
           fip="127.0.0.1" fport="21238" />
   ```

2. Arrancá el servidor:

   ```
   ./correr_servidor.sh        # Linux, macOS, Git Bash
   correr_servidor.bat         # Windows
   ```

3. Abrí el cliente y entrá con cualquier usuario. La cuenta se crea sola.

El servidor deja cada sesión grabada en `logs/sesiones/`, que es lo que se usa
para depurar.

### Variables de entorno

| Variable                | Para qué sirve                                           |
| ----------------------- | -------------------------------------------------------- |
| `AO_TILE`               | Punto de aparición en Guide Palace (por defecto `82,83`) |
| `AO_TILE_LYCEUM`        | Punto de aparición en el Lyceum (`152,74`)               |
| `AO_DURABILIDAD`        | Multiplica la durabilidad de lo que entrega el servidor  |
| `AO_SECUENCIA_COMPLETA` | Manda la captura de entrada entera, para comparar        |

---

## Cómo está organizado

```
proto/        el protocolo: framing, cifrado, códec de mensajes, LZO
server/       el servidor: login, mundo, inventario, combate, diálogos
server/plantillas/   bloques medidos de tráfico real, en JSON
tools/        proxy de captura y herramientas de análisis
docs/         TODO lo que se averiguó, con cómo se verificó
```

**Leé `docs/01_HECHOS_VERIFICADOS.md` antes de tocar nada.** Son 1750 líneas
con cada hallazgo, cómo se comprobó, y los errores que se cometieron por el
camino con su diagnóstico. Esa última parte vale más que el código: varias
cosas se dieron por buenas con una sola muestra y resultaron falsas.

---

## Las cuatro tablas que estaban escondidas en el cliente

Cuatro sistemas se estuvieron adivinando durante días hasta que el dato
aparecio dentro de los `.pak` del propio cliente. Ninguno necesitaba una
formula: son tablas, y las suposiciones estaban todas mal.

**`adv.xml` -- lo que puede dar el martillo verde.** 2645 filas, por parte y
nivel, con un minimo y un maximo de cada stat. Antes de esto se ajustaron
dos formulas a unas capturas de pantalla y las dos estaban mal; lo que las
tumbo fue usar el mismo martillo en dos piezas y ver que daban rangos
distintos. La tabla cuadra exacta con el juego: un baston de nivel 300
ofrece 344 de HP, 2428 de ataque, 697 de ataque magico y 30 de agilidad,
que es justo lo que enseñaba el cuadro del cliente. Y ademas fija la forma
del asunto: un arma nunca saca defensa, una armadura nunca saca ataque,
solo una montura saca velocidad, y solo una mochila saca peso y casillas.

**`pet.xml` -- 1751 mascotas.** Sprite, id de tipo, nombre, con que clase de
`petattrib` se sacan sus stats, su etapa de evolucion y sus dos ramas. El id
de tipo iba en cero, y sin el el cliente no sabe que mascota esta mirando:
la ventana salia sin nivel y sin dibujo. Las trece parejas sprite/tipo que
se vieron en las capturas cuadran todas.

**`petaspect.xml` -- las escenas de crianza.** 107, con tres opciones cada
una, de -3 a +3. El texto cuadra con el del juego palabra por palabra.

**`jeweleffect.xml` -- que hace una gema.** 870 filas. Los numeros estan en
la propia gema y esta tabla dice sobre que stat caen, y eso depende de donde
se engarce: la misma runa da ataque magico en un arma y defensa magica en
una armadura.

## Fallos conocidos

### La ficha de la mascota no se guarda

Todo lo demás de las mascotas funciona: la entrada de inventario de 231
bytes, la ventana con sus stats de verdad, sacarla y guardarla, renombrarla,
la experiencia, subir de nivel y el árbol de evoluciones entero. Pero su
ficha vive solo en memoria, así que vuelve al nivel 1 en cada reconexión. El
objeto de la mochila sí persiste; lo que la mascota se ha vuelto, no.

### El contador de crianza no se puede leer

Cuando la mascota sube de nivel el cliente enseña una escena con tres
opciones y avisa de que "(Your act affects Pet's growth)". Ese texto no
viaja por la red: el cliente saca la escena de su propio `petaspect.xml` y
de vuelta solo llega la opción elegida, en el `c2s 0x003E` con los valores
4, 5 y 6 -- el mismo mensaje que lleva las órdenes con 0, 1 y 2.

Así que el servidor nunca se entera de a qué escena se respondió, y por eso
no puede saber cuánto valía la respuesta. Cada una de las 107 escenas tiene
sus tres valores, de -3 a +3. Para cerrarlo, el servidor tiene que elegir él
la escena y recordarla, en vez de dejar que la elija el cliente.

### La ID Card dibuja al personaje desnudo

El muñeco que camina por el mundo lleva su equipo bien, pero la figura del
panel de la ID Card sale en ropa interior. Ahí el arma y los zapatos **sí**
se dibujan; la que no se aplica es la prenda del cuerpo.

**El último candidato quedó descartado (30/09/2026).** El `0x0179` se
llevaba tiempo arrastrando como el mensaje que faltaba por mandar, con sus
ids `40287..40295` tomados por sprites de ropa. No lo son: esos nueve
números están literales en `setting/pet_inlay.xml`, con el mismo orden y la
misma agrupación de tres en tres, y el ALIAS del archivo los llama
`ItemID` con `Priority1/2/3`. Cruzados contra `item.xml` resultan ser
**martillos** — Hammer, Attribute Hammer y Value Hammer, con sus variantes
normal, untradable y de un día. El `0x0179` es una lista de objetos por
prioridad para engarzar, es una tabla estática igual para todos, y no
dibuja nada.

Con eso caen los cuatro candidatos que había: `0x0149`, `0x0179`, la ficha
`0x0002` y la correlación del requisito de habilidad. El mensaje que
redibuja la figura **no está en nada de lo capturado hasta hoy**, así que
sigue haciendo falta una captura con la ID Card **abierta** quitándose y
poniéndose una prenda del cuerpo. Lo que ya no hace falta es buscar la
tabla item → sprite: no existía.

### La fórmula de daño se va a nivel alto

`ataque x 33 / (33 + defensa)` cuadra con lo que hace un personaje de nivel
bajo. A nivel 118 se equivoca por un factor de unas 75 veces. La relación
resultó ser lineal en la defensa en vez de multiplicativa, con una pendiente
que depende de los niveles en juego, y no hay muestras suficientes de varios
rangos de nivel para fijarla.

### La animación de ataque del bastón y el hacha

El `0x000A` lleva un tipo y un número de animación, y el par depende del arma.
Medido siguiendo los cambios de equipo dentro de cada sesión:

| arma                  | tipo | animación |
| --------------------- | ---- | --------- |
| espada, daga          | 3    | 1480      |
| lanza                 | 2    | 827       |
| bastón                | 2    | 951       |
| dos armas de una mano | 2    | 832       |

El número no es una duración: la lanza pega más lento que la espada y sin
embargo su número es menor. Lo que hace es elegir qué animación reproduce el
cliente, así que mandar el equivocado hace que la lanza ataque como si
llevaras dos armas y ni se vea el arma. El bastón y el hacha todavía caen en
el par de la espada, así que una captura de alguien atacando con ellos
completaría la tabla.

### Fotos de fallos ya resueltos

Las imágenes de `docs/capturas/` se conservan como registro. Los cinco están
resueltos: el panel de habilidades y los hechizos de F1-F3, los diálogos y el
movimiento de los NPC, abrir cajas, la tienda y los portales del suelo.

---

## Lo que está saltado a propósito

Para que el servidor arranque sin una base de datos ni un registro, hay cosas
que no se comprueban. No son fallos, son decisiones:

**Las cuentas se crean solas.** Entrás con cualquier usuario y queda guardado
en `data/cuentas.json`. Si querés preparar una a mano, es un JSON normal:

```json
{
  "cuentas": {
    "tuusuario": {
      "password": "loquesea",
      "personajes": []
    }
  }
}
```

**La contraseña NO se valida.** Entra cualquiera. El usuario sí se lee del
mensaje de autenticación, pero el bloque donde viaja la contraseña no está
descifrado, así que no hay con qué compararla. Se intentó dos veces dar con el
campo y las dos salieron mal: una rechazaba logins válidos y la otra aceptaba
todo porque el offset resultó ser una constante del cliente. Está documentado
en `server/cuentas.py`.

**No hay registro, ni correo, ni recuperación.** Es un servidor local.

### Fallos visuales al reconectar

Algunas cosas se ven mal hasta que salís y volvés a entrar. El servidor y el
cliente terminan de acuerdo, pero el cliente no refresca en el momento:

- Al cambiar de mapa, la música se corta
- El panel de equipo puede quedar con una casilla dibujada de más

No corrompen nada: lo que hay en `data/cuentas.json` es siempre lo correcto.

---

## Cómo ayudar

Lo que más falta no es programación: son **capturas**.

Casi todo lo que no funciona es porque no se grabó nunca. El proxy se pone
entre el cliente y un servidor que funcione, y deja el tráfico de los dos
sentidos con marca de tiempo:

```
python tools/proxy.py --server-xml "ruta/al/server.xml"
# jugás un rato haciendo lo que se quiere capturar
python tools/proxy.py --server-xml "ruta/al/server.xml" --restaurar
python tools/correlacionar.py --novedades
```

Dos consejos que costaron varias rondas aprender:

- **Una captura solo trae lo que tuviste a la vista.** Para poblar un mapa hay
  que recorrerlo entero, no pararse en un punto.
- **Dejá un par de segundos entre acción y acción.** Si se amontonan, no hay
  forma de saber qué respuesta corresponde a qué pedido.

Lo que haría falta ahora, por orden de utilidad:

1. **Equipar una prenda del cuerpo con la ID Card abierta**, para aislar el
   mensaje que redibuja la figura. Sigue siendo la primera de la lista: con
   el `0x0179` ya descartado no queda ningún candidato en lo capturado.
2. **Elegir opciones de diálogo** en varios NPC distintos. Con cinco o seis
   casos se llenan los 35 NPC del Lyceum que siguen sin texto.
3. **Recolectar un recurso** con la herramienta equipada. De eso dependen
   nueve habilidades y hoy ninguna puede subir.
4. **Una pelea larga contra monstruos de varios niveles**, anotando el nivel
   de los dos bandos, para fijar la fórmula de daño.
5. **Atacar con bastón y con hacha**, para terminar la tabla de animaciones
   de ataque (espada, lanza y dos armas ya están medidas).

### Aportes de cualquier tipo

Sirve todo, no hace falta saber de ingeniería inversa:

- **Capturas de tráfico.** Es lo que más falta. Ver arriba.
- **Código.** Los pull request son bienvenidos. Si tocás el protocolo, decí
  contra qué lo comprobaste: el proyecto se apoya en que cada afirmación tenga
  su verificación detrás.
- **Datos del cliente.** Si encontrás algo en los `.xml` o los `.pak` que acá
  se dio por imposible, decilo. Ya pasó dos veces que el dato estaba ahí.
- **Reportes de fallos.** Con el log del servidor y qué hiciste en el cliente
  alcanza. Si podés, el `logs/sesiones/` de esa partida ayuda mucho.
- **Traducciones.** La documentación está en español.
- **Probar y contar qué se rompe.** Media hora jugando encuentra cosas que no
  aparecen leyendo el código.

Si no sabés por dónde empezar, abrí un issue y preguntá.

Antes de grabar nada, mirá si el dato ya está en los XML del cliente. Pasó dos
veces: los puntos de aparición estaban en `jumpmap.xml` y los diálogos en
`msg.xml`, y se pidieron capturas para cosas que ya estaban en el disco.

---

## Créditos

Este servidor se escribió desde cero, pero no se empezó de la nada.

- **[AngelsOnlineDev/AO](https://github.com/AngelsOnlineDev/AO)** — el proyecto
  que abrió el camino. No se copió código de ahí, pero sí se estudió, y de
  mirar su log salió el hallazgo que destrabó todo el proyecto: que el
  redirect al mundo va **en respuesta al `0x0006`**, no después de la
  autenticación. Se estuvo semanas atascado en esa pantalla comparando bytes
  que ya eran correctos; el problema era el momento, no el contenido.
- **Squirrel**, de RageZone — por intentarlo antes y dejar rastro. Que alguien
  haya empezado y documentado algo, aunque no llegara al final, ahorra el
  trabajo de averiguar por dónde ni siquiera vale la pena entrar.

Y a quien haya conservado el cliente y sus `.pak`. Sin ellos no habría nada
que reconstruir: buena parte de lo que aquí funciona salió de leer los `.xml`
del propio juego, no del tráfico.

---

## Aviso

Angels Online es propiedad de IGG. Esto es trabajo de preservación de un juego
que ya no existe, hecho sobre un cliente que cualquiera puede instalar.

**No se incluye nada de IGG**: ni el cliente, ni sus datos, ni el binario
descompilado. El servidor lee los `.xml` y los `.pak` del cliente que ya tengas
instalado; sin él no funciona y no sirve de nada.

**Tampoco se incluyen capturas de tráfico.** Las que se usaron llevaban nombres
de cuenta y chat público de otras personas. El análisis está en `docs/`; los
bytes crudos no hacen falta para nada. Si aportás capturas, revisá lo mismo
antes de subirlas.
