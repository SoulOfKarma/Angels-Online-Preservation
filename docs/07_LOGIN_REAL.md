# Login: lo que se logro y donde esta el bloqueo

Estado al cierre de la sesion del 18/09/2026.

## Funciona de punta a punta

| etapa | estado |
|---|---|
| handshake y cifrado | OK |
| autenticacion | OK (sin validar clave, ver abajo) |
| lista de personajes | OK, 3 ranuras |
| **creacion de personaje** | **OK, persiste en data/cuentas.json** |
| stats correctos | HP 205/205, MP 154/154, Guide Palace (51) |
| servidor de avatares | OK |
| redirect | OK, byte a byte identico al real |

## El bloqueo

**El cliente NO intenta conectar al servidor de mundo.** Medido: se abrieron
30 puertos señuelo y ninguno recibio conexion. No es que conecte y falle: no
conecta.

## Lo verificado contra trafico real

Se capturo una sesion completa de un servidor VIVO con `tools/proxy.py`
(que reescribe el redirect para que la sesion de mundo tambien pase por el).
Con eso se comparo byte a byte:

- **bloque de cuenta (0x0000, 656 B)**: identico salvo lo propio del personaje
  (nombre, char_id, clase, HP/MP) y del servidor (sub-canal).
- **redirect (0x0004, 30 B)**: identico salvo token aleatorio, IP y puerto.

O sea el problema NO esta en lo que el servidor manda durante el login.

## Correcciones que salieron de esa comparacion

1. **Tamano del bloque**: 656 B, no 654 (era una estimacion heredada).
2. **Indice de ranura**: se escribe SIEMPRE, incluso en ranuras vacias.
3. **Nombre de cuenta** en +59: no lo mandaba.
4. **Nombres secundarios** en +593: la captura real los tiene en CERO; yo
   escribia ahi por seguir documentacion heredada.
5. **Apariencia** `[0,0,0,8,8]`: con todo en cero el cliente no podia armar la
   ruta del sprite y mandaba basura de pila en su 0x0006. Ahora manda
   `101_Wait.spr`, igual que el cliente real.
6. **HP/MP maximos**: NO van en la ficha. El binario los lee de arreglos
   separados (`dword_958E0C` / `dword_958E10`), que se llenan desde los
   offsets 455 y 467 del bloque.
7. **Requisitos por servidor** (+644/648/652): la captura traia 70, 40, 41 --
   pero de un personaje de nivel alto. Copiarlos le decia al cliente que cada
   canal exige nivel 70. Van en 0.

## Lo aprendido del binario sobre la conexion al mundo

`sub_51A3C0` tiene dos caminos:

```c
if ( byte_958E8B ) { ... }        // NUNCA se ejecuta: ese byte no se asigna
else if ( v11 >= 0 ) {            // este es el camino real
    v14 = lista_servidores + 372 * v11;
    sub_51A370(v14);              // ip de +64, puerto de +80 de esa entrada
    if (campo_UI_2702 vacio) { error 2; return; }
    if (campo_UI_2704 vacio) { error 3; return; }
    ...conecta...
}
```

Dos cosas importantes:

- `byte_958E8B` esta inicializado en 0 y **no se asigna en ninguna parte** del
  codigo decompilado, asi que la primera rama es codigo muerto.
- La IP y el puerto salen de una entrada de **372 bytes de la lista de
  servidores**, no del redirect.

**Pero esta funcion es el connect del LOGIN, no el del mundo** (usa la lista
de servidores, que viene del server.xml). El handler que procesa el redirect y
dispara la conexion al mundo **todavia no esta identificado**.

## Proximo paso concreto

Encontrar quien procesa el sub-mensaje 0x0004 en la conexion de login. Dos
caminos:

1. Seguir el despachador de mensajes del login (`sub_51A300` registra
   `sub_51B250` en +48 y `sub_51B6B0` en +144; el primero es el bloque de
   cuenta y el segundo el MOTD -- falta el de 0x0004).
2. Comparar el trafico del proxy contra el nuestro tambien en la conexion de
   MUNDO: la captura real tiene 129 mensajes de esa sesion y todavia no se
   comparo con lo que emitimos.

## Deuda conocida

- **La contrasena no se valida.** Dos intentos de identificar el campo del
  hash fallaron (offset 21 y offset 54; el segundo resulto ser una constante
  del cliente). Hay un experimento controlado listo en
  `tools/analizar_auth.py` que lo resuelve con 6 ingresos.
- El HP maximo se ve como `205 / 0` **justo despues de crear** el personaje.
  Es esperado: el maximo vive en arreglos que solo se llenan desde el bloque
  de cuenta (0x0000), y la respuesta a la creacion (0x0001) no los toca. Al
  volver a entrar se ve bien.


---

# Cierre de la sesion: que se descarto y que queda

## El sintoma exacto

Al apretar "Enter game" el cliente **se congela**. No muestra error, no deja
log, no genera dump, y **no intenta ninguna conexion TCP**. Queda bloqueado.

## Verificado IDENTICO byte a byte contra un servidor real

Capturado con `tools/proxy.py` contra un servidor vivo:

| pieza | resultado |
|---|---|
| HELLO del login (134 B) | identico |
| bloque de cuenta (656 B) | identico salvo lo propio del personaje |
| redirect (30 B) | identico salvo token, IP y puerto |
| cantidad y orden de frames | identico (3 frames, todos seq=1) |
| respuesta del servidor de archivos (69 B) | identico |
| HELLO del servidor de archivos | identico |

## Descartado con evidencia

- **Version del cliente**: se probo con 8.5.1.0 (Angels Online) y con 8.6.0.8
  (Play Angels Online, que es el que genero todas las capturas). Mismo
  comportamiento en ambos.
- **Puerto de destino**: 35 puertos con señuelos, incluidos los valores por
  defecto del binario (`dword_91AA6C=6768`, `dword_91AA80=1234`) y los rangos
  vistos en capturas reales. Ninguno se activo.
- **Interfaz de red**: los señuelos se abrieron en `0.0.0.0`, cubriendo las 8
  IPs de la maquina. Tampoco.
- **MOTD**: el servidor real no lo manda; se quito.
- **Numeracion de secuencia**: el servidor usa siempre seq=1; corregido.
- **Cerrar la conexion de login**: el cliente lo interpreta como caida
  ("connection interrupted"). No es lo que espera.
- **Campos del bloque**: ranuras, sub-canal y clase probados con los valores
  reales exactos. Sin efecto.
- **Mapa inicial** (`stage_id`): probado 51 y 2. El cliente refleja el cambio
  en la tarjeta pero se congela igual.
- **Equipo** (9 LE32 por ranura): el servidor real tambien los manda en CERO.

## Lo que eso significa

No queda nada observable en el trafico que se pueda corregir comparando. El
cliente se traba por algo que **no viaja por la red**.

## Unico camino que queda

Correr el cliente bajo un depurador (x64dbg u OllyDbg), apretar "Enter game" y
pausar. La pila de llamadas muestra en que funcion quedo bloqueado, y con el
decompilado al lado eso da la respuesta en minutos.

Los puntos de interes ya identificados:

- `sub_51A3C0` (0x51A3C0): el connect, con dos ramas. `byte_958E8B` esta en 0
  y NUNCA se asigna, asi que la primera rama es codigo muerto.
- `sub_51A370` (0x51A370): copia ip/puerto desde la entrada de servidor. La
  primera direccion (+64/+80) es `ip`/`port` del server.xml; la segunda
  (+96/+112) es `fip`/`fport`.
- `sub_500170` (0x500170): parsea el server.xml a entradas de 372 bytes.
- La tabla de handlers del login se indexa por opcode en `this+48+opcode*8`.
  `sub_51A300` registra SOLO dos: 0x0000 y 0x000C. **Para 0x0004 (el redirect)
  no hay handler registrado**, lo que explica que el cliente lo ignore.

Esa ultima linea es probablemente la clave: si el redirect no tiene handler en
esta conexion, la direccion del mundo tiene que llegar por otra via que
todavia no se identifico.
