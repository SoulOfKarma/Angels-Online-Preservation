# Arena/Holy: dialogos del proxy y bloqueo real al inscribirse

## Evidencia usada (sin pedir capturas dentro del evento)

Se leyeron unicamente los paquetes de NPC/dialogo relevantes del proxy, no
claves de autenticacion ni conversaciones personales.

| Captura | Tiempo | S2C0012 observado |
| --- | --- | --- |
| mundo_185855_203071_orden.jsonl | 8.4345 /10.7707 | raiz8366, rechazo7577, retrato71 |
| misma | 23.2322 /25.1870 | raiz8361, rechazo7577, retrato71 |
| misma | 27.2167 /28.3193 | raiz7550, rechazo7577, retrato71 |
| misma | 35.9737 /37.0987 | raiz7581, rechazo7607, retrato69 |
| mundo_192143_533481_orden.jsonl | 3.8668 /14.2833 | raiz8366, rechazo7577, retrato71 |
| misma | 22.2354 /23.3394 | raiz7581, rechazo7607, retrato69 |

Las dos capturas tienen la misma raiz High-Tier byte por byte. El menu Holy
de la primera tiene observar7584; el segundo sustituye esa opcion por premios
7751 y reordena la reentrada. No se mezclan a ciegas: el servidor conserva el
perfil MPC/cliente IGG con opcion de observar. Queda documentada la variante.

El rechazo medido NO agrega una pagina automatica de horarios. Arena7577 y
Holy7607 se mandan como una sola pagina sin opciones; el siguiente0012 cierra
el cuadro. Los horarios se consultan mediante la opcion informativa normal.
Los tests comparan los rechazos y las raices High/Holy con los bytes del proxy.

REA nuevo: `docs/rea_evidence/1792716753779_procedure_pseudo_code.json`,
FUN_005ed670 de G:/Angel.exe. Verifica retrato, cantidad de opciones, salto de
ocho bytes por opcion/accion y cierre cuando mid=0. El interprete de mapas
ahora envia los IDs de acciones originales, no una lista de ceros.

## Causa de la entrada rechazada

No era solo el rango abierto. `entrada()` comparaba diccionarios crudos:

- `guardar_inventario` omite las cantidades1; en memoria pueden aparecer
  explicitamente. `{20:1}` y `{}` significan la misma cantidad para el mismo item.
- `personaje_de`/login generan la ranura376 con el deed de casa activo aunque
  aun no este en la foto guardada del inventario. Los tests viejos creaban un
  Personaje directo y no reproducian ese paso.

`cuentas.inventario_equivalente` compara item/cantidad efectiva por casilla.
Solo admite la diferencia virtual376 si coincide con el deed derivado del
personaje; no ignora arbitrariamente items equipados. Ignora cantidades
huerfanas sin item, igual que el guardado. Una pila cambiada de2 a3, un item
distinto o un saldo cambiado siguen rechazandose sin cobrar ni sobrescribir.
El chequeo se realiza dentro de BEGIN IMMEDIATE junto al estado de la ronda.
Se usa tambien en desellado, construccion y entrega de premios.

## Dialogos y cobro

`server/competicion_dialogos.py` gestiona las confirmaciones con IDs del cliente:

- Fuera de registro:7577 (Arena) /7607 (Holy), no avisos genericos por chat.
- Nivel incorrecto:7575. Oro insuficiente:7576. Falta piedra:7605.
- Reentrada sin inscripcion:7612. Competidor intentando observar Holy:7610.
- Inscribirme -> confirmacion -> aceptar -> pagina7574/7604 -> siguiente:
  transaccion de cobro e ingreso. Cancelar o cerrar el registro durante las
  paginas no cobra; una confirmacion repetida no cobra dos veces.
- Observar usa7578 (Arena) y7608 (Holy); no consume piedra ni cobra oro.
- Arena envia a Waterfall durante registro (tag1); al empezar mueve a la
  plataforma de combate, sin rellenar HP/MP.

Confirmaciones/success provienen del grafo map114; el proxy de esta revision
solo verifica el recorrido cerrado, no la temporizacion de admision exitosa
del servidor remoto. El servidor local ejecuta sus propias transacciones,
sin habilitar globalmente las acciones nativas71/86/116 para cobrar otra vez.

## Tarifas corregidas por indicacion expresa de Karma

260..279: **4.000.000**. Desde280: **8.000.000**, incluidos401+.
No son400/800 millones ni4.000/8.000 millones. El resto de la tabla previa
no se extrapola ni modifica en esta revision.

La copia inglesa de7753/7754 tiene cantidades infladas hardcodeadas; no se
presentan como importes oficiales verificados. Para esos dos clerks se usa la
pregunta original neutra7571 y se informa por chat el cobro real4M/8M antes
de aceptar. Se conservan retrato71 y acciones del grafo; no se modifica el
cliente ni se transmite un texto NPC inventado. Las paginas informativas del
cliente que contengan esos importes pueden seguir reflejando su XML antiguo.

## Persistencia de piedras

Otro fallo encontrado: `guardar_mejoras`, `guardar_inventario(...mejoras=...)`
y el guardado atomico de casa filtraban fuera `holy_pass_fin`.
Ahora los tres conservan el vencimiento. Un desellado que parecia correcto
en memoria podia perder su contador al guardar/reconectar; el test nuevo
desella, ejecuta las funciones reales de guardado, carga con `personaje_de`
y comprueba el timestamp en el paquete de inventario.

## Verificacion y despliegue

`tools/test_competition_proxy_admission.py` usa SQLite temporal y el guardado
real, ademas de los paquetes del proxy. Cubre cantidades dispersas, deed de
login, carreras reales, dialogos, costes, confirmacion/cancelacion/repeticion,
piedras, Waterfall y vencimiento tras recargar. No modifica cuentas en vivo.

Bateria ampliada:367 pruebas pasan, incluidas las nuevas pruebas de proxy y
persistencia y las regresiones de Lyceum, pets, ligas, Outpost, Holy/Arena,
carga de mapas y casas. Dos advertencias asyncio existentes, sin fallos.
Tambien pasan py_compile y git diff --check.

Reiniciar servidor y reconectar; las herramientas no reinician las sesiones
del usuario. Abrir una ronda para el nivel real correspondiente, por ejemplo
`/aastart 5 434 15` y `/aastart 5 303 15`. No se requiere disponer de una
captura de un torneo remoto activo para probar estas correcciones locales.
