# Holy: objetivos, cruce y filtros del chat

## Filtros persistentes

La seleccion de Item/Char.EXP/Skill EXP en el filtro del chat NO es lo mismo que las opciones globales de midage.ini. La investigacion inicial se corrigio al seguir la nativa real de ese menu.

`extracted_luas/chat.lua::OnUpdateChFilter` llama a game.updatechfilter. La tabla de nativas de G:/Angel.exe da5849e0; su desensamblado local (Capstone) llama a650e00. El decompilado disponible de650e00 empaqueta las casillas del tab actual y llama a614da0(7,(tab<<16)|mask). Captura local127_0_0_1_16769_20261023_131805_orden.jsonl: t20.8219,21.1198,21.6499, C2S0016 con cuerpos07df800000,079f800000,071f800000, respectivamente. La mascara cambia al desmarcar Item, Char.EXP y Skill EXP.

S2C001D, long7/subpropiedad0..3 restaura el tab correspondiente:5ffc90 consume la mascara8000 y los bits inferiores. Su entrada en la tabla esta31 posiciones antes que TEAMID(long38). No es un paquete supuesto ni un filtro global de mensajes del servidor.

`chat_filtros.py` guarda inmediatamente la mascara por personaje y tab, preservando bits desmarcados, y login la reenvia tras la secuencia base. Se conserva tambien en guardar_sistemas. La escritura es estricta usuario+char_id, sin el fallback a otro personaje que tienen algunos guardados heredados. Comandos incompletos, tabs fuera0..3 y bits desconocidos se rechazan. Un personaje sin ajustes mantiene los valores por defecto del cliente. No se parcheo Angel.exe, angel.dat, los Lua ni archivos del cliente. Los intentos nuevos de decompilacion Ghidra de5849e0/523d80 agotaron330s cada uno; no se presentan como evidencia exitosa. Se uso el decompilado disponible, desensamblado acotado del binario y captura para completar la ruta.

## Edificios visibles pero no atacables

Una sala compartida de112 puede existir antes de abrir la ronda o conservar los objetos de la anterior. La escena enviaba los edificios nuevos, pero _entrar_en_sala sustituia ses.monstruos por el diccionario viejo. Los clics no encontraban monstruo y caian a pulsar el pasaje, generando repetidamente Enemy passage: destroy its guardian to advance. El log citado muestra clics al Raphael Guardian10 en t510.6653 seguidos de ese mensaje en t510.6669.

`sincronizar_monstruos` sustituye objetivos antiguos por las MISMAS instancias autoritativas de la ronda, conservando el diccionario compartido y referencias de los jugadores de esa sala. Se llama al entrar en la sala, al entrar/refrescar la competicion y al publicar edificios. Ahora la seleccion entra por combate normal; no se elimina la proteccion a aliados.

Se verifica el router de clic y ataque normal completo con arma0 y arco6, contra guardian y estatua rivales. El fixture reproduce tambien la sala creada antes de abrir HB y otra ronda con objetos antiguos. La muerte de guardian abre su puerta; la estatua reduce su contador. Construccion/reparacion sigue consumiendo materiales de Holy, sin resurreccion automatica.

## Cruce y reglas

El movimiento del cliente anuncia el destino antes de llegar. El cruce de guardian ya no salta inmediatamente al recibir esa ruta: se agenda segun la distancia en pixeles y la velocidad del personaje. Al llegar se revalida ronda, fase, vida, posicion y existencia de puerta; otro movimiento, cambio de mapa, fin de ronda o destruccion invalidan el salto pendiente. El salto sigue siendo local0003/efecto1640, sin recargar el mapa. Limpia callbacks antiguos de portal/colision; conserva proteccion contra rebote. La suavidad visual final requiere prueba en el cliente.

No se cambian las condiciones de victoria:20 capturas o limite de tiempo; al agotarse gana el mayor numero de capturas, no la puntuacion personal. Si ambos numeros son iguales hay empate. Se mantienen10 estatuas iniciales por equipo y25 como maximo, junto con puertas1/6/7/10, respaldados por la guia original ya documentada; no se activan25 de inicio sin evidencia.

## Pruebas

Bateria de171 pruebas aprobada en52,89s: filtros/reconexion, objetivos de rondas, ataques, Holy, Arena/avatar, aislamiento de cuentas, carga de mapa, avisos y accesos. Compilacion y diff-check sin errores, salvo advertencias anteriores de finales de linea. No se reinicio el servidor ni se modificaron cuentas reales. Requiere reiniciar el servidor y reconectar los clientes para cargarlo y comprobar el resultado visual. Las selecciones que se hicieron antes de este arreglo no habian quedado guardadas; hay que volver a marcarlas una vez.

Bateria complementaria:211 pruebas aprobadas en30,51s (puertas/protocolo, chat de Holy, premios, proxy, supremo, Aliua, Outpost, Totem War, ligas, instancias y mascotas), con una advertencia previa de asyncio. Total entre ambas baterias:382 pruebas aprobadas; no es una ejecucion de todos los tests del repositorio.
