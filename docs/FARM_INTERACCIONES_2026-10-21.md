# Farm: acciones rechazadas y efectos visuales

## Causa comprobada

`logs/hestia.log`, 21/10/2026, 13:24:50–13:24:52: el personaje termina
su movimiento en `(2384,911)` pixeles, casilla `(74,28)`, y manda
C2S `014D 43 00 00 00`: regar la parcela 67. Su centro en `farm.mpc`
es `(69,28)`. La seleccion exigia distancia Chebyshev <=4 y devolvia
`None` sin aviso: la accion no llegaba a sus comprobaciones de madurez,
cuota o recompensa. El mismo filtro bloqueaba abono y cosecha.

Ahora las acciones usan `RADIO_INTERACCION=6`, independiente del radio
de siembra. Es un margen de compatibilidad con la parada observada del
cliente, **no una distancia oficial extraida de XML**. Fuera de ese alcance
hay aviso; se mantienen liga, mapa, cuotas, madurez y recompensas anteriores.
No se modifica BC, Super BC ni los otros sistemas.

## Correccion tras la prueba visual fallida

La prueba del usuario mostro que los efectos enviados mediante S2C0010 **no
eran correctos**: aparecieron lineas en el mapa y la planta dejo de verse.
La existencia de una secuencia en un OBD no valida su uso con ese paquete.
Se retiro completamente ese envio y su temporizador de despawn; tampoco se
envia una magia diferente como sustituto.

Lectura de `data/cuentas.db` tras la prueba, sin modificarla: el cultivo de
KarmaV3 seguia en liga 91, parcela 67, crop 186, sembrado 1792599260,
con 5 riegos, 3 abonos y 0 cosechas. Su madurez era el 21/10 a las 15:14:20
y su marchitez a las 19:14:20, hora local. En la prueba de las 13:45--13:49
no habia caducado: **no fue una eliminacion persistente del cultivo**.
La causa exacta de las lineas del renderer aun no esta comprobada.

Antes, regar retiraba y recreaba solo la tierra, despues de mandar la ficha
del cultivo, sin volver a insertar la planta encima. Ahora `refrescar_cultivo`
recrea primero la tierra y luego la planta y su ficha, igual que al entrar a
Farm. Abonar y cosechar tambien refrescan la planta existente. Se mantienen
el propietario, semilla, generacion, etapa, madurez y contadores: no se borra,
no se replanta y no se reinician cuotas. El redibujado se difunde solo a los
miembros presentes en la misma granja. Un rechazo no retira ninguna entidad.
Esto es una correccion defensiva de representacion; requiere confirmacion
visual en el cliente, no demuestra por si sola la causa del fallo anterior.

## Recursos localizados, animaciones pendientes

`extracted_paks/UPDATE8/setting/effect.obd`, Big5:

| Accion | Sequence | Nombre original | Recurso |
| --- | --- | --- | --- |
| Regar | 50076 | 農場澆水功能 | `effect/crops/Water000..010.SHP` |
| Abonar | 50077 | 農場施肥功能 | `effect/crops/Grow000..010.SHP` |

Las 22 imagenes estan presentes en el indice del `UPDATE8.PAK` del cliente
`C:\AO\Angels Online`. Solo se leyo ese archivo; no se parcheo el cliente.
No se identifico un efecto dedicado de **cosecha** en esta busqueda:
no se asigna otra magia como sustituto.

Los recursos 50076/50077 son de clase `SP_CLASS_MAGIC`, no
`SERV_CLASS_FARMOBJ`. **No se reproducen actualmente**: hay que establecer
su inicializacion y transporte correctos antes de habilitarlos de nuevo.
Tampoco se deben tratar como indices de magia en S2C0011.

## REA y limites de verificacion

Objetivo: `G:\REA\binarios\play_angel_unpacked.exe`, SHA256
`2749eef56454aed55c06a80d18c2a6120896f0aac707f10006786d6b6c653af7`.
Registros completos en `docs/rea_evidence/`:

- `1792600961330_procedure_pseudo_code.json`, `005f03c0`, Evidence
  `ev_e2a99715ecbbdaed49eaa49820a12232708e26cf6ed71830bbc3c2c00894ed400`:
  S2C0010 crea la secuencia indicada en +18 y coloca el objeto usando +10/+14.
- `1792600961342_procedure_pseudo_code.json`, `005b85d0`, Evidence
  `ev_339a9effbd662d29ebb9b11f1de16c781be1c75f25019bb9a735226ddf90285a2`:
  crea y registra el objeto con identificador propio.
- `1792600961350_procedure_pseudo_code.json`, `005b86f0`, Evidence
  `ev_401c4641b988a9391fc711da1920af4b250fa6d66f4e8b30d5fd99608b4faba05`:
  con argumento final1 convierte casillas a pixeles y suma medio tile.
- `1792600801196_procedure_pseudo_code.json`, `0058f350`: cosechar envia
  C2S014F con el indice seleccionado; la funcion no lanza un efecto local.

La primera consulta de referencias agoto el tiempo del proveedor. La
decompilacion posterior termino correctamente y se contrasto con el
ensamblado. Son evidencias **estaticas**, no una prueba visual en el juego.

## Pruebas

`python tools/test_farm_interacciones.py`: reproduce la posicion del log;
verifica agua, abono, cosecha madura, rechazo de cosecha prematura, aviso
de distancia, rechazo desde otro mapa, orden tierra/planta, preservacion de
generacion y contadores, ausencia de S2C0010/S2C0011 y temporizadores de
efectos, etapa madura, cuotas y visibilidad para otro miembro de la granja.
Estos tests verifican estado y paquetes, **no el dibujo del cliente**.

Tambien se ejecutan `tools/test_ligas_servicios.py` y
`tools/test_ligas_regresiones_mundo.py` contra bases temporales.

Para probar en el cliente: reiniciar el servidor actualizado, volver a Farm
y volver a entrar para reconstruir la escena que quedo mal. Si no se ha
marchitado, la planta se recupera de su registro existente; no dar otra
semilla ni editar tiempos/cuotas. Una planta aun creciendo permite agua y
abono; cosechar solo cuando madura. Las cuotas existentes no se borran.
Quedan pendientes la confirmacion visual del redibujado y la implementacion
validada de las animaciones (incluida cosecha, sin recurso confirmado).
