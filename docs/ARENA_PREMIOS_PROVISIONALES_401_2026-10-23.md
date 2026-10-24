# Premios provisionales401+ autorizados por Karma

Peticion: usar por ahora el premio del nivel anterior o un equivalente.
Se habilita una politica separada `arena_lv280_para401_v1`: equipo original
IGG Lv280 para la categoria401+ (map240). NO se presenta como tabla oficial401+.
`premios_arena` sigue reservado para una tabla exacta; la sustitucion usa
`arena_premio_compat.habilitado` en competiciones_config.json.

## Lote

| Puesto | Entrega provisional |
| --- | --- |
| 1 | Arma,4 piezas de armadura,accesorio,capa,montura e insignia1 |
| 2 | Las mismas defensas,montura e insignia2,sin arma |
| 3 | Defensas e insignia3,sin arma ni montura |
| 4..32 | Defensas,sin arma,montura ni insignia |

- Arma: preferencia por la equipada; si no corresponde,se usa una rama
  aprendida de mayor nivel. IDs66298..66303, por Sword/Axe/Spear/Bow/Staff/Shadow.
- Armadura: rama aprendida de mayor nivel entre Mantle32/Garment33/Vestment34;
  fallback coherente con arma si no hay rama. IDs66305..66316.
- Accesorio66319 y capa66320. Montura fisica66317 o magica66318 segun arma,
  no segun armadura. Insignias66330/66331/66332.
- El campeon con Shield y espada/hacha recibe tambien escudo66304.
- No se escalan estadisticas,no se cambian requisitos ni se parchea el cliente.
- No se inventan cantidades de tickets17350/20191 ni se regala Blessing77691.
  EXP/oro/creditos de este lote son0; Holy conserva su politica independiente.

La distribucion y seleccion anteriores son compatibilidad autorizada,
no una asignacion por puestos recuperada del servidor oficial.

## Duracion,cobro y seguridad

Se reclama en High-Tier Clerk, opcion7751, dentro de4horas desde el cierre.
Equipo vence a las9240minutos(6dias10horas) desde el cierre: no se renueva al
cobrar tarde,reconectar,reintentar,mover,equipar o pasar por banco personal.
Metadatos por pieza: arena_premio_fin,item,ronda; se serializa el timestamp
absoluto nativo del inventario. El reloj y entrada a mapa depuran las piezas
vencidas,incluidas las equipadas y las del banco personal.
Al vencer equipo se refrescan apariencia/stats y se limita HP/MP al nuevo
maximo,sin conservar vida o mana sobrante de sus bonos.

El cobro es manual,no por el reloj automatico. Una transaccion entrega el
lote entero y marca el ledger entregado. Bolsa insuficiente no consume el
derecho ni deja piezas parciales. No se entrega a otro propietario con el
mismo char_id ni se sobreescribe progreso de combate no guardado.

Los premios temporales se excluyen de venta NPC,puestos de jugadores,
deposito en banco de liga y conversion a bonos permanentes de coleccion.
La caducidad viaja con metadatos al mover equipo y por el banco personal.

No se anade el bloqueo historico de registro mientras el premio exista:
esta sustitucion no cambia el acceso/reentrada de las pruebas actuales.

## Resultado reciente que figuraba sin_tabla

Al pulsar reclamar,solo el titular puede habilitar un plan provisional para
su resultado401+ antes sin_tabla,si aun esta dentro de las4horas y pasa las
mismas condiciones de elegibilidad. No se modifican otros resultados,planes
ya entregados,cancelaciones,observadores ni tablas explicitas configuradas.
El plan y su entrega usan la misma transaccion. No se recorren estos resultados
cada segundo en el reloj: la reparacion solo se intenta al reclamar.

Rondas nuevas congelan la configuracion de sustitucion al abrirse y el lote
al guardar el resultado. Deshabilitar la opcion no quita un premio pendiente
ya concedido. Fuera de401+ no se activa esta sustitucion.

## Verificacion y despliegue

`tools/test_arena_reward_compat.py`:18 pruebas en SQLite temporal: componentes
por puesto,seleccion fisica/magica,cobro unico,bolsa llena,falla SQL,ventana4h,
reparacion del resultado sin_tabla,aislamiento de cuenta,progreso no guardado,
campo nativo de vencimiento,movimientos/equipamiento,banco y conversiones.

No se han editado cuentas o rondas reales ni reiniciado procesos. Se requiere
recargar el servidor para cargar los cambios Python; despues se reclama en
High-Tier Clerk. Las pruebas no equivalen a validacion visual de entrega real.

Regresion dirigida final:255 pruebas aprobadas,un aviso existente de asyncio.
Compilacion Python y git diff-check correctos.

## Respuesta del Clerk al reclamar

Se reutilizan los textos originales de `msg.xml` del cliente IGG:
7761 confirma la entrega de equipo,7762 explica la falta de espacio,
7775 indica plazo vencido y7781 rechaza la reclamacion sin derecho a premio
(incluido un premio ya cobrado,con detalle adicional en el aviso de chat).
La confirmacion solo se muestra despues de una entrega confirmada en SQLite.
Se instala un guion nuevo para que aceptar cierre la respuesta sin repetir
la entrega. Antes de la primera ronda tambien se muestra7781 sin error SQL.

`tools/test_arena_reward_dialogue.py` comprueba el router real de clic/opcion/
aceptacion,los IDs presentes en los datos,la bolsa llena,reintentos,el plazo,
resultados no elegibles y la ausencia de resultados. No se han reiniciado
procesos ni modificado cuentas reales para este ajuste.
