# Servidor local para Angels Online

*[English](README.md) · **Español***

Reconstrucción del protocolo de red de **Angels Online** (IGG, cerrado en
febrero de 2026) y un servidor que lo habla, hecho por ingeniería inversa del
cliente y de capturas de tráfico.

No es un emulador completo. Es el **protocolo documentado** y un servidor que
llega hasta donde llega: se crea un personaje, se hace el tutorial, se elige
clase, se pelea y se compra. Lo que falta está listado abajo, sin adornos.

---

## Estado real

**Funciona**

- Login, creación y selección de personaje, con persistencia en disco
- Entrada al mundo, movimiento y cambio de mapa
- Tutorial de Angel Raphael: elegir clase, recibir el equipo y el traslado
- Inventario completo: equipar, desequipar, mover entre casillas, durabilidad
- Stats calculados desde `item.xml` (el equipo suma de verdad)
- Compra en tiendas
- Angel Lyceum poblado: 52 NPC, 81 monstruos y 158 recursos en su sitio
- Combate: pegar, recibir, ver el número de daño, matar y cobrar el botín
- Diálogos de NPC con sus opciones

**No funciona**

- Los NPC no se mueven ni reaccionan; los monstruos no atacan por su cuenta
  ni reaparecen al morir
- Elegir una opción de diálogo cierra el cuadro en vez de continuar
- No hay experiencia ni subir de nivel
- Los recursos no se recolectan
- No se pueden borrar personajes
- Las zonas de teletransporte del suelo no funcionan (el cambio de mapa sí,
  pero hay que dispararlo desde el servidor)
- 35 de los 52 NPC del Lyceum siguen sin diálogo
- La contraseña **no se valida**: el bloque de autenticación no está descifrado

---

## Cómo ejecutarlo

Hace falta **Python 3.10 o superior** y el cliente de Angels Online instalado.

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

1. **Elegir opciones de diálogo** en varios NPC distintos. Con cinco o seis
   casos se resuelve la tienda y el punto de reaparición.
2. **Borrar un personaje** que ya haya pasado su período de protección.
3. **Cruzar una zona de teletransporte** del suelo.
4. **Recolectar un recurso** con la herramienta equipada.
5. **Subir de nivel** y ver qué manda el servidor.

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
