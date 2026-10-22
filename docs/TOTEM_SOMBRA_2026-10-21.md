# Totem de Crashing Hillock: ajuste de posicion

La prueba quitando la sombra adicional no resolvio el problema visual,
segun la comprobacion del usuario. Se descarta ese experimento.

Por propuesta del usuario se cambia exclusivamente el totem del campo 8
de `(93,176)` a **`(92,174)`**. La posicion anterior procedia de una captura;
la nueva es un ajuste visual local confirmado por el usuario tras probarlo,
no una nueva medicion del servidor oficial.

`totem_war.TOTEM_CAMPO[8]` alimenta la creacion del monstruo y su paquete
0x012E, incluidas nuevas entradas al mapa y recreaciones tras captura.
No se cambian otros campos, arenas 200..207, mapas de entrenamiento,
sprites, reglas de captura ni ventanas del totem.

El sincronizador del cliente deja de quitar sombras. Para clientes que ya
recibieron el experimento, restaura exclusivamente la linea exacta de flags
que aquel dejo en 60237..60240 con proceso SERV_CLASS_TOTEMOBJ. Conserva
otros objetos, otras personalizaciones, nombres Big5 y todo el resto del
pak; no restaura el archivo entero desde un respaldo viejo.

## Prueba en el juego

Cerrar el cliente y reiniciar el servidor permite restaurar los flags en
update26.pak mediante el actualizador habitual (con respaldo .bak). Luego
abrir el cliente y entrar otra vez a Crashing Hillock para recibir el totem
en `(92,174)`. Si el pak esta bloqueado por el juego, la restauracion de
sombra no se aplica, aunque el cambio de posicion es del servidor.

Comprobar visualmente el pedestal y el clic en su nueva casilla. Las
pruebas automaticas comprueban coordenadas, paquete, facciones, recreacion,
posiciones de otros mapas y restauracion acotada del experimento; no
sustituyen esta validacion visual.

Validacion de entrega: el usuario confirmo el ajuste en el juego. Las suites
de visual del totem, items del cliente, Totem War e instancias dieron
**42 passed**, con un aviso de deprecacion de asyncio en una prueba existente.
