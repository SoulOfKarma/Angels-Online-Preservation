# Handshake (Hello)

Derivado de `sub_81EED0`, `sub_81FAD0`, `sub_81FC10`, `sub_81FB70` en el
binario del cliente, y verificado contra capturas reales de ambos servidores.

## Transporte

Frame con `seq=0xFFFF`, **sin cifrar** (`flags=0x00`). Es el primer frame que
manda el servidor al aceptar la conexion. Su cuerpo es un sub-mensaje normal:
`[LE16 sub_len][...]`.

## Objeto socket: offsets relevantes

| offset | contenido |
|---|---|
| `+195616` | puntero a funcion de descifrado "cruda" (rama de codigo embebido) |
| `+195620` | contexto de clave para esa funcion |
| `+195624` | objeto cripto de RECEPCION (vtable: `+4` SetKey, `+12` Decrypt) |
| `+195628` | objeto cripto de ENVIO (vtable: `+4` SetKey, `+8` Encrypt) |

`sub_81FC10` y `sub_81FB70` son ambos **SetKey** -- sobre el cifrador de envio
y el de recepcion respectivamente, **con la misma clave**.

`8 * N` en la llamada NO es un tamano en bytes: es la longitud **en bits**
(16 bytes -> 128). Internamente `sub_81FC90` hace `*(DWORD*)(this+4) >> 2`
sobre el tamano en bytes.

## Dos variantes

### Minima -- la que usa IGG (sub-mensaje de 20 bytes)

```
[LE32 key_len=16][16 bytes de clave]
```

El cliente hace SetKey sobre sus cifradores internos. **Es la que conviene
implementar**: esta atestiguada en produccion y no requiere generar codigo.

Verificacion: `build_hello(clave)` reproduce el Hello real de IGG
**byte a byte identico**.

### Con cifrador embebido -- la que usa el servidor privado (132 bytes)

```
[LE32 key_len=16][16 bytes de clave]
[LE32 code_len=80][80 bytes de codigo maquina x86]
[LE32 ctx_len=24][LE32 1][LE32 16][16 bytes]
```

Si el cliente no tiene objeto cripto instalado, toma ese codigo, lo vuelve
ejecutable (`sub_828170`) y lo usa **como funcion de descifrado**. El servidor
envia el algoritmo, no solo la clave.

## ADVERTENCIA DE SEGURIDAD

Esta segunda rama es **ejecucion de codigo remoto por diseno**. Un servidor de
Angels Online puede hacer que el cliente ejecute x86 arbitrario en la maquina
del jugador, y el cliente lo hace sin validar nada.

Consecuencia practica: **conectar este cliente a un servidor que no controlas
es ejecutar el codigo que ese servidor decida enviarte.** Vale para cualquier
servidor privado de AO, incluido aquel del que salieron estas capturas.

En el caso medido el codigo era inofensivo -- desensamblado con capstone,
resulta ser el mismo XOR por DWORD que el cliente ya implementa en
`sub_81FC90`:

```asm
shr    ecx, 2              ; n_dwords = key_bytes / 4
lea    ebx, [ecx - 1]      ; mascara
and    ebp, eax            ; i & mascara
mov    ebp, [esi+ebp*4]    ; clave_dwords[i & mascara]
xor    ebp, [ecx - 4]      ; ^ origen
mov    [edx - 4], ebp      ; -> destino
```

Pero eso es una observacion sobre **esa** captura, no una garantia sobre
cualquier servidor.

## Cifradores

Confirmados al 100% sobre ~150.000 frames reales de IGG:

| direccion | cifrador |
|---|---|
| S -> C | XOR estatico de 16 bytes |
| C -> S | XOR con clave evolutiva (cada DWORD += `padded_len` tras cada paquete) |

Ambos vienen de `sub_81FC90`/`sub_81FD10`: XOR por DWORD con mascara
`(n_dwords - 1)`, asi que **la clave debe medir una potencia de 2 en dwords**.
16 bytes = 4 dwords.

## Configuracion recomendada para nuestro servidor

1. Hello en variante **minima** con una clave de 16 bytes.
2. S -> C **en texto plano** (`flags=0x00`): el servidor privado lo hace asi y
   el cliente lo acepta sin problema.
3. C -> S descifrado con XOR evolutivo partiendo de esa clave.

Las tres decisiones estan atestiguadas en capturas reales; ninguna es
conjetura.

## Implementacion

`proto/handshake.py`: `build_hello()`, `parse_hello()`, `XorStatic`,
`XorEvolving`.
