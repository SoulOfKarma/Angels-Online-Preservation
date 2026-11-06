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

## Ejecución del 26 de octubre de 2026: contenido TW 27–32 dentro del cliente IGG

Se cambió de estrategia respecto de la "Opción A": **no hace falta el exe de
Taiwán**. Medido con REA (Ghidra) sobre `angel.dat` IGG desempaquetado con UPX
(sha256 `7c1f8cc1…`): `WinMain` (0x533FD0) monta `update2.pak` … `update31.pak`
(xref de la cadena `update31.pak` en 0x5341f7). No existe `update32.pak` en el
binario, así que lo de TW 32 se funde en nuestro `update31.pak` (gana 32).
`setting\BIG5\` de TW y `setting\eng\` de IGG tienen el mismo formato.

Herramientas (todas en `tools/`):

| Herramienta | Qué hace |
|---|---|
| `pak_tool.py` | list / verify / extract / manifest / build; lector con `lo \| hi<<16`, CRC, rutas seguras; `actualizar()` reemplaza **y añade** entradas |
| `tw_migracion.py analizar` | qué trae TW 27–32 que IGG no tiene |
| `tw_migracion.py memoria` | memoria zh→en: pares reales por ID y campo (TW chino ↔ IGG inglés), descarta pares con números distintos (IDs reutilizados por IGG) |
| `tw_migracion.py construir` / `tablas` | fusiona tablas + traduce → `work/salida/setting_update26`; `construir` además arma `work/salida/paks/update27..31.pak` |
| `tw_migracion.py instalar` / `instalar_tablas` | respalda en `work/backup/<ts>` y lleva todo al cliente y a `extracted_paks/update26` |
| `tw_migracion.py desinstalar <ts>` | vuelve al estado de ese respaldo |
| `tw_migracion.py contenido` | `corpus/content.db`: añade filas con ID nuevo y cambia textos chino→inglés; no toca nada más |
| `traducir.py estado` / `exportar N M` | cobertura y lotes pendientes priorizados |

Política de fusión: **IGG manda**. Fila o archivo que IGG ya tiene se queda
igual (salvo traducir texto); de TW solo entra lo que IGG no tiene:

- `setting\eng\*.xml`: filas con `編號` nuevo al final (item9 2.238 → 3.700,
  exchange +12.294, magic +680, monster +194, stage +11, msg +632…).
- Raíz de `setting\`: se añaden solo claves nuevas en `itemicon2-4`,
  `skillicon`, `peticon`, `faceicon` (`id`), `shop` (`編號`), `level` (`等級`),
  `pet_inlay`, `chardef` (`號碼` dentro de su sección) y los `.obd`
  (`[OBJECT]` por `Sequence`: `char3/4`, `npc`, `common`, `mapobj`, `server`,
  `m02`). Se quedan como IGG: `actboard`, `star_client`, `pet_star`, `fuse`,
  `eventdef`, `globalwnd` (World Boss necesita servidor), `battlepass*`,
  `midage.tic`, `system.xml` (las listas de carga TW e IGG son idénticas).
- Assets (`shape`, `map`, `music`, `brush`, `script`, `bmp`): solo rutas
  nuevas → `update27..31.pak` (12.472 archivos, ~495 MB).

**Por qué las tablas van dentro de `update26.pak` y no en un pak superior.**
`cliente_local.aplicar_modo_estacion` re-parchea `update26.pak` al arrancar el
servidor (estación en `stage.xml` desde el `.bak`, medalla 83266 e
item tables desde `extracted_paks/update26`, battlepass, activityurl). Un
`update27.pak` con esas tablas taparía esos parches. Por eso `instalar`
escribe las tablas en `update26.pak` **y** en `update26.pak.bak`.

Traducción: solo campos de texto (`基本名稱`, `原型名稱`, `說明定義`, `文字`,
`名稱`, `說明`, `獎賞說明`, `任務名稱`, `步驟NN`, `地點NN`, `承接NN`,
`封號`…). Los valores en chino de enums (`是/否`, `物品類別`, `顏色`, `系別`,
`HP定義`…) **no se traducen**: el exe los compara literalmente (IGG también
los deja en chino). El texto se traduce por línea (`&#xA;` / `\n` literal) y
los manuales usan `#` por número para cubrir todos los niveles.

Orden de búsqueda: `work/traduccion/manual/*.json` → memoria exacta →
plantilla numérica de la memoria. Estilo IGG: `祝福` = "Lucky",
`打孔錘` = "Piercing Hammer", `強化錘` = "Enhanced Pestle", `N星` = "N-star",
`頂級輕裝/重裝/法袍禮盒` = "Classic Light Armor/Heavy Armor/Gown Box",
`福袋` = "Lucky Bag", `扭蛋` = "Egg", `附魔-` = "Enchanted-",
`變身` = "Shapeshift:", `衣箱` = "Wardrobe Chest".

Estado al cierre del 26/10/2026:

- Instalado en `C:\AO\Angels Online`: `update26.pak` (+.bak) con 177
  archivos de setting fusionados y `update27..31.pak` nuevos. Primer respaldo
  (estado IGG puro): `work/backup/20261026_160246`.
- `content.db`: +1.462 objetos (item9), +230 petattrib, +69 doll y el resto
  de tablas al día; respaldo previo `work/backup/content_20261026_15*.db`.
- Versión mostrada: `cliente_local.VERSION_CLIENTE = '8.7.6.1'` (reg.ini y
  update3.ini). `angel.dat` solo la muestra; no viaja al servidor.
- Traducción: memoria de 101.641 pares + lotes manuales 000–006 (1.750
  segmentos, prioridad: nombres → contenido nuevo → descripciones). Quedan
  ~53.800 segmentos (~900k caracteres), sobre todo descripciones y textos
  JP/TW que ya traía el cliente IGG.
- Suite completa: 373 fallos que **ya existían** (pasan por separado; dependen
  del orden de ejecución). `test_mascotas` y `test_house_system` fallan igual
  con los datos originales (comprobado restaurando content.db/level/petattrib).

Para continuar la traducción:

```text
python -I tools/traducir.py exportar 250 8     # lotes en work/traduccion/lotes
#  rellenar y guardar como work/traduccion/manual/lote_NNN.json
python -I tools/tw_migracion.py tablas
python -I tools/tw_migracion.py instalar_tablas
python -I tools/tw_migracion.py contenido
```

### Ampliación de la misma fecha: update32.pak propio y región Sand Castle Tales

- **update32.pak propio.** `tools/parchear_angel_update32.py` parchea el
  `angel.dat` IGG (desempaquetado con UPX) para que monte también
  `update32.pak`: en `0x534201` (justo tras cargar update31) un `jmp` a una
  cueva en `0x8b29e0` que hace `sub_74BBD0("update32.pak", 0)`, luego el
  `CoInitialize` original y vuelve a `0x53420c`; la cadena va en `0x9125e0`
  (relleno de `.rdata`) y se amplía el VirtualSize de `.text`/`.rdata` hasta
  su SizeOfRawData. Verificado con REA. Original guardado como
  `angel.dat.antes_update32` (y `angel_igg.dat`). `DESTINO_PAK` ya manda TW 32
  a `update32.pak`.
- **map169.mpc (Karang Desert)** de TW 32 reemplaza al de IGG
  (`REEMPLAZOS_TW`): trae el tornado `(7,172) → 423`, la entrada a la región.
- **Servidor:** mapas 423–429 poblados desde sus `.mpc`
  (`tools/poblar_del_cliente.py`, 218–237 monstruos cada uno, nv 400–466) y
  registrados en `login.PLANTILLAS_POR_STAGE`; portales de 169 y 423–429 con
  `tools/propagar_portales.py`; Superwing (`angels_go.json`, ids 356–364) y
  aparición (`jumpmap.json`) con `work/registrar_region.py`; lógica de mapas
  (misiones 1620–1624 de Rotwood Abyss, barreras `CHANGE_STATICOBJ`,
  diálogos) en `eventos.json` con `tools/propagar_eventos.py`.
- **TRAMPA DEL `<ALIAS>`.** Las tablas IGG acaban en uno o varios
  `<ALIAS …/>`/`<DEFINE …/>` (traducen los atributos chinos a los nombres que
  pide el exe: `id`, `classname`…). Lo que va **detrás** no lo carga el
  cliente. La primera instalación dejó ahí las filas de TW: sin `stage 423`
  el cliente crasheaba al entrar (terreno nulo en `sub_56F160`, EIP
  `0x56F1B3`) y la categoría 40 no salía en el Superwing.
  `punto_insercion()` ahora mete las filas antes del primer ALIAS/DEFINE y
  `tw_migracion.py reparar_alias` arregló lo instalado (34 tablas).
- **Región 30 del mapa del mundo.** El exe registra las regiones en código
  (`sub_5AA1E0(this, region, res, smap, mpc)`, 29 regiones, hueco para 30).
  `parchear_angel_update32.py` añade la 30 (`smap\world89/88/90`,
  `world*_30.mpc`) con una cueva en el relleno de `.rdata` (marcada
  ejecutable). Sin probar en partida: la pestaña puede necesitar algo más.
- **Chaos nuevas (Past the Time Spirit, Rainbow Town 308).** Pobladas 430,
  431, 439, 440; destinos en `dialogos.VIAJES_POR_OPCION` con la casilla del
  TAG 1 de cada `.mpc`. Menú en dos páginas (`PAST_TIME_PAG1/2`, mensajes TW
  158419–158425).

### Tercera ronda (26/10): lo que faltaba para jugar la región

- **Paredes**: `tools/transitable.py` regenerado (408 mapas): sin esto el
  servidor trataba los mapas nuevos como todo transitable y los mobs
  atravesaban las rocas. Mapas repoblados después, para que nadie nazca
  dentro de una pared.
- **Instancias que no reviven**: `tools/instancias_de_stage.py --json`
  (429, 430, 431, 439, 440 quedan `dinamica`).
- **NPC de la región** (36): `tools/npcs_del_cliente.py --poner` en 423–429.
  Los de servicio de Bluesand Realm (entidades 90425000–90425004) hablan en
  `dialogos.propio`; los investigadores abren las tiendas 227/228 de
  `shop.xml` TW (skills nuevas I–IV). Textos propios en
  `work/msg_propios.json` (`tw_migracion.py msg_propios`).
- **Skills V nuevas**: las 18 tienen rama, nivel (390/400), rango 5 y
  pergamino en `content.db`; `/skills5` ya las enseña sin cambios.
- **Interfaz** (`tw_migracion.py ajustes_wnd`, copia de lo que hizo TW):
  lista "Map Types" del Superwing `rows=40` en `wnd05.xml`; pestaña 25516
  "Sand Castle Tales" en `wnd01.xml`, junto con las otras tres pestañas
  nuevas del mapa. Las cuatro usan `appdata=5`, como en Taiwan; no `7`.
- **Drops**: las tablas de drop de los mobs nuevos (28174…) no vienen en el
  cliente TW (son del servidor oficial). Se usa el respaldo por nivel de
  `drops_monstruos.json` (cubos 400–470). Los mobs de tropa de las Chaos no
  sueltan al 100% (`combate.es_de_tropa`).
- **Item Mall**: el catálogo TW no está en el cliente (solo
  `malllayout.xml`); `mall_selection.py` no mezcla IDs de TW. Pendiente de
  decisión.

### Mascotas de Taiwan (26/10)

- `tools/pets_de_pet_xml.py` regenerado: 1.795 mascotas (+44: los cinco de
  los Tres Reinos, la linea Mecha y la linea Raccoon) y 164 tablas de
  habilidades (+15). El generador ahora recorta los valores: TW trae clases
  como `' 輔助攻擊型'` y el servidor las buscaba tal cual en petattrib.
- **Choque de ID 83266**: aqui es la Rank Promotion Medal, en TW un huevo.
  La memoria emparejaba '機兵蛋' con "Rank Promotion Medal" y lo puso en el
  huevo 83173 y la mascota 30081. `tw_migracion.IDS_PROPIOS` excluye esos IDs
  de la memoria; `work/revertir_choque_83266.py` devolvio los campos. Si se
  crea otro objeto propio, anadir su ID a `IDS_PROPIOS`.

### Traducción de las 18 skills nuevas (26/10)

- Completadas las descripciones de los 90 pergaminos (item9, 80625–80714),
  siguiendo el formato IGG: `Skill rank N, [description], right click the
  scroll to learn.` El objeto 80715 es Healing Oil y queda fuera de este parche.
- `tools/traducir.py` compone el texto del pergamino a partir del nombre de
  la skill y su descripción traducida. Solo lo da por completo si ambos
  están resueltos; conserva la memoria exacta de los pergaminos antiguos.
- Los manuales ahora tienen la prioridad documentada sobre la memoria:
  se evita el par incorrecto `反連鎖戰術Ⅴ → Wallpaper Frame Egg`. Las referencias
  usan `Anti-Chain Tactics`, como las skills 596–600 del cliente instalado.
- Manual ampliado en `work/traduccion/manual/skills_nuevas_tw.json`.
  Aplicadas las traducciones que Claude había dejado pendientes de instalar:
  276 campos en 236 filas de magic, dentro de las 276 filas que corresponden
  a estas 18 skills y sus efectos; 90 campos de item9 y 366 textos en
  `corpus/content.db`. No cambian los parámetros de juego.
- Instalado en `extracted_paks/update26/setting/eng`, `content.db` y
  `C:\AO\Angels Online\update26.pak` y `.bak`. Respaldo de los XML, ambos
  PAK y la base de contenido en `work/backup/skills_20261026_180929`.
  El helper `work/traduccion/aplicar_skills.py` y el manifiesto
  `work/traduccion/skills_instalacion.json` conservan el alcance y hashes.
- Verificación: diez pruebas de traducción; números, marcadores `%1` y
  separadores de línea conservados; CRC de las 939 entradas de cada PAK;
  contenido idéntico en todas las entradas ajenas a las dos tablas;
  comprobación de integridad de SQLite. Reiniciar el cliente para cargar los textos.

### Ejecución de las skills TW 390/400 (26/10)

El servidor aun usaba `client_tables.json` anterior a TW: faltaban las 276
filas de estas 18 lineas (incluidos los subhechizos) y los efectos 715–733.
Por eso `efecto_existe()` descartaba sus sprites y los encadenados no se
resolvian. Ultimate Healing se clasificaba como buff sin efecto y Time Rift
Strike como un AoE de radio 1, sin salto ni raiz. Los logs de las 18:17–18:18
confirmaban ambos casos.

- `tools/actualizar_skills_tw.py` sincroniza esas 276 filas y el catalogo de
  efectos de la tabla portable. Conserva todas las filas anteriores y las
  otras secciones. Los sprites 715–733 se verificaron tambien en los PAK
  instalados en `C:\AO\Angels Online`.
- `server/taiwan_skills.py` ejecuta las 18 lineas en sus cinco rangos. Usa
  los datos originales para potencias, coeficientes, duraciones, intervalos,
  umbrales de HP, probabilidades, radios, SP, MP y tiempos de impacto.
  Se conecta desde el manejador real de `0x0006` de `app.py`.
- Implementa Wind Armor y el golpe de Whirlwind Sword Dance; combos y
  componente de mano secundaria; Earthsplitter frontal con tres impactos;
  Skullcrusher condicionado por HP restante; ruptura de armadura y su onda;
  carga de lanza; disparo con retirada; rafaga de area pequena; golpe extra
  de Deathcall; bombas con drenaje de mana y detonacion manual/automatica;
  rescate de un miembro del grupo intercambiando posiciones, curandolo y
  protegiendo al lanzador; Ultimate Healing con segunda cura condicionada;
  pulsos de Terror desde las invocaciones; Soul Burst consumiendo ambas;
  Time Rift con salto instantaneo, impacto y raiz; Flame Brand con tics y
  explosion; Rockskin; Steel Beak con raiz, reduccion de defensas y
  recuperacion de HP/MP al matar.
- Publica las dos fases de los efectos nativos y la animacion corporal del
  arma en habilidades fisicas. Adapta las entidades al receptor para que
  otros jugadores vean los efectos. Respeta las reglas de PvP/estructuras;
  las raices tambien bloquean el movimiento de jugadores. Anti-Chain Tactics
  reduce la precision de los golpes posteriores de un combo entre jugadores.
- Valida recursos antes de cobrarlos, comparte cooldown entre rangos y
  cancela impactos pendientes tras muerte, desconexion, cambio de personaje,
  mapa/sala o respawn. `Monstruo.vida_combate` distingue cada vida del blanco.
- Validacion: 130 casos nuevos, incluyendo ejecucion de los 90 rangos,
  paquetes reales de cast, animaciones, PvP, costes y cancelaciones; junto
  con regresiones relevantes, **186 pruebas correctas**. Cuatro pruebas
  antiguas fallan igual cargando `app.py` y `combate.py` de HEAD: critico
  base esperado 6 frente al actual 5; dobles de personaje incompletos para
  dos casos de SP; y un doble de sesion sin `volcar` en el caso de muerte.
  Se excluyeron explicitamente de la corrida de 186.

Reiniciar el servidor y volver a entrar para cargar el modulo y la tabla
actualizados. La validacion es de servidor y paquetes; no se automatizo una
sesion visual del cliente. La revision siguiente detecto que tambien faltaba
el script visual en los PAK; la instalacion anterior no bastaba.

### Correccion del script visual, NPC y flores (26/10)

El cliente nativo busca `castNNN` y `magicNNN` en `SCRIPT\MAGIC.SO` al
recibir `0x0011` (handler IGG `0x5F0420`). El script IGG llegaba a 714:
estaban los sprites nuevos, pero faltaban las funciones 715--733. Flame
Brand usaba efectos anteriores (19/546), por eso era la excepcion visible.

- Instalado el `magic.so` de TW en ambos `update26.pak` del cliente y en
  los extraidos. Conserva los 4.268 simbolos anteriores con las mismas
  firmas y agrega 130; incluye los 38 exports de cast/impacto nuevos.
  `script/main.l` es identico en ambas versiones. `tools/smart_script.py`
  valida la tabla; `tw_migracion.py` ya incluye esta sustitucion.
- `tools/reparar_region_tw.py` preparo, respaldo e instalo solo ese script
  y las traducciones de flores/comerciantes en `msg.xml`. Los 940 recursos
  de cada PAK pasan CRC y los ajenos al cambio conservan su contenido.
  Respaldo: `work/backup/region_tw_20261026_191156`; manifiesto:
  `work/region_tw_reparacion.json`. La primera copia fue bloqueada por el
  juego abierto; se instalo tras confirmar el usuario que lo cerro.
- Los temporizadores de las skills vacian la cola de la sesion real al
  emitir efectos. La cura muestra su numero verde tambien con HP lleno,
  manteniendo el HP limitado al maximo. Rescue permite seleccion propia.
  Retirados los avisos de chat propios de este modulo.
- Restaurados los arboles y raices NPC nativos de mapas 423--429. Los
  investigadores de Bluesand abren las tiendas originales 228/227 antes
  de intentar el emparejamiento antiguo por retrato (que elegia quest625).
  Los ocho totems usan la visibilidad capturada en Lyceum: nombre al pasar
  el cursor, sin rotulo permanente bajo el modelo.
- Fragrant Greenhouse tiene 39 puntos de interaccion con flores, de tres
  colores; 41 referencias de objetos en el MPC, dos repetidas en decorado.
  Se conecto el evento 5011, asignado al decorado 12986 sin interactivo,
  usando el mismo objeto de clic 60305 de las otras flores. Las decisiones
  nativas conducen a 17 TAG, incluido el regreso a la entrada. Sus casillas
  coinciden con el MPC y permiten caminar. Informe reproducible:
  `python tools/auditar_flores_fragrant.py` -> `work/flores_fragrant.json`.
- Verificacion: 226 casos de skills, traduccion y region; otras 75
  regresiones de eventos, buffs, totems y portales; todos correctos.
  Incluye clic real a cada flor, cuidados correctos/incorrectos y paquete
  de traslado con cambio efectivo de posicion, no un mock de teletransporte.
  Compilacion de app/combate/cuentas/presencia y modulos nuevos correcta.

No se observo una sesion grafica del juego: los paquetes, datos y exports
instalados estan comprobados; la apariencia final se valida al abrir el
cliente. El servidor debe cargar el codigo y los arboles nuevos al arrancar.
Arranque realizado a las 19:27:44: login/mundo escuchan en 16768/16769;
`reparar_region_tw.py verificar` sigue correcto tras sincronizar el cliente.

### Flores amarillas y Healing Cross (26/10)

- La captura posterior mostro `517396`, flores amarillas, aun en chino.
  Traducidos ese prompt y el libro de cuidados (517382--517395), incluidos
  capitulos y cantidades de agua, deshierbe y control de plagas. Instalados
  ambos PAK y el XML extraido tras cerrar el usuario el cliente. Solo cambia
  `msg.xml`; el script visual anterior se conserva. Respaldo y preparado:
  `work/backup/region_tw_20261026_194145`.
- La auditoria ya reconoce las flores por sus opciones nativas, evitando
  excluir colores por una lista incompleta de mensajes. Con las amarillas
  son 52 interactivos y 18 destinos internos (54 referencias de objetos,
  dos repetidas). Conectado tambien el evento amarillo 3012, que solo tenia
  decorado. Los casos anteriores de 39/17 correspondian a tres colores.
- Healing Cross I--V (13310--13314) no entraba en las curas: la formula 58
  no estaba implementada y la frase `spell attack` lo clasificaba como
  ataque. Ahora se reconoce por formula y calcula la cura a partir de sus
  parametros: base + MATK * coeficiente / 100, limitada al 80% del HP maximo
  del receptor. Se respetan coste, cooldown y prohibicion de objetivo monstruo.
- Los paquetes de cura ahora conservan el byte alto del efecto 499 (antes
  se truncaba a 243). En el flujo de curacion se manda el tiempo real de
  casteo en el campo correspondiente, junto al ID del hechizo; el numero
  verde va en su paquete independiente. Objetivo cero de una cura propia
  no se interpreta como area de ataque en la casilla (0,0).
- Verificados 14 casos de Healing Cross y 343 casos conjuntos correctos,
  excluyendo el caso antiguo de critico base ya documentado. Incluyen HP
  bajo, cinco rangos, seleccion propia/automatica, otro jugador con un
  maximo diferente, HP lleno, monstruos, MP y cooldown, efecto y casteo.
  Reiniciar el servidor propio desde su terminal para cargar este codigo.
  No se deja ninguna instancia adicional en segundo plano.

### Avisos de resultado de las flores (26/10)

Las capturas TW posteriores muestran 517405 (fallo: el Flower Spirit
expulsa al jugador) y 517404 (acierto: lo guia hacia el interior) abiertos
tras el traslado. En el servidor se enviaban los mensajes, pero el cierre
del portal los borraba inmediatamente. En esos dos nodos de Fragrant
Greenhouse se aplica primero el salto y despues se abre el resultado,
conservando el texto traducido y el avance normal para cerrarlo. Los demas
dialogos mantienen su orden. Verificados los avisos de acierto/fallo de las
52 flores, su destino y cierre manual: 110 pruebas de region correctas;
tambien pasaron 23 regresiones de eventos y portales.

Pendiente de sistemas (necesitan código/captura, no solo datos): World Boss
(`worldboss.xml`, `script\WorldBoss.l`), los 11 mapas nuevos de `stage.xml`
(el servidor aún no los puebla), nuevos NPC/quests de `sp_v29_questnpc.xml` y
`sp2026_*.xml`, textos en imágenes `.tga`.

## Estado al cerrar esta investigación

- Confirmado que Taiwan llega a `update32`.
- Confirmado que los PAK modernos son legibles con una corrección pequeña al
  tamaño de su índice.
- Confirmado que Eternal es útil pero no cubre toda la rama 29–32.
- Confirmado que el ejecutable Taiwan es la base más razonable para sistemas
  modernos.
- En el corte del 26/10 no se modificó ninguna instalación externa ni ningún
  PAK. La migración quedo aplazada en ese momento; el avance posterior figura
  en la seccion siguiente.

## Update32 Taiwan del 04/11/2026: preparacion Python y port a Rust

El nuevo `update32.pak` fue respaldado antes de que el launcher Taiwan pueda
reemplazarlo (SHA-256
`f9b9bc0c4d543ec441dcb0ebfab81542e66aa805efffa3e72942286f6f965ffb`). Se
integraron en el servidor F las 65 recetas del aniversario 2026 bajo el grupo
2417, el NPC Anniversary Angel y sus textos ingleses. El grupo 683 de IGG se
mantiene intacto. El cliente `C:\AO\Angels Online` ya tiene los PAK
actualizados; sus respaldos estan en
`G:\Ao Proyect Improved\AO 2\work\backup\20261105_204726` y
`G:\Ao Proyect Improved\AO 2\work\backup\canjes_tw_20261105_204743`.
El `angel.dat` de C ya cargaba `update32.pak` y no se reemplazo. La
implementacion y los pasos pendientes de sincronizacion estan en
[PORT_RUST.md](./PORT_RUST.md).

Al reconstruir el PAK del cliente, incluir
`extracted_paks/update32_main_l_pestana_sand_castle.l` como `SCRIPT\MAIN.L`
para conservar la pestana Sand Castle Tales. Las insignias por piso, las
tarjetas de puesto permanentes y la transformacion sellada aun requieren
implementar y probar sus usos en Python; despues se sincronizan a Rust.

## NPC de spmsg, dialogos en chino, tope 481 y canjes del Lyceum (26/10/2026)

- **Matia y demas NPC de los sp_*.xml.** Su arbol esta en `setting/eng/spmsg.xml`,
  no en un .mpc. `tools/propagar_dialogos_mapa.py --sp` lo vuelca a
  `server/plantillas/dialogos_sp.json`; `dialogos_mapa._arbol()` lo pone debajo
  del de cada mapa y `app._msgid_sp()` + `dialogos_mapa.raiz_sp()` lo usan al
  hacer clic, solo si `dialogos.propio()` no tenia mas que la linea raiz.
  Matia decia 159001 ("no tienes nivel 380") porque la mision 1590 ya estaba
  cogida y misiones.py no tenia nada que ofrecer; ahora sigue el arbol
  (en curso 159013, terminada 159014). Test: `tools/test_dialogos_sp.py`.
- **Dialogos en chino.** 371 segmentos alcanzables desde NPC que existen
  (region TW + sp colocados) en `work/traduccion/manual/npc_dialogos_00{0,1,2}.json`.
  Ojo: `RN` (`\d+`) junta el color con el numero (`/c$2390等` -> `/c$#等`), asi
  que el valor debe llevar `/c$#...`. Quedan ~3.600 lineas de eventos TW cuyos
  NPC no estan colocados.
- **Tope de nivel 481.** level.xml (TW update32) llega a 481; `level_curves.json`
  acababa en 471. Ampliado 472-481 (nivel, skills, mascotas A/B/C) y
  `combate.NIVEL_MAXIMO = 481`.
- **Canjes.** exchange.xml instalado = filas IGG + filas TW con numero nuevo.
  En los grupos donde IGG y TW comparten recetas (Fashionable 439, Gear Clerk
  181/182, Astral Angel 393) TW anadio 410 recetas que reusaban numeros IGG:
  `work/anadir_canjes_tw.py instalar` las mete como 34979-35388. Fortunia no
  tiene nada nuevo: sus grupos altos (495+) ya contienen todo lo de TW y los
  bajos (4-294) son contenido distinto, no ampliado.

## Item Mall de Taiwan invisible y pestana del mapa (26/10/2026)

- **Item Mall.** El 0x005F del cliente (REA `FUN_00620e80`, registrado en el
  slot +0xda0 de la tabla de handlers) guarda cada producto en una tabla
  indexada por id y descarta `id >= 0x9C41` (40001); ademas solo avanza el
  puntero en los aceptados, asi que tras el primer rechazo se pierde el resto.
  Las 257 filas de Taiwan iban en 50000+: no salia ninguna. Renumeradas a
  36000-36256 (hueco libre de IGG entre 34022 y 39000); `tools/mall_tw.py`
  usa `ID_BASE = 36000` y `test_product_ids_fit_the_client_table` lo vigila.
- **Pestana "Sand Castle Tales".** Faltaba `<child>25516</child>` en la ventana
  del mapa, y ademas estaba en la pagina 8: `script\main.l` (update25) tiene
  `MAX_MAPPAGE = 5` y las paginas IGG son appdata 3..7. Ahora va en la 7 con
  Sun Sea Maze / Cybertronica / Night City Code, cuatro botones de 98 px
  (`tw_migracion.py ajustes_wnd`).

## "????" en las bolsas del Item Mall (26/10/2026)

El cliente pinta como `?` lo que sigue en chino/japones. `work/pendientes_mall.py`
recorre producto -> objeto -> `動態資料1` (fila de drop.xml/serv_drop.xml) ->
objetos de dentro y saca lo pendiente de `原型名稱`, `基本名稱` y `說明定義`:
3.768 objetos alcanzables, 175 textos traducidos en
`work/traduccion/manual/mall_contenidos_000.json` (instalado). Ojo: la memoria
TW<->IGG tiene pares malos por reutilizacion de IDs (p. ej. 吉祥如意結 ->
"Zionic-Tsubasa's Attack", 粉柔-貴雅小鹿斑比 -> "Shiny Mana Rune"); los que
aparecieron van corregidos en ese manual, que manda sobre la memoria.

### Restauracion del Mall y revision de Sand Castle Tales (05/11/2026)

- El `update26.pak` activo de `C:\AO\Angels Online` habia perdido 25 filas
  alcanzables desde el catalogo del Mall y conservaba campos traducidos solo
  en `update26.pak.bak`. Se restauraron selectivamente las filas y textos,
  manteniendo los atributos no textuales del paquete activo. El PAK instalado
  tiene SHA-256
  `14208477459d8ac2602cf6996d37693a16cd6b9c11c38ed4cd41d41fb42c9853`;
  el original se guardo como
  `C:\AO\Angels Online\update26.pak.pre_mall_restore_20261105.bak`.
- `server/cliente_local.py::aplicar_modo_estacion` vuelve a escribir las
  tablas `ITEM5.XML`–`ITEM9.XML` desde `extracted_paks/update26` al iniciar.
  Por eso tambien se instalaron alli las tablas reparadas. La auditoria de
  inicio verifico que los 3.582 objetos alcanzables en esa vista no faltan en
  esas tablas ni conservan campos CJK traducibles sin traducir.
- En el cliente C se verificaron la pestaña `25516`, `rows="40"` del
  Superwing, los hooks de region 30 en `angel.dat` y los recursos
  `WORLD88/89/90.SHP` y `WORLD*_30.MPC` de `update31.pak`/`update32.pak`.
  `SCRIPT\MAIN.L` de `update32.pak` coincide con
  `extracted_paks/update32_main_l_pestana_sand_castle.l`. El mapa aun no se
  comprobo visualmente en partida; si sigue en blanco, hace falta una captura
  para distinguir el mapa del mundo de los mapas de la region.
- Revision adicional (05/11/2026): 18 bolsos/huevos de `ITEM9.XML` tenian
  `動態資料1` enlazado a `drop.xml`, pero `說明定義` no incluia `%s`; el cliente
  por eso no mostraba los contenidos aleatorios. Se agrego
  `/c$2%s/c*`, preservando las descripciones existentes, en la fuente de F y
  en `update26.pak`/`update26.pak.bak` del cliente C. Los 18 enlaces y las
  941 entradas de ambos PAK se validaron. Respaldo:
  `work/backup/mall_details_20261105_214726`.
- El cliente C del servidor es distinto del cliente Global. En esta revision
  solo se modifico `C:\AO\Angels Online`; los procesos Global que estaban
  abiertos no se tocaron. `midage.ini` configura 1280x768, mientras el mapa
  instalado para esa anchura es 1280x720; no se cambio la resolucion por
  suposicion. Falta confirmar visualmente el mapa dentro del cliente C.

### Sincronizacion adicional F/cliente C (05/11/2026)

- `tools/tw_migracion.py ajustes_wnd` conserva `appdata=5` en las cuatro
  pestañas nuevas, con 105 px de ancho y 15 px de separacion. Se aplico al
  cliente C y se verificaron las 941 entradas de ambos PAK. Copia previa:
  `work/backup/map_tabs_before_install_20261105_222210`.
- En `item4.xml`, el ID 31916 tenia `Potent ` + `Blue Potion` en
  `UPDATE16`, aunque el baseline Taiwan y `content.db` dicen `Potent ` +
  `Blue Potion 6`. Se corrigio la fuente F y el `UPDATE16.PAK` del cliente C.
  Copia previa: `work/backup/potion31916_before_install_20261105_222611`.
  Los IDs 31716-31719, 48421, 74146 y 74147 ya coincidian con las traducciones
  inglesas listadas en el baseline.
- `server/pase.py` vuelve a sortear las listas diarias/semanales ausentes del
  periodo vigente, y la prueba cubre el paquete enviado al cliente. El mapa y
  las misiones aun requieren confirmacion visual dentro del cliente C.
