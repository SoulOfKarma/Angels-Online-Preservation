# Codec declarativo

## Por que existe

El emulador anterior escribia la misma estructura de paquete a mano en dos
lugares (parser y builder) sin nada que los confrontara. Los dos crashes que
mataban sesiones eran consecuencia directa:

| archivo | bug | efecto |
|---|---|---|
| `packet_builders.py:784` | `'<HIIIIIH'` recibiendo `y = -3` | `struct.error` -> sesion cerrada |
| `handlers/npc.py:489` | `'<HIIIIIB'` con 7 campos y 6 argumentos | dialogo del tutorial imposible |

Aca cada mensaje se define **una sola vez**; parser y builder se derivan de esa
definicion. Ambos bugs son inexpresables: la aridad la garantiza la definicion
y el rango lo valida cada campo.

```
CASO 1  ->  dst_y=-3 fuera de rango [0,4294967295] para U32
CASO 2  ->  ENTITY_MOVE: falta el campo 'speed'
```

Mensajes que nombran el campo culpable, en lugar de `argument out of range`.

## Estructura

| archivo | contenido |
|---|---|
| `proto/codec.py` | tipos de campo (U8/U16/U32/I32/Bytes/Str) y clase `Msg` |
| `proto/messages.py` | definiciones por opcode, derivadas del corpus |
| `tools/roundtrip.py` | harness de conformidad |
| `tools/infer_fields.py` | infiere estructura desde las muestras reales |
| `tools/test_regresion.py` | prueba que los crashes originales no vuelven |

## Harness de conformidad

Tres pruebas por esquema, contra **todas** sus muestras reales:

1. **TAMANO** — el tamano declarado coincide con cada muestra
2. **ROUNDTRIP** — `build(parse(x)) == x` byte a byte
3. **CONSTANTES** — los campos declarados `const` se cumplen siempre

Estado actual: **28/28 esquemas validados, 609.551 muestras, 98,8% del corpus.**

### Alcance real de cada prueba (importante)

El roundtrip prueba que la estructura es **exacta y reversible**, no que los
nombres sean correctos: un `Bytes(63)` opaco pasaria igual. Quien de verdad
falsa hipotesis es la prueba 3 y el cruce de `entity_id`.

### Cruce de entity_id

Un campo declarado `entity_id` se contrasta contra el universo de entity_id
observados (los de 0x0005 y 0x0008, ya confirmados).

> **REGLA: el cruce se hace SIEMPRE por servidor, nunca agregado.**
>
> Cada servidor tiene su propio espacio de entity_id. Agregarlos produjo dos
> falsas refutaciones: `0x0013` daba 43,1% y `0x001D` 27,3% mezclados, pero
> **100,0%** y **98,2%** medidos solo contra el servidor privado. Estuve a
> punto de renombrar dos campos correctos por ese error.

Servidor privado (universo de referencia: 254 entity_id, sesion completa):

| opcode | cruce |
|---|---|
| 0x0005 ENTITY_MOVE | 100,0% |
| 0x0008 NPC_SPAWN | 100,0% |
| 0x000A | 100,0% |
| 0x0013 | 100,0% |
| 0x0016 s2c | 100,0% |
| 0x000B | 99,9% |
| 0x001D ENTITY_ATTRS | 98,2% |
| 0x0007 | 94,7% |

IGG marca `0x0013` (19,3%) y `0x001D` (21,9%) como SOSPECHOSO, pero por
observacion incompleta: esa captura arranca a mitad de sesion y solo vio
spawnear 512 entidades de las muchas que el trafico menciona. No es que el
campo signifique otra cosa: es que ahi no hay con que verificarlo. El flag
dice eso, no lo contrario.

Refutacion que SI se sostuvo: `0x0016 c2s` da 17,9% incluso medido solo contra
el privado, y quedo renombrado a `unk_00`.

## Los opcodes estan acotados POR SERVICIO

El mismo numero de opcode significa **cosas distintas segun el puerto**:

| opcode | puerto | significado |
|---|---|---|
| `0x0002` S2C | 24131 / 24132 | ficha completa del personaje (4118 B) |
| `0x0002` S2C | 30007 | nombre de archivo PNG del avatar (69 B) |

Por eso `Msg` acepta `puertos=(...)`. Sin ese filtro el harness mezclaba las
dos cosas y reportaba "tamano variable" sobre un mensaje que en realidad es
de tamano fijo.

Al analizar un opcode nuevo, **mirar siempre de que puerto vienen las
muestras** antes de concluir que un mensaje tiene variantes.

## Convenciones

- Un campo se nombra **solo** con evidencia de lo que significa. El resto queda
  `unk_<offset>`: estructuralmente exacto, semanticamente honesto. Nunca un
  nombre inventado que alguien despues tome por confirmado.
- `rev=` distingue revisiones. IGG y el servidor privado **no corren el mismo
  protocolo**:
  - `0x0008` mide 62 bytes en IGG y 63 en el privado.
  - `0x0011` tiene `@8`/`@12` en cero solo en el privado.
  - El privado limpia el campo de nombre con NUL; IGG deja bytes residuales
    (por eso va como `Bytes` y no como `Str`: normalizarlo rompia el roundtrip
    en 784/788 muestras).

## Longitud variable

`Count` + `Array` resuelven los mensajes de largo dinamico. El contador **no se
pasa al construir: se deriva de `len(array)`**, asi que no puede desincronizarse
del array. Es la misma clase de error que los crashes originales, solo que en
vez de reventar el struct corrompe el stream del cliente.

```python
VarMsg(0x001D, 's2c', 'ENTITY_ATTRS', [
    U32('entity_id'),
    Count('n', of='attrs'),
    Array('attrs', [U8('kind'), U32('a'), U32('b')]),
])
```

`len = 5 + n*9`, verificado en ambos servidores. Roundtrip exacto en
**261.756 / 261.756** muestras. Este solo opcode llevo la cobertura de 55,2%
a 97,6%.

## Lo que falta

2,4% del corpus: `0x001B`, `0x0001`, `0x0128`, `0x0167`, `0x000D` y las
variantes raras de `0x0013` (7 muestras de 15 y 20 bytes). Son de baja
frecuencia pero incluyen los mensajes grandes, probablemente inventario y
listados: importan para jugar, aunque no para moverse.
