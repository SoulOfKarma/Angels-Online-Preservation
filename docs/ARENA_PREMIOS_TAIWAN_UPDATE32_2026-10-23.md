# Premio de Angel Arena: auditoria Taiwan update32

Decision posterior: Karma autorizo usar temporalmente el nivel anterior o un
equivalente. La implementacion separada y sus limites estan en
[Premios provisionales401+](ARENA_PREMIOS_PROVISIONALES_401_2026-10-23.md).
Las conclusiones siguientes conservan lo recuperado originalmente; no son
una afirmacion de que el lote provisional sea el premio oficial401+.

Fuente autorizada por Karma: `G:/ALO Taiwan/天使之戀Online`.
Lectura de los indices de data1,update,update2..update32, en orden numerico,
sin extraer sobre el cliente, modificar cuentas ni activar un premio supuesto.
Esta revision analiza PAK/XML; no pretende haber recuperado codigo del servidor
oficial mediante una nueva sesion REA.

## Procedencia

- update32.pak: SHA256
  `0805e3a1361ce5db2b22522c254360be75ceda5fabdb949f731ff0a03df0bc62`.
- data1.pak: SHA256
  `782cf014be65031ac81f7d512db9111cfa41298880fa1236360a8f1dbcab7d6d`.
- msg.xml,item.xml..item9.xml,exchange.xml vigentes: setting/big5 de update32.
- map/map114.mpc y setting/eventdef.xml: data1.
- Cada contenido leido se valida contra longitud y CRC del indice.

## Hallazgos confirmados

Mensajes de msg.xml:

- 7564: los32 clasificados pueden reclamar; solo el campeon se convierte en
  Battle Angel. Es distinto de la guia IGG antigua que describe top10.
- 7751: reclamar premio de victoria.
- 7755/7756/7757: segundo recibe armadura,montura,insignia; tercero armadura e
  insignia; clasificados armadura. Estas lineas describen una categoria antigua.
- 7763/7767/7771: campeon recibe arma,armadura,montura,insignia.
- 7758..7760: eleccion ligera/pesada/magica.
- 7762: bolsa sin espacio y plazo de4 horas desde el fin para reclamar.
- 7775: plazo vencido; 7776: premio segun habilidades y puesto.
- 7575/7747: restriccion de registro mientras siga vigente el premio.
- 8366/8367: existe dialogo de categoria401+, pero no contiene IDs del lote.
  Sus tarifas Taiwan tampoco deben sustituir las tarifas IGG configuradas.

Objetos comprobados tambien por ID en el XML IGG local:

| ID | Nombre IGG | Que demuestra |
| --- | --- | --- |
| 8659..8661 | Angel No.1/2/3 | Insignias por puesto; version de nivel60 |
| 17350 | Angel Arena Credit Ticket | Ticket canjeable en Sign-up Office |
| 20191 | Angel Skill Exp Ticket | Participacion;1000 Skill EXP a una habilidad elegida |
| 66330..66332 | Angel No.1/2/3(Lv280) | Ultima familia de insignias temporales localizada |
| 77691 | Warrior Angel Blessing | Existe objeto de atributos permanentes; NO prueba entrega por ganar |

Familias temporales localizadas en item7.xml:
66275..66297(nivel260,23 filas),66298..66332(nivel280,26 filas seleccionadas).
No todas las posiciones del intervalo son necesariamente premios: se debe
filtrar por prefijo y descripcion de Arena, como hace la consulta.
Hay otras familias de equipo en niveles inferiores.

El campo de duracion9240 coincide con9240 minutos=6dias10horas. La
[guia oficial japonesa](https://alo-nhn.ujj.co.jp/playguide/gamesystem/pvp_cs.php)
documenta explicitamente ese plazo, los certificados/reclamacion dentro de4h,
el equipo segun habilidades/puesto y las insignias para los tres primeros.
No se usa esa guia para inferir importes o IDs de una categoria401+ IGG.

## Limite concreto: falta la asignacion401+

Los nodos1000103,1000143,1000169 de map114 llaman accion83 sin parametros.
eventdef.xml la nombra EVENT_ACT_GIVE_ARENAPRIZE. Ni cantidades,ni objetos,
ni seleccion por habilidades aparecen en esos nodos: delegan la entrega.

No se recupero el lote de401+ ni la cantidad por puesto de tickets17350/20191.
La busqueda de materiales exactamente17350 y premios exactamente77691 en
exchange.xml no encontro recetas. El registro de exchange con ID17350 no es
un canje de ese ticket: usa otro material; no confundir IDs de tablas distintas.
El nombre de Blessing tampoco autoriza regalar un consumible permanente.

Por tanto, no se activo un lote Lv280 para jugadores401+ ni se inventaron
cantidades. `premios_arena` permanece null. El mensaje de la captura sale de
`competicion_premios.informar_reclamacion`: estado sin_tabla, no entregado.
Las tablas se congelan al abrir una ronda; cambiar configuracion no arregla
retroactivamente su plan. Cualquier reparacion de premios historicos necesita
un plan verificado, seleccion por puesto/habilidad y entrega idempotente.

## Reproducibilidad

`tools/audit_arena_tw_rewards.py`: lector estrictamente de solo lectura,
indices grandes lo|hi<<16, orden numerico, CRC/tamano, salida JSON ASCII.

Ejemplos:

```powershell
python tools/audit_arena_tw_rewards.py --tables msg.xml --ids 7564 7755 7756 7757 7762 7763 7775 7776 8366 8367
python tools/audit_arena_tw_rewards.py --tables item2.xml item3.xml item7.xml item8.xml --ids 17350 20191 66330 66331 66332 77691
```

`tools/test_audit_arena_tw_rewards.py`:4 pruebas aprobadas(indice>64KiB,
CRC erroneo,entradas de directorio,precedencia de parches y ninguna escritura
en las fuentes). Compilacion y diff-check verificados.
