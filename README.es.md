# Servidor local para Angels Online

*[English](README.md) · **Español***

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

## Estado real

**Funciona**

- Login, creación, selección y borrado de personaje, con persistencia en disco
- Entrada al mundo, movimiento, cambio de mapa y portales del suelo
- El tutorial de Angel Raphael: elegir clase, recibir el equipo y el traslado
- Inventario con **cantidades**: los consumibles se apilan, y equipar,
  desequipar y mover entre casillas se contesta casilla por casilla, como
  hace el servidor real
- Tiendas: comprar **varios objetos y varias unidades de una vez**, vender,
  separar un montón y destruirlo. Los precios de compra y venta salen de
  `item.xml`, y el total de una venta coincide con el capturado al oro
- Usar consumibles: las pociones y la comida devuelven HP y MP y gastan una
  unidad
- Stats calculados desde `item.xml` (el equipo suma de verdad), incluido el
  peso que se carga
- Combate: pegar y recibir, números de daño, críticos, armas duales, efectos
  de ataque, morir y revivir, botín, experiencia y experiencia de habilidad
- Monstruos: cadencia de ataque propia de cada uno, persecución, paseo,
  reaparición y efectos de sangrado y aturdimiento
- **95 mapas poblados a partir de capturas**: 14.917 monstruos, 1.149 NPC y
  8.951 objetos de mapa, 5.029 de ellos con su recurso identificado. Cada
  monstruo, NPC y recurso sale de una captura; nada está inventado
- **Hay zonas enteras cerradas**, es decir con todos sus tornados cruzados y
  medidos: **Heart of Eden**, **Floating** (6 mapas), **el anillo del
  desierto** (Crescent Valley, Desert Racetrack, Ghost Village, Troop
  Outpost, Ancient Front, Fantastic Sand City, Nightmare Palace) y
  **Candyland** (7 mapas). **Atlantis está completo salvo las instancias**, y
  a la cadena del bosque (de Cryptic Moon Swamp a Giant Wooden Stairs, 8
  mapas) solo le quedan dos tornados. Más buena parte de Pharaoh, East Orient
  y los territorios de las cuatro facciones
- **208 portales**, casi todos medidos en los dos sentidos: la casilla del
  tornado sale de la captura, y también aquella donde el servidor real deja
  al jugador al cruzar. La mayoría se cruzaron **dos veces en cada sentido**,
  que es como se descubrió que algunos portales no dejan siempre en la misma
  casilla
- **El Angels GO!, el teletransporte de las Superwing**, funciona: el `0x0151`
  lleva el id de la tabla `jumpmap.xml` del propio cliente, se gasta una
  Superwing y la respuesta se bifurca, con las dos ramas medidas: un `0x0003`
  si el destino está en el mapa donde ya estás, y un `0x0007` más `0x000C` si
  es otro mapa. La tabla tiene **355 destinos** y **140 están activos**, los
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

**A medias**

- Diálogos de NPC: 17 de los 52 del Lyceum tienen su texto y sus opciones
- **Las habilidades solo están probadas de verdad en tres ramas: espada,
  lanza y hacha/martillo (Warrior)**, y ahí a medias -- se lanzan, pegan y
  dan buff, pero falta bastante. Las **ramas de magia (Life, Wraith, Chaos,
  Earth) no están probadas**: un jugador avisó de que a un mago le fallaron
  los hechizos, y eso todavía no está diagnosticado. Arco y daga tampoco se
  han probado. Si vas a probar el servidor, juega una clase cuerpo a cuerpo
- Hechizos: salen en F1-F3, se lanzan, dan buff y hacen daño, pero faltan
  algunos efectos visuales
- La fórmula de daño aguanta a nivel bajo y se va mucho a nivel alto: resultó
  ser lineal en la defensa, y los coeficientes dependen del nivel de los dos
  bandos
- Los combos se leen de `magic.xml` pero no se ejecutan
- El efecto de lentitud se registra pero no cambia la velocidad de movimiento
- El bastón y el hacha usan la animación de ataque de la espada hasta que
  alguien capture la suya
- Las monturas se equipan en la ranura 10 y sí dan velocidad, pero no la
  correcta: dos monturas distintas que declaran el mismo `move_speed` dan
  velocidades distintas en el servidor real, así que lo que aporta una
  montura depende de su propia instancia y eso no viaja en `item.xml`

**No funciona**

- La ID Card dibuja al personaje en ropa interior, aunque el muñeco del mundo
  sí sale vestido (más abajo)
- Los recursos no se recolectan, así que las nueve habilidades de recolección
  y producción no suben nunca
- Faltan cinco NPC del Lyceum que nunca se capturaron
- Las contraseñas **no se validan**: el bloque de autenticación sigue sin
  descifrar
- Las misiones y si se habló con Michael **no se guardan en disco**: duran lo
  que dura la sesión y se pierden al reconectar
- La puerta del buceo está **documentada pero no se aplica**: los dos
  entrenadores, sus diálogos y las dos habilidades están capturados, pero el
  portal a los mapas submarinos deja pasar a cualquiera
- Las instancias: nadie ha entrado en ninguna. **Hay cinco entradas
  identificadas y dejadas apagadas**: Nightmare Palace, Half-beast Hamlet,
  Giant Wooden Stairs (que tiene dos tornados al mismo sitio) y Chocolate
  Forest. Están en `portales.json` con su casilla y su entidad pero con el
  destino en null, y el servidor se las salta, así que pisarlas no hace nada.
  De Lost Region y Horrible Lost Region están capturados el diálogo de
  entrada, los dos modos y los mensajes de rechazo; sus monstruos se saben
  por la wiki, sus posiciones no. Ojo con una cosa: ese diálogo de dos modos
  **no** es como se entra a las instancias en general, la mayoría no pregunta
  nada
- Los equipos y la lista de amigos: el protocolo está documentado desde una
  captura con dos cuentas, pero el servidor todavía no implementa ninguno

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

| Variable | Para qué sirve |
|---|---|
| `AO_TILE` | Punto de aparición en Guide Palace (por defecto `82,83`) |
| `AO_TILE_LYCEUM` | Punto de aparición en el Lyceum (`152,74`) |
| `AO_DURABILIDAD` | Multiplica la durabilidad de lo que entrega el servidor |
| `AO_SECUENCIA_COMPLETA` | Manda la captura de entrada entera, para comparar |

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

## Fallos conocidos

### La ID Card dibuja al personaje desnudo

El muñeco que camina por el mundo lleva su equipo bien, pero la figura del
panel de la ID Card sale en ropa interior. Ahí el arma y los zapatos **sí**
se dibujan; la que no se aplica es la prenda del cuerpo.

Tres candidatos quedaron descartados por medición, para que nadie los repita:
el `0x0149` es byte a byte idéntico siempre, el `0x0179` sale igual después
de cada equipado sin importar qué te pongas, y la ficha `0x0002` no contiene
ningún id del equipo — dos logins del **mismo** personaje con equipo distinto
se diferencian en sólo 56 bytes, y todos son stats y nivel.

Lo que lo resolvería es una captura hecha con la ID Card **abierta**,
quitándose y poniéndose una prenda del cuerpo.

### La fórmula de daño se va a nivel alto

`ataque x 33 / (33 + defensa)` cuadra con lo que hace un personaje de nivel
bajo. A nivel 118 se equivoca por un factor de unas 75 veces. La relación
resultó ser lineal en la defensa en vez de multiplicativa, con una pendiente
que depende de los niveles en juego, y no hay muestras suficientes de varios
rangos de nivel para fijarla.

### La animación de ataque del bastón y el hacha

El `0x000A` lleva un tipo y un número de animación, y el par depende del arma.
Medido siguiendo los cambios de equipo dentro de cada sesión:

| arma | tipo | animación |
| ---- | ---- | --------- |
| espada, daga | 3 | 1480 |
| lanza | 2 | 827 |
| bastón | 2 | 951 |
| dos armas de una mano | 2 | 832 |

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
   mensaje que redibuja la figura.
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
