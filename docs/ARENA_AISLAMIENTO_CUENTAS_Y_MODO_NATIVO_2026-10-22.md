# Arena: mezcla de cuentas y modo nativo

## Fallo reproducido con la ronda real

Ronda `d4d6c0eea21f4cbeb10bff4bd83939a8`, mapa 240: KarmaV3 primero, KarmaV6 segundo; Karma era observador. Una muerte final entre dos competidores cierra supervivencia. Los logros por entrar en el top no equivalen a dos victorias.

La base permite char_id repetido en cuentas distintas. `competicion_logros.aplicar` hacía SELECT por char_id y UPDATE de **todas** las filas con ese ID. En esta ronda el ID1007 leía primero KarmaV7 (cuenta karmav2) y sobrescribía la ficha de KarmaV6 (cuenta karmav3), incluidos inventario, nombre y datos ajenos a los logros. Esta es una causa comprobada de corrupción, no una suposición sobre `/skillclear`.

Ahora cada inscripción guarda `usuario`; toda lectura/escritura de logros se resuelve por cuenta y ranura. La publicación en vivo también usa cuenta+ID. Una inscripción de otra cuenta con el mismo ID no puede reutilizar el miembro existente. Los resultados antiguos solo se resuelven si la identidad es inequívoca, nunca con `fetchone` arbitrario.

Los planes de premio congelan propietario y mapa; otra cuenta con ese ID no puede cobrarlos. Los planes antiguos ambiguos no se entregan. También se corrigieron cuatro lecturas de logros/bonos/amplify/pase en app.py que omitían la cuenta.

## Recuperación

Karma confirmó servidor detenido. `tools/recover_karmav6_after_arena.py` restaura la ficha propia desde el archivo manual previo y el **último S2C001A anterior a la muerte**, no desde el inventario incorrecto de KarmaV7:

- Captura `logs/sesiones/127_0_0_1_16769_20261022_222417_orden.jsonl`, t403.3237.
- 36 entradas, arco69578 en ranura3, ocho piezas+15, gemas, extras y vinculaciones leídos de cada entrada. Cantidad de oro exacta: 1.892.008.122, después del pago de8M. Se conserva la venta de19 unidades de42399 (pila restante381).
- Nivel434 y ramas actuales; nombre KarmaV6, retorno seguro a114(22,36).
- Logros ajenos recuperados del archivo propio; se vuelve a aplicar de forma aislada su segundo puesto. Se retiran de KarmaV7 los logros de esta participación ajena.
- Archivo reversible de las filas dañadas: `data/backups/manual_arena_collision_20261022_224025.json`.
- El script rechaza una segunda aplicación sobre la ficha ya recuperada. El JSON espejo fue regenerado sin importar datos viejos sobre SQLite.

## REA: modo de combate que faltaba

Sobre `G:/Angel.exe`, SHA2567c1f8cc16e2032081dc15ccc1a67de668803f62d8252ab570d1f4724c162d6e9b:

- `FUN_005fbdd0` instala `FUN_005ffa00` en0x4648. Base de propiedades0x4408: **propiedad36**, no22.
- `FUN_005ffa00` controla `DAT_00a38119`, activa `FUN_0074a610` para la entidad propia y desactiva con `FUN_0074a5d0`. Actualiza música mediante005b36a0.
- Evidencias `1792719963714_procedure_pseudo_code.json`, `1792719984190_procedure_pseudo_code.json`, `1792719930799_procedure_pseudo_code.json` en docs/rea_evidence.

Se activa36 al comenzar combate y se apaga para eliminados, cierre y antes de salir. No se activa Totem War22 ni sus premios. El apagado que recalcula música ocurre después de revivir, evitando recalcular con el estado de muerto. En la muerte final ya no hay un teleport al área de espera inmediatamente antes del cambio a114.

Los avisos usan ahora la pausa de60s entre registro y combate indicada en string2149. `arena_preparacion_segundos` permite configurar0..60; GM con registro0 conserva inicio inmediato. `/aa begin` omite la espera explícitamente. Con `/aastart 30 434 5`: registro5min, preparación1min, combate30min.

## Resultados y premios

String2228 anuncia resultados;2589 describe el top10;2231 contiene el mensaje de puesto. Se publican las posiciones **del resultado persistido**, excluyendo observadores y sin fabricar un ganador por timeout.

REA005f3b40/006344a0 distingue canal11 (banner normal, variante0),13(variante1),15(variante2). Puestos se envían por13; su apariencia roja exacta y el color neutral de actores/compañeros aún requieren comparación visual con cliente. No se afirma haberlo comprobado por capturas nuevas.

Arena **no** entrega sus planes automáticamente por el reloj; queda pendiente para la opción7751 del Clerk. Holy conserva entrega automática de EXP autorizada. Selección de Arena sigue siendo por puesto final y nivel de la categoría, no por el rango de reputación del jugador.

El XML real contiene7755..7780: segundo/tercero/participación, elección de armadura ligera/pesada/mago y plazo de cuatro horas. Sin embargo esos textos describen categorías antiguas A..D y no aportan por sí solos los IDs de premios401+. `GIVE_ARENAPRIZE` del MPC delega en servidor. La tabla moderna sigue null: **no hay entrega oficial completa401+ ni canje temporal reconstruidos**. No se sustituye por equipo inventado ni se presenta `sin_tabla` como éxito.

No se afirma que todas las mecánicas de compañeros estén completas: invocaciones/mercenarios usan targeting PvP del dueño, pero la IA autónoma de mascotas todavía selecciona monstruos PvE. Falta revisar combate contra compañeros, clones y representación visual con captura de una ronda funcional. Las pruebas automatizadas no certifican esos apartados.

Verificación final:376 pruebas aprobadas, dos advertencias previas de asyncio; compilación Python y diff-check sin errores. La prueba nueva reproduce char_id1007 duplicado con el esquema compuesto real y comprueba preservación exacta de la otra ficha, idempotencia, propietario de premios, modo36 y transición registro/preparación/combate/cierre.
