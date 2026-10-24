# Pulido de Holy, Arena, desplazamientos y consumibles

Revision posterior a las capturas de KarmaV6/KarmaV3. No se reinicio el servidor, no se modificaron cuentas reales ni se parchearon ejecutables/archivos del cliente.

## Combos, daño0 y edificios

Los golpes diferidos de combo, area, barrage, ricochet, marcas y Chain Lightning leian combate.ATACANTE del ultimo paquete o tick de IA atendido. En Holy eso podia corresponder al propietario del edificio y rechazar el golpe por aliado. con_atacante envuelve esos callbacks con la sesion del lanzador y restaura el contexto anterior con finally. No se elimina la proteccion a aliados ni se fuerza daño a edificios muertos.

Ademas, publicar enviaba un spawn de cada edificio vivo tras cada golpe. Ahora conserva una instantanea por sesion/ronda: un edificio que sigue vivo recibe actualizacion de HP, no otro spawn; destruirlo lo retira y reconstruirlo vuelve a enviarlo. Se evitan reinicios reiterados de animacion/seleccion durante el combo.

Se verifica Strangle Strike V5850: nueve golpes positivos, aun intercalando una sesion del equipo dueño del golem entre cada callback. Queda pendiente la observacion visual del ritmo en el cliente.

## Recogida del cristal

La recogida por clic exige distancia Chebyshev<=1 (al lado, incluida diagonal), no3. Las posiciones del servidor anticipaban el destino de un tramo antes de llegar fisicamente. Se conserva el origen y plazo del tramo de Holy para comprobar tambien el clic; la recogida automatica se mueve al callback de llegada, cancelable si cambia la ruta. Morir o saltar invalida el movimiento pendiente. No se da la recogida desde lejos solo porque el cliente anuncio una ruta que termina sobre el cristal.

## Desplazamientos

Las formula7 de suelo no ofensivas, incluida Swiftness Spell, no tenian desplazamiento: se iban a la rama generica de area. desplazamientos.py resuelve el salto local0003, efecto XML, MP/SP, cooldown, limites de alcance, destino transitable, replica a observadores y guardado. Rushing usa el Charge range del tooltip XML (V755:5), no el alcance generico12 del cursor; conserva su coste de1000SP. Permite portar el cristal y no lo entrega, elimina ni duplica al moverse. Las restricciones de puertas/base rivales de Holy siguen aplicandose. Dimension Shift13595..13599 sigue en su ruta ofensiva existente, sin sustituir su explosion ni cambiarla por este salto simple.

El warp del guardian no se rearma indefinidamente con peticiones repetidas a la misma puerta. Se amplia la zona trasera a tres tiles alrededor del guardia con comprobacion del lado exterior, manteniendo tambien los tags/disparadores originales, espera de llegada, proteccion contra rebote y revalidacion de ronda/puerta/vida. Las parejas de arcos reflejados invierten3/7, incluido punto7; las normales conservan5/1. La correccion de frames y suavidad final requiere verificacion visual.

## Apertura y reaparicion

Por indicacion nueva del usuario, las rondas nuevas abren con las diez puertas custodiadas en cada lado (dos golems por puerta), no solo1/6/7/10 de la guia antigua. Esto sustituye expresamente la configuracion anterior documentada; no se presenta como dato oficial recuperado. Estatuas: siguen10 iniciales y25 maximas. Destruccion y reparacion con materiales mantienen sus transacciones y no borran la estructura del arco.

La reaparicion inicial usa el tag de luz del propio lado: Jabaly/team1 tag3, Raphael/team2 tag4, en vez de tag120/145 con diez estatuas o los tags de limites7/8. Los siguientes escalones de avance por construir estatuas se conservan. La admision desde Sign-up Office conserva tags1/2. Al revivir se limpian movimientos pendientes y se actualizan stats sin obligar a transformar de nuevo.

## Auras y transformaciones

Al terminar Holy se desactiva la propiedad nativa62 ANTES de poner TEAMID0, se retiran marcas42 de hostilidad propias/publicas y luego se oculta el marcador. Antes podia quedar el modo de Holy activo durante la cuenta regresiva mientras el equipo ya era0 (anillo verde). El resultado/final/cuenta regresiva no cambian.

Al refrescar las fases, cada participante recibe tambien las marcas publicas actuales de los otros jugadores, ademas de difundir las propias. En Arena se comprueban ambos sentidos tras registro: modo propio36 activo y long42 del rival activo en cada cliente. No se sustituyen por Totem War22 ni se cambian las facciones persistidas. Apariencia y seleccion real del rival requieren prueba con los clientes; las pruebas de paquetes no certifican la imagen final.

Las transformaciones guardadas/antiguas rehidratan los modificadores derivados de su magic.xml al calcular stats/maximos y al revivir. Se conserva fin y sprite, sin recastear ni renovar duracion. Shark V415 vuelve a tener la conversion melee y sus modificadores existentes (matk150/mdef200/mp_to_hp130/velocidad ataque20); no se inventa una formula nueva. Se eliminan hp/mp planos que representen costes del hechizo, no bonos de maximos.

## Consumibles

Las Red/Blue Potion74136..74155 indicadas usan formula2 con duracion0 y cantidad de recuperacion, pero es_buff resultaba true por ser objetivo self. buff_de las interceptaba, gastaba el item y creaba un buff que ya habia vencido, sin curar. Ahora esos efectos instantaneos llegan a la ruta de recuperacion real. Los numeros flotantes de HP/MP se emiten por la cantidad nominal incluso si ya estaban llenos; HP/MP reales quedan limitados a su maximo.

Los buffs temporales de items conservan la ruta de buff, maximos, temporizador y politica de consumo originales. Se añaden modificadores porcentuales, resistencias, velocidad de ataque, critico y mitigacion que faltaban en el diccionario plano leido por stats; se guarda tambien el buff inmediatamente. La piedra reutilizable63816 sigue sin consumirse y se prueba que sus bonos4000Def/2800Matk y una hora quedan guardados. No se convierte una piedra de maximos en una pocion ni se consume una pila entera.

## Verificacion y limites

Pruebas nuevas en tools/test_competition_polish_runtime.py:18 pociones de la lista, con barras bajas y llenas; combo intercalado; recogida por proximidad y llegada; Rushing/Swiftness portando cristal; warp repetido; limpieza de modo antes de equipo0; Shark sin recasteo; marcas mutuas de Arena; parejas7; HP de edificios sin respawn repetido; buff temporal persistido.

La bateria ampliada que incluyo tools/test_dano_y_regen.py obtuvo212 aprobadas y3 fallos en fixtures antiguos incompletos (P sin hp/mp y Ses sin volcar, en _sumar_sp/_procesar_muerte_monstruo). No se cambiaron esos fixtures ni esas funciones en este pulido. No afirmar que todos los tests del repositorio pasan. Compilacion y diff-check sin errores, salvo advertencias de finales de linea anteriores.

Los cambios requieren reiniciar el servidor y abrir rondas nuevas para aplicar la apertura con todas las puertas. Falta comprobar visualmente auras, direccion y recorrido con los clientes reales. No se ha certificado cada consumible del catalogo; las pociones indicadas y la ruta de buffs mencionada si tienen regresiones especificas.

Resultado final de la suite seleccionada (sin test_dano_y_regen ni test_house_system, cuyos fallos de fixtures anteriores estan documentados):516 pruebas aprobadas en133,05s, dos advertencias anteriores de asyncio. Tras invalidar tambien movimiento pendiente al revivir y cerrar las conexiones de lectura de consumibles:54 pruebas focalizadas aprobadas (36 pociones excluidas en ese pase) y dos casos adicionales de pocion roja/azul, incluido recurso lleno. Compilacion y diff-check sin errores. No se reinicio ningun proceso del juego.
