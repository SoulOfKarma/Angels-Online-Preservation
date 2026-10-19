# Guía de migración del cliente Taiwan hasta update32

> Documento de relevo para continuar esta investigación con otra IA o con otro
> desarrollador. Se basa en mediciones realizadas el 19 de octubre de 2026
> sobre los clientes locales indicados abajo. No presupone que dos ramas con el
> mismo número de parche tengan el mismo contenido.

## Objetivo

Incorporar progresivamente al emulador Hestia y a un cliente de pruebas el
contenido posterior a `update26`, usando el cliente oficial de Taiwan hasta
`update32` como fuente principal y Angels Online Eternal como fuente auxiliar
de traducciones.

El objetivo **no** es copiar `update27.pak` a `update32.pak` sobre el cliente
IGG actual. Las tres instalaciones pertenecen a ramas y esquemas de empaquetado
distintos. La migración debe separar:

1. assets que el cliente puede consumir directamente;
2. tablas de datos que también necesita el servidor;
3. textos traducibles;
4. funciones nuevas que dependen del ejecutable y del protocolo;
5. scripts o reglas que deben reimplementarse en Hestia.

## Instalaciones examinadas

| Rol | Ruta | Estado observado |
|---|---|---|
| Cliente actual del proyecto | `C:\AO\Angels Online` | Rama IGG/Global hasta `update26` |
| Traducción auxiliar | `G:\Angels Online Eternal` | Ejecutable que enumera PAK hasta `update28` |
| Fuente oficial moderna | `G:\ALO Taiwan\天使之戀Online` | Ejecutable que enumera PAK hasta `update32` |

No modificar ninguna de estas instalaciones durante la fase de análisis. Crear
copias de trabajo con rutas diferentes y conservar hashes de los originales.

## Conclusión ejecutiva

La migración hasta `update32` es técnicamente viable, pero la base recomendada
para obtener todos los sistemas modernos es el **cliente Taiwan 32**. Eternal
sirve para recuperar parte de la traducción de 27–28. El cliente IGG actual
sirve como referencia funcional y de protocolo, pero no es un destino seguro
para copiar directamente los PAK modernos.

Razones:

- Los PAK 27–32 usan la misma familia de archivo `OD 05 06` que ya entiende el
  proyecto.
- Taiwan incluye tablas acumulativas de monstruos, objetos, mapas, NPC, magia,
  mascotas, misiones, drops y tiendas.
- El ejecutable Taiwan contiene lógica posterior que no existe necesariamente
  en IGG ni en Eternal.
- Eternal sólo carga explícitamente hasta `update28`; Taiwan carga hasta
  `update32`.
- Eternal y Taiwan divergen en datos. Las traducciones de Eternal deben
  transferirse por ID y campo, nunca reemplazando filas completas de Taiwan.

## Inventario verificado de los PAK modernos

### Taiwan

| PAK | Tamaño | Entradas internas | SHA-256 |
|---|---:|---:|---|
| `update27.pak` | 69,869,658 B | 1,014 | `63BC9E1AF40F902CCAA9E4A909116D83528368CA34B1FBE84B1363DD1FF353CC` |
| `update28.pak` | 66,078,920 B | 1,922 | `9CF3516AA3CFDE2EDA14168DDE2E95E6223D1300BC57EDD673B44926FB3F6E5D` |
| `UPDATE29.PAK` | 199,751,662 B | 2,971 | `CCED5484372D09807861366A4C4A5837A16C0E96715636ECF35406A88AA4B335` |
| `UPDATE30.PAK` | 186,459,059 B | 3,550 | `170BAB35A240C5EABA1FFBBA8B327C2BE5D4C44AF07859C1CC377FD755550DAA` |
| `update31.pak` | 78,067,844 B | 2,003 | `D1604A684A2CA1BACF00B72E2712A676EF166CB954BD7913671D8A0B5FFDE6E1` |
| `update32.pak` | 64,754,620 B | 1,657 | `0805E3A1361CE5DB2B22522C254360BE75CEDA5FABDB949F731FF0A03DF0BC62` |

Contenido predominante observado:

| PAK | SHP | SPR | XML | MPC |
|---|---:|---:|---:|---:|
| Taiwan 27 | 554 | 353 | 66 | 26 |
| Taiwan 28 | 1,338 | 453 | 68 | 22 |
| Taiwan 29 | 1,676 | 1,148 | 92 | 27 |
| Taiwan 30 | 1,640 | 1,752 | 81 | 30 |
| Taiwan 31 | 1,260 | 639 | 66 | 20 |
| Taiwan 32 | 221 | 1,313 | 89 | 18 |

### Eternal

| PAK | Tamaño | Entradas internas | SHA-256 |
|---|---:|---:|---|
| `update27.pak` | 83,020,817 B | 2,194 | `4CDAB5438B11216DE36724C607034F9E51B1280581110F56DAB17E0053440A2B` |
| `update28.pak` | 474,817,792 B | 30,918 | `314E425BB66416EAE884AFF4DC4A0230D30589DC99879DE6CDF98A2EA8C056B7` |

`update28.pak` de Eternal es una consolidación grande: contiene 29,124
entradas bajo `shape`, 1,172 bajo `setting`, 568 bajo `map` y carpetas
`setting/BIG5`, `setting/ENG` y `setting/MAP`.

### Referencia IGG

`C:\AO\Angels Online\update26.pak`:

- tamaño: 39,791,807 B;
- 799 entradas internas;
- SHA-256:
  `BF3CF5D0B2489405568B42975B7A1DCD06C14E1E75C6940AE802114287BBAE01`.

El `data1.pak` actual ronda 709 MB y pertenece a la línea incremental antigua.
El `data1.pak` moderno de Taiwan/Eternal ronda 143 MB y los parches 8–26 de
esas instalaciones son marcadores de 75 bytes. Ésta es una diferencia de
linaje, no una simple ausencia de seis archivos.

## Cobertura real de Eternal frente a Taiwan

Comparando nombres internos sin distinguir mayúsculas:

| Conjunto Taiwan | Assets no `setting` presentes en Eternal 27–28 |
|---|---:|
| 27–28 | 2,369 / 2,776 = 85.3 % |
| 27–29 | 4,354 / 5,610 = 77.6 % |
| 27–30 | 6,300 / 9,046 = 69.6 % |
| 27–31 | 7,572 / 10,955 = 69.1 % |
| 27–32 | 7,617 / 12,481 = 61.0 % |

Por lo tanto:

- Eternal es útil para traducir y comparar 27–28.
- Eternal **no** contiene todo 29–32.
- Faltan aproximadamente 4,864 assets no `setting` del conjunto Taiwan 27–32.
- Algunos faltantes son sistemas completos: `worldboss`, `battlepass`,
  `loginreward`, `onlinereward`, `roulette` y sus scripts/interfaz.

No asumir que “Eternal update28” equivale a “Taiwan update28” ni que contiene
todo lo publicado después.

## Diferencias medidas en tablas

Las tablas no prueban por sí solas que una rama sea superior: también contienen
contenido privado, retirado o reorganizado. Sirven para demostrar divergencia.

| Tabla | Eternal 28 ENG/BIG5 | Taiwan 32 BIG5 |
|---|---:|---:|
| `monster.xml` | 19,493 filas | 19,420 filas |
| `stage.xml` | 484 filas | 466 filas |
| `npc.xml` | 3,388 filas | 3,401 filas |
| `quest.xml` | 1,527 filas | 1,503 filas |
| `magic.xml` | 18,853 filas | 19,216 filas |
| `item9.xml` | 3,857 filas | 3,700 filas |
| `drop.xml` | 22,875 filas | 4,590 filas |
| `msg.xml` | 42,549 filas | 42,424 filas |

En Eternal, `monster.xml` y `npc.xml` de `ENG` son byte por byte iguales a sus
copias `BIG5`, mientras que `quest.xml`, `magic.xml`, `item9.xml`, `drop.xml` y
`msg.xml` sí difieren. La traducción de Eternal es parcial y debe auditarse por
tabla y por campo.

## Formato PAK y corrección obligatoria del lector

Los PAK terminan en un bloque de 22 bytes cuya firma es:

```text
4F 44 05 06    # "OD\x05\x06"
```

Los bytes 4–21 del pie se decodifican así:

```python
for i in range(4, 22):
    eocd[i] ^= (3 * i - 91) & 0xFF
```

Después se interpretan como:

```python
lo, hi, count_a, count_b, cd_uncompressed_size, cd_offset, comment = \
    struct.unpack('<HHHHIIH', eocd[4:22])
compressed_cd_size = lo | (hi << 16)
```

El segundo `u16` no debe ignorarse. En Eternal `update28`, el índice comprimido
mide 487,981 bytes:

```text
lo = 29,229
hi = 7
29,229 + (7 << 16) = 487,981
```

El lector actual en `server/cliente_local.py`, función
`_extraer_archivo_pak`, usa sólo `lo`. Por eso puede leer update27 pero falla
con `zlib.error: incomplete or truncated stream` al intentar leer el índice
grande de Eternal 28.

Antes de extraer o reconstruir los PAK modernos se debe corregir, con pruebas,
tanto el lector como el escritor de `server/cliente_local.py`:

1. combinar `lo | (hi << 16)` al leer;
2. separar nuevamente los 32 bits en dos `u16` al escribir;
3. no asumir que los dos contadores de entradas siempre son idénticos;
4. recorrer el directorio hasta `len(cd)`, validando cada cabecera;
5. rechazar offsets o tamaños fuera del archivo;
6. verificar CRC y tamaño descomprimido de cada entrada;
7. probar con update26, Eternal 27/28 y Taiwan 27–32.

El directorio comprimido comienza en `cd_offset + 4`; su primer byte se XOR-ea
con `0x7A` antes de `zlib.decompress`. Las entradas usan la estructura central
tipo ZIP `<IHHHHHHIIIHHHHHII>` y los datos individuales están comprimidos con
DEFLATE crudo (`zlib.decompress(data, -15)`).

## Semántica de parches

Usar orden numérico explícito:

```text
data1 < update < update2 < ... < update32
```

Nunca ordenar lexicográficamente: `UPDATE10` quedaría antes de `UPDATE8`.

Para cada ruta interna, gana la versión del PAK numéricamente más alto que la
contenga. Si `update32` no incluye `item6.xml`, se usa la última versión
anterior disponible de ese archivo. Cuando un parche contiene `monster.xml` o
`drop.xml`, ese archivo completo reemplaza al homónimo anterior; no se deben
fusionar filas antiguas indiscriminadamente.

Adaptar [tools/paks.py](../tools/paks.py) para aceptar:

- raíz de extracción configurable;
- máximo de parche configurable;
- nombres en cualquier combinación de mayúsculas;
- manifiesto con SHA-256, PAK de procedencia, tamaño y ruta normalizada.

No cambiar inicialmente el comportamiento usado por IGG. Crear un perfil
separado, por ejemplo `taiwan32`.

## Arquitectura recomendada de trabajo

### 1. Copias aisladas

Crear, fuera de las instalaciones originales:

```text
work/taiwan32_original/     copia inmutable o referencia sólo lectura
work/taiwan32_client/       cliente ejecutable de pruebas
work/taiwan32_extracted/    extracción completa
work/eternal28_extracted/   traducciones auxiliares
work/manifests/             catálogos y hashes
```

No ejecutar `server/cliente_local.py` contra esas rutas hasta que su lector y
escritor de PAK grandes tengan pruebas.

### 2. Extracción reproducible

La herramienta debe ofrecer al menos:

```text
list <pak>
extract <pak> <destination>
verify <pak>
manifest <pak> <json-output>
```

Cada manifiesto debe registrar:

- archivo PAK y SHA-256;
- ruta interna normalizada;
- tamaño comprimido y descomprimido;
- CRC almacenado y CRC calculado;
- offset;
- extensión;
- hash del contenido descomprimido.

Después de extraer, comprobar que no haya rutas absolutas, `..`, colisiones por
mayúsculas o escrituras fuera del directorio de destino.

### 3. Vista vigente Taiwan 32

Construir una vista virtual “last PAK wins” sin copiar todavía al cliente. Ésa
será la fuente oficial de datos. Mantener también las seis versiones para
poder responder en qué parche apareció o cambió cada fila.

Generar informes de:

- archivos añadidos, sustituidos y eliminados por parche;
- IDs nuevos y modificados por tabla;
- mapas nuevos y assets referenciados ausentes;
- scripts nuevos;
- cambios de esquema XML;
- ventanas o sistemas nuevos;
- IDs que colisionan con contenido Eternal o IGG.

### 4. Corpus separado

No sobrescribir `corpus/content.db` durante la exploración. Crear algo como:

```text
corpus/content_tw32.db
```

Cada tabla necesita procedencia:

```text
_branch = taiwan
_pak = update32
_source_path = setting/BIG5/monster.xml
_source_sha256 = ...
```

Adaptar [tools/extract_content.py](../tools/extract_content.py) en un perfil
separado y comparar conteos/columnas antes de conectar ese corpus al servidor.

## Estrategia de traducción

La traducción se hace por ID estable y por campo traducible, manteniendo los
valores técnicos de Taiwan.

Ejemplo conceptual:

```text
Taiwan row ID 12345:
  stats, sprite, flags, scripts, references -> conservar Taiwan
  name/description/dialog text             -> tomar Eternal si coincide
```

Prioridad sugerida:

1. coincidencia exacta de ID y contexto entre Taiwan y Eternal;
2. traducción ya existente en el cliente IGG;
3. glosario aprobado del proyecto;
4. traducción automática marcada como provisional;
5. revisión humana dentro del juego.

No traducir:

- nombres de atributos XML;
- rutas;
- nombres de archivos referenciados;
- claves de scripts;
- identificadores;
- tokens como `%123%`, códigos `/c$...`, saltos `\n` o marcadores de formato.

Traducir y probar:

- `msg.xml`, `string.xml`;
- nombres/descripciones en `item*.xml`, `monster.xml`, `npc.xml`, `magic.xml`;
- misiones y opciones de diálogo;
- nombres de mapas;
- textos incluidos en `.tga` u otros assets gráficos;
- botones que incorporen sufijos o texto chino.

Mantener una memoria de traducción versionada:

```text
table, id, field, zh_tw, en_eternal, en_final, status, source_patch
```

No reemplazar toda una tabla BIG5 por la tabla ENG de Eternal: los conteos y
los datos técnicos divergen.

## Elección del cliente

### Opción A: Taiwan 32 traducido — recomendada

Ventajas:

- contiene la lógica de cliente más reciente;
- enumera explícitamente `update27.pak` a `update32.pak`;
- puede mostrar las interfaces y sistemas nuevos que el ejecutable IGG no
  conoce.

Costes:

- adaptar el protocolo de Hestia;
- traducir 29–32;
- posiblemente adaptar launcher, login, codificación y fuentes;
- revisar dependencias y protecciones del ejecutable.

Como el ejecutable sólo enumera hasta `update32.pak`, no asumir que cargará un
`update33.pak`. Las traducciones deben integrarse en una copia reconstruida del
PAK de mayor prioridad o debe parchearse de forma controlada la lista de PAK.

### Opción B: Eternal 28

Útil para llegar antes a contenido 27–28 en inglés. No es una base suficiente
para sistemas completos de 29–32 porque su ejecutable sólo enumera hasta 28 y
faltan miles de assets Taiwan posteriores.

### Opción C: IGG update26

Sólo recomendable para portar contenido compatible de manera selectiva:
modelos, animaciones, objetos o mapas que no dependan de código nuevo. Una tabla
o un sprite nuevo puede funcionar; una ventana, protocolo o sistema nuevo no
aparecerá mágicamente por copiar sus archivos.

## Adaptación del servidor

Migrar parche por parche, no todo de una vez.

### Datos relativamente automatizables

- `monster.xml`: identidad, sprites, nivel y stats;
- `drop.xml`: tablas y pesos, respetando su semántica real;
- `item.xml` a `item9.xml`: objetos, requisitos y presentación;
- `magic.xml`: definiciones y referencias de efectos;
- `npc.xml`: identidad y sprite;
- `stage.xml`, `jumpmap.xml`: mapas y conexiones;
- `shop.xml`, `exchange.xml`: contenido de tiendas/canjes;
- `pet.xml`, `petattrib.xml`, `petskill.xml`: mascotas;
- `quest.xml`, `msg.xml`: misiones y textos.

### Sistemas que requieren código o captura

- IA o scripts que no estén completamente expresados en XML;
- interfaces nuevas;
- battle pass, world boss, login reward, roulette y sistemas equivalentes;
- nuevos paquetes C2S/S2C;
- cambios en apariencia, inventario o estructuras con longitud distinta;
- instancias y reglas temporales;
- validaciones antifraude y persistencia.

Para capturas y comparación de protocolo ya existen herramientas útiles:

- [tools/procesar_capturas.py](../tools/procesar_capturas.py)
- [tools/separar_por_mapa.py](../tools/separar_por_mapa.py)
- [tools/poblar_mapa.py](../tools/poblar_mapa.py)
- [tools/analizar_captura.py](../tools/analizar_captura.py)

El repositorio ya reconoce diferencias de Taiwan, por ejemplo entidades de 63
bytes y nombres BIG5. No generalizar una captura aislada: tomar inicio de
sesión, entrada a mapa, aparición/desaparición, apertura de ventana, acción,
respuesta correcta, error y cierre.

## Orden sugerido de implementación

### Fase 0: infraestructura

- corregir lector/escritor de PAK grande;
- crear extractor y manifiestos reproducibles;
- crear perfiles IGG, Eternal y Taiwan;
- generar `content_tw32.db` sin alterar producción;
- añadir pruebas de precedencia y seguridad de rutas.

### Fase 1: arranque y protocolo base

- arrancar una copia de Taiwan 32 contra un entorno Hestia separado;
- comparar handshake, login y selección de personaje;
- validar tamaños de los paquetes más frecuentes;
- adaptar sólo los campos comprobados mediante captura;
- lograr entrar a un mapa vacío sin crash.

### Fase 2: presentación y contenido pasivo

- textos, fuentes y codificación;
- mapas y decorados;
- objetos visibles;
- monstruos/NPC visibles sin interacción;
- animaciones y sonidos.

### Fase 3: contenido jugable

- combate y stats;
- drops;
- tiendas y exchange;
- portales;
- NPC y diálogos;
- misiones;
- pets y skills.

### Fase 4: sistemas nuevos

Implementar uno por uno con captura oficial y prueba de regresión. No habilitar
un botón hasta que apertura, operación, error, persistencia y reconexión estén
implementados.

### Fase 5: traducción final

- aplicar memoria de traducción;
- revisar desbordes visuales;
- revisar texturas con chino;
- comprobar variables y colores de texto;
- producir el PAK localizado reproducible;
- verificar hashes y arranque limpio.

## Criterios de aceptación por parche

Un parche no se considera migrado sólo porque el cliente arranque. Debe pasar:

- extracción completa sin CRC inválidos;
- cero assets referenciados ausentes en el alcance implementado;
- carga de tablas sin pérdida de columnas;
- login y entrada a mapa;
- aparición correcta de jugadores, NPC, mobs, pets e invocaciones;
- movimiento y combate visibles para otros jugadores;
- muerte/desaparición sin crash;
- drops con probabilidades correctas;
- tiendas y canjes con datos reales;
- portales de entrada y salida;
- persistencia tras desconectar/reconectar;
- textos sin tokens rotos;
- prueba de regresión del contenido 1–26.

## Errores que se deben evitar

- Copiar los PAK 27–32 directamente sobre `C:\AO\Angels Online`.
- Probar primero con la única instalación funcional del usuario.
- Mezclar filas de XML acumulativos de todos los parches.
- Ordenar nombres de PAK alfabéticamente.
- Considerar Eternal como traducción completa de Taiwan 32.
- Reemplazar stats Taiwan por una fila Eternal sólo para obtener el nombre.
- Traducir nombres de atributos o tokens internos.
- Inventar layouts de paquetes basándose en el nombre de una ventana.
- Habilitar una interfaz sin implementar su respuesta de error.
- Poblar mapas masivamente antes de probar un mapa mínimo.
- Cambiar `content.db` productivo antes de comparar el corpus Taiwan.

## Incidente corregido: Exchange Time Crystal

El 19 de octubre de 2026 se reprodujo un crash del cliente IGG al elegir
`Exchange Time Crystal` en `Past the Time Spirit`.

Evidencia:

- el cliente envió `DIALOGO_SIGUIENTE`, opción 3, diálogo `158514`;
- el servidor respondió inmediatamente con opcode decimal 518 (`0x0206`),
  cuerpo de 28 bytes:

```text
03 00 00 00
47 54 00 00 00 00 00 00
48 54 00 00 00 00 00 00
49 54 00 00 00 00 00 00
```

- esos IDs son 21575, 21576 y 21577;
- el servidor no lanzó excepción;
- el proceso cliente mostró “This program will be terminated...” y se
  desconectó.

Causa: `0x0206` se tomó de `WND_EXCHANGE` como si fuera opcode S2C. Es un ID de
ventana, no un opcode de red. Además, `0x0206` queda fuera de la tabla IGG
conocida de 512 handlers (`0x0000`–`0x01FF`). La misma suposición se había
usado para Voucher Angel.

El mecanismo correcto se obtuvo del ejecutable IGG decompilado:

1. `docs/tabla_s2c.md` asigna `FUN_005f4890` al opcode S2C `0x0151`;
2. ese handler lee un `u32` en `body+0`;
3. guarda ese valor como grupo de exchange;
4. llama `CreateItemWnd` y `CreateExchangeWnd`;
5. carga localmente las recetas pertenecientes al grupo desde `exchange.xml`.

La respuesta correcta para Past the Time Spirit es, por tanto:

```text
opcode 0x0151 + u32 grupo 659
```

El grupo 659 contiene las recetas 21575, 21576 y 21577. Voucher Angel usa el
mismo opcode con el grupo 254, que contiene las recetas 11342 y 11343. El código
y sus pruebas se corrigieron para enviar sólo esos paquetes de seis bytes.

## Entregables esperados para una futura sesión

1. lector/escritor PAK corregido y probado;
2. manifiestos JSON de Taiwan 27–32 y Eternal 27–28;
3. extracción separada y verificable;
4. informe de diferencias por parche;
5. `content_tw32.db` con procedencia;
6. memoria de traducción por ID/campo;
7. cliente Taiwan 32 de pruebas, nunca la copia original;
8. matriz de compatibilidad de opcodes y layouts;
9. implementación incremental con pruebas;
10. paquete traducido reproducible y procedimiento de rollback.

## Estado al cerrar esta investigación

- Confirmado que Taiwan llega a `update32`.
- Confirmado que los PAK modernos son legibles con una corrección pequeña al
  tamaño de su índice.
- Confirmado que Eternal es útil pero no cubre toda la rama 29–32.
- Confirmado que el ejecutable Taiwan es la base más razonable para sistemas
  modernos.
- No se modificó ninguna instalación externa ni ningún PAK.
- La migración queda aplazada; este documento conserva el punto exacto desde
  el cual retomarla.
