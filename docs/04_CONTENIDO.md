# Contenido del juego

`corpus/content.db` (54 MB) -- extraido de los XML del cliente en
`G:\extracted_paks` por `tools/extract_content.py`.

## CORRECCION a lo dicho al inicio del proyecto

Al evaluar la viabilidad afirme que las tablas de drop, los stats de combate y
la IA de monstruos habia que **reimplementarlos desde cero**. Eso era falso.
Estan en los datos del cliente:

| dato | archivo | contenido |
|---|---|---|
| stats de combate | `monster.xml` | nivel, HP, atk medio y varianza, def, matk, mdef, precision, agilidad, 6 resistencias, velocidad/rango de mov. y ataque, prob. de critico, EXP que otorga |
| tablas de drop | `drop.xml` | items y cantidades por tabla, enlazada desde `monster.掉寶編號` |
| IA de monstruos | `simpleai.xml` | maquina de estados completa |

Lo que **si** falta y es codigo, no datos: la **formula de combate** que combina
atk/def/precision/agilidad en dano final.

`simpleai.xml` define 7 tipos de condicion (entrar en combate, HP propio entre
X e Y, HP del objetivo entre X e Y, distancia al objetivo, cantidad de enemigos
alrededor, muerte propia) con acciones probabilisticas: hablar, cambiar de
estado de IA, usar hechizo de ataque, usar hechizo de apoyo.

## Semantica de parches -- IMPORTANTE

El cliente carga los `.pak` en orden y **un archivo de un parche posterior
reemplaza ENTERO al homonimo anterior**. No se fusiona registro por registro.

Verificacion: `monster.xml` crece de forma monotona, 1.682 registros en `data1`
a 19.194 en `update26`. Cada archivo es completo y acumulativo.

> El primer intento uso merge por registro y resucitaba contenido eliminado:
> inflaba `drop.xml` de 5.426 a 6.745 tablas. Corregido a "gana el ultimo".

## Tablas

| tabla | registros | notas |
|---|---|---|
| `monster` | 19.195 | ver advertencia de categorias abajo |
| `magic` | 18.498 | hechizos y habilidades |
| `petattrib` | 11.500 | atributos de mascotas |
| `item` .. `item9` | ~82.000 en total | 9 tablas fragmentadas por rango de id |
| `doll` | 6.273 | apariencia / equipamiento visual |
| `drop_table` | 5.426 | renombrada: `drop` es palabra reservada en SQL |
| `npc` | 3.358 | |
| `quest` | 1.490 | |
| `stage` | 446 | mapas, con nombre e id |
| `level` | 471 | curva de EXP por las 43 habilidades |
| `shop` | 227 | inventario por tienda |
| `simpleai` | 131 | comportamientos |

## Advertencias sobre la calidad de los datos

Medidas, no supuestas. Ninguna es un bug del extractor:

**1. `monster.xml` mezcla categorias.** No son solo monstruos. Contiene
estructuras de asedio GvG (`Aur-Fort VII`, HP = 400.000.000, nivel "1") y
entidades cuyo nombre es un item (`Wood Bow`, `Copper Sword`). Cualquier
estadistica agregada por nivel carece de sentido sin filtrar antes por
categoria -- el "HP medio de nivel 1" da 566.162 por esta razon.

**2. Cobertura de drops del 13,7%.** Se referencian 18.926 `drop_id` distintos
y solo existen 5.426 tablas. El enlace **es real**: donde resuelve, el nombre
coincide en el 72,5% de los casos, y los que no coinciden son entradas
*adyacentes* (`Copper Spear` -> `Copper Hook`), o sea deriva acumulada entre
los dos archivos a lo largo de 28 parches.

**3. Las tablas de drop 1-231 solo existen en `data1`.** Todos los parches
posteriores arrancan en 232, pero hay monstruos que todavia referencian ese
rango bajo. Con la semantica del cliente, esas tablas **no existen** y esos
monstruos no dropean nada.

> Decision pendiente, del proyecto: se puede reinyectar el rango 1-231 desde
> `data1` para recuperar drops, aceptando que son datos de 2007. Es una
> decision de diseno, no un arreglo tecnico, y por eso no la tomo sola.

**4. La EXP excede la precision de punto flotante.** Nivel 471 =
24.549.618.000.000.000 (2,45x10^16), por encima de 2^53. Tratar siempre como
entero; nunca como `float`/`REAL`.

**5. Atributos sin traducir.** Las columnas cuyo nombre sigue en chino no se
descartan: se guardan tal cual. Perder datos por no entenderlos seria peor que
tener columnas con nombre incomodo. `magic` tiene 95 de 148 asi.

## Procedencia

Cada tabla lleva la columna `_pak` con el parche del que salio cada registro.
