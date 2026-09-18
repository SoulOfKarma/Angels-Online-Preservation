# Prueba con el cliente real

## La idea

**No apuntes a que funcione: apunta a que falle de forma legible.**

El primer intento va a fallar en algun punto -- hay diez mensajes que se envian
como plantilla sin entenderlos, y seguro alguna suposicion esta mal. El valor
esta en saber **exactamente donde**.

Por eso el servidor **graba toda la sesion** en `logs/sesiones/`, en el mismo
formato que `logs/raw_streams/`. Sobre esa grabacion corren las mismas
herramientas que se usaron con las capturas reales.

## Antes de empezar

El `server.xml` del cliente ya apunta bien:

```xml
ip="127.0.0.1" port="16768"  fip="127.0.0.1" fport="21238"
```

Hacer una copia igual, por las dudas:

```
copy "C:\AO\Angels Online\server.xml" "C:\AO\Angels Online\server.xml.bak"
```

## Correr

```
correr_servidor.bat
```

o bien:

```
python server/app.py -v
```

Abre dos puertos:
- **16768** servidor de juego
- **21238** servidor de archivos (todavia no responde, pero **graba lo que el
  cliente pide**, que es justo lo que hace falta para implementarlo)

Despues, arrancar el cliente normalmente.

## Que mirar

En el log del servidor:

| linea | significado |
|---|---|
| `conectado clave=...` | el cliente abrio la conexion |
| `grabando sesion -> ...` | donde queda la grabacion |
| `0x0002 AUTH` | el cliente mando credenciales |
| `entro al mundo: entidad N` | se emitieron los 21 mensajes |
| `opcodes SIN ESQUEMA` | **lo importante**: lo que no sabemos interpretar |

Del lado del cliente, si se cae deja `error.log` y `err*.dmp` en
`C:\AO\Angels Online\`. Los dos sirven.

## Despues de la prueba

```
python tools/diagnosticar.py
```

Reconstruye el dialogo completo en orden, marca cada mensaje del cliente que no
sabemos interpretar, y señala en que punto se corto.

## Los tres desenlaces posibles

**A. El cliente no manda nada tras el Hello.**
Rechazo en el handshake. Revisar el formato del Hello, o que el cliente espere
conectarse antes a otro puerto. El diagnostico lo dice explicitamente.

**B. Manda la autenticacion y despues corta o se cuelga.**
El mejor caso: el handshake sirve y falla algo de la secuencia de
inicializacion. `diagnosticar.py` muestra hasta donde llego.

**C. Entra y se ve algo.**
Aunque salga mal dibujado, es la senal de que la cadena completa funciona.
A partir de ahi se corrige por observacion.

En los tres casos **queda la grabacion**, y sobre ella se puede trabajar igual
que con las capturas del servidor real.

## Que NO esperar

- El servidor **no valida credenciales**: acepta cualquier autenticacion.
- **No hay mapa**: los datos estan en `corpus/content.db` pero no se sirven.
- **No hay otras entidades**: ni NPCs ni monstruos.
- El movimiento se confirma, pero **sin colisiones ni validacion**.
- El servidor de archivos **no responde**, solo registra los pedidos.
