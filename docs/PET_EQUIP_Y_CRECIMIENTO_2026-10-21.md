# Equip Pet y crecimiento por nivel

## Corrección de Equip Pet

El hueco central señalado en Gear no es el accesorio 9 ni Pet Amplify.
El control 16026 de `wnd03.xml` corresponde al slot **558**:
`Angel_unpacked.c::sub_57B320` mapea 16026 a 558, y el refresco de Gear
llama `sub_646850` con esa misma casilla. El texto 2732 de `string.xml`
establece el requisito de cinco estrellas.

Faltaban tres piezas del servidor: admisión de mascotas en 558,
clasificación como equipo y cálculo de sus bonos. Además, el vaciado de
ranuras extendidas omitía 558, lo que habría dejado un icono fantasma al
retirar la pet.

Se implementó:

- Arrastrar una pet guardada y viva, con Star Level general >= 5.0
  (50 décimas), a 558. Se validan ambos sentidos de un intercambio.
- Conservar ficha, mejoras, verdes e instancia al equipar, reemplazar y
  retirar. Las validaciones no reescriben la identidad de una pet activa.
- Aplicar la vinculacion al equipar cuando lo declara el item, sin gastar
  otra vinculacion al retirar y volver a equipar por el mismo propietario.
- Aplicar a los ocho atributos del personaje la quinta parte entera de
  los **bonos verdes**, no de los stats base ni de la saciedad. Ataque se
  suma a ambas manos; rigor y agilidad se mantienen separados del ataque.
- Integrar esos bonos en el paquete de stats, los límites reales de HP/MP
  y los caminos de entrada/reconexión que los recalculan.
- Retirar la bonificación inmediatamente al desequipar. Una pet equipada
  no puede invocarse simultáneamente; otra pet distinta sí puede combatir.
- Mantener sin cambios los accesorios 8/9, la montura y Pet Amplify 559–598.

### Procedencia del porcentaje

El slot y requisito están respaldados por los archivos locales anteriores.
La transferencia del 20% de los verdes está descrita en el
[testimonio de juego sobre 殖裝](https://forum.gamer.com.tw/Co.php?bsn=09734&sn=339259).
Es una referencia comunitaria original, **no una fórmula recuperada del
servidor oficial**. Se mantiene explícita como `DIVISOR_BONOS = 5` en
`server/pet_equipment.py`; el redondeo implementado es hacia abajo por
atributo. No se usa esta referencia para inventar crecimiento por nivel.

No se generaron pets nuevas ni se elevaron estrellas de pets existentes.
Battlemaid tiene sprite 3200, gráfico 44181 e **item 20012**; estos IDs no
son intercambiables.

## Saltos de stats por nivel

La tabla oficial instalada `extracted_paks/update26/setting/eng/petattrib.xml`
contiene valores por clase y nivel, no un incremento constante.
Para Battlemaid, clase 強攻型:

| Nivel | HP base | Ataque base |
| --- | --- | --- |
| 119 | 7281 | 2204 |
| 120 | 7353 | 2234 |
| 121 | 7744 | 2386 |
| 122 | 7822 | 2429 |

`mascotas.dar_exp` recalcula `stats_de` al subir; la prueba hace cruzar
120 → 121 y compara directamente el resultado con ese XML. Este salto
**ya estaba implementado**, sin necesidad de añadir un multiplicador.

Esto no prueba una subida especial de verdes o estrellas a una edad
determinada. Los verdes guardados, las intensificaciones, la evolución y
la base por nivel son mecanismos diferentes. El comportamiento exclusivo
del servidor oficial no puede deducirse como ausente solo por no verlo en
una rutina del cliente.

## Validación

`python -m pytest tools/test_pet_equipment.py tools/test_pet_combos.py tools/test_pet_progression.py tools/test_captured_pets.py tools/test_extended_inventory_slots.py -q -p no:cacheprovider`

Resultado: **79 passed**. Incluye movimientos reales por `Servidor.manejar`,
intercambio inverso rechazado por estrellas insuficientes, stats y topes de
HP/MP, retirada del bono, identidad de la pet activa, serialización JSON,
ranura vacía y salto de nivel contrastado con el XML.

La batería ampliada de pasivas/SP tiene dos fallos antiguos: interpreta
offsets de resistencias como barras de SP. Se reprodujeron los mismos dos
fallos sustituyendo en memoria las funciones modificadas de inventario por
las de HEAD, sin editar archivos ni cuentas. No se corrigieron en este cambio.

Pendiente: confirmar en el cliente la interacción visual tras reiniciar el
servidor.

## Contraste REA: crecimiento y tooltip

Análisis **estático**, sin ejecutar el juego. Se usó
`G:/REA/binarios/play_angel_unpacked.exe`, SHA-256
`2749eef56454aed55c06a80d18c2a6120896f0aac707f10006786d6b6c653af7`.

- `FUN_007114b0` carga una fila de atributos con clase y nivel, HP/MP,
  ataque/rango, defensa y demás campos. La almacena con un índice de clase
  y nivel (`clase * 501 + nivel`); admite 24 clases y niveles hasta 500.
- `FUN_0063def0` consulta `FUN_0063eb40` con la clase del sprite y el nivel
  guardado. Usa esa base y, por separado, los verdes de la instancia para
  construir las líneas de atributos.
- `FUN_0063ec70` calcula la estrella individual pasando el verde a
  `FUN_00716b10`; no deduce ese verde de la base por nivel.
- `FUN_0057b320` confirma 16026 → `0x22e` (558), diferenciándolo de los
  slots posteriores de Amplify.

Estas rutinas respaldan la lectura por nivel y la separación de base y
verdes. **No reconstruyen una regla privada del servidor oficial que
añada verdes al alcanzar cierto nivel.** Tampoco prueban su ausencia en
otros recorridos. La petición sobre una posible explosión de verdes o
estrellas queda parcialmente resuelta: salto base demostrado/aplicado;
bonificación especial de verdes aún sin determinar.

Registros locales completos (directorio `docs/rea_evidence`, ignorado por Git):

| Rutina | Registro | Evidence ID |
| --- | --- | --- |
| 007114b0 | 1792624452665_procedure_pseudo_code.json | ev_9066fc79d4eee7f13e95b61b3974325d58beb0613ec0d7072b3d709a6ae83b93 |
| 0063def0 | 1792624452625_procedure_pseudo_code.json | ev_e19ad6afe714f5b72f2c80d5d4368e331f134da4c2d9151317fa928c763cb56d |
| 0063ec70 | 1792624541516_procedure_pseudo_code.json | ev_ac496cbc0fdd7715b36e8fc470ef1a121b2ca05e4d030b467013eafa645c117b2 |
| 0063eb40 | 1792624452694_procedure_pseudo_code.json | ev_ad20aceca8b8f5f53e2ee8066de59cc5d04418b2fc41659296d9576ab75a7587 |
| 0057b320 | 1792624452683_procedure_pseudo_code.json | ev_1bf463532eba453ad62c9a784695de6365a5f20df4496c0bdc6cc729fa21ff09 |

Limitación de decompilación: `0063eb40` aparece con retorno `void` en su
propio resultado, aunque su llamador recupera el resultado de consulta.
No se interpreta esa firma inferida como prueba de que no devuelve datos;
el uso por clase/nivel se observa en el llamador y el índice en el cargador.
La sesión nativa se cerró al concluir.
