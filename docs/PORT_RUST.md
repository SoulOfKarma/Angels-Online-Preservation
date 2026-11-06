# Flujo de sincronizacion Python -> Rust

Python sigue siendo la referencia funcional durante el port. Cada cambio de
datos o comportamiento debe probarse primero en Python y luego regenerarse y
validarse en Rust; no se considera sincronizado hasta que ambos usen los
mismos datos y pasen sus pruebas comparativas.

## Taiwan update32 (04/11/2026): sincronizar despues de Python

El `update32.pak` Taiwan nuevo reemplaza la version anterior. SHA-256 de la
fuente respaldada: `f9b9bc0c4d543ec441dcb0ebfab81542e66aa805efffa3e72942286f6f965ffb`.
Al reconstruir el cliente, conservar
`extracted_paks/update32_main_l_pestana_sand_castle.l` como
`SCRIPT\MAIN.L`; el archivo de Taiwan quita la pestana Sand Castle Tales.

### Hecho primero en Python

- Separo las 65 recetas Taiwan del grupo 683 bajo el grupo 2417, porque IGG
  ya usa el 683. La accion de dialogo 2019294 del Anniversary Angel abre 2417.
- Se agrego el NPC Anniversary Angel y los mensajes ingleses del aniversario
  2026.
- `work/anadir_canjes_tw.py` admite `instalar_servidor` para actualizar solo
  los datos extraidos del servidor, sin escribir los PAK del cliente.
- Los cambios se integraron en `F:\Ao Proyect\AO 2` y en la tabla de contenido
  del servidor. El cliente `C:\AO\Angels Online` ya recibio los PAK
  actualizados; los respaldos estan en
  `G:\Ao Proyect Improved\AO 2\work\backup\20261105_204726` y
  `G:\Ao Proyect Improved\AO 2\work\backup\canjes_tw_20261105_204743`.
- El `angel.dat` de C ya tenia el cargador de `update32.pak`; no se reemplazo.

### Pendiente para Rust

1. Regenerar los exportadores de items, dialogos, misiones/NPC, usos y Taiwan,
   incluyendo `corpus/content.db` y las tablas `extracted_paks/update26`.
2. Portar el NPC y el dialogo en `sistemas_mapa.rs`, los grupos y recetas en
   `mall_operaciones.rs`/`recent_mall.rs`, y los mensajes en
   `temporizadores.rs`.
3. Mantener el grupo 683 de IGG, comprobar las 65 recetas del grupo 2417 y
   comparar el dialogo, costos, recompensas e inventario entre Python y Rust.
4. Probar NPC y canje por TCP y ejecutar las pruebas gemelas afectadas antes
   de marcar esta migracion como sincronizada.

Los efectos/uso de insignias por piso, las tarjetas de puesto permanentes y la
transformacion sellada siguen pendientes de implementacion y validacion en
Python antes de portarlos a Rust. No se debe duplicar la mision 130 existente.

### Item Mall y mapa Sand Castle Tales (05/11/2026)

- Se repararon en Python/cliente C las filas y traducciones Mall ausentes de
  `update26.pak`. Las tablas fuente `ITEM5.XML`–`ITEM9.XML` de F tambien se
  actualizaron porque `aplicar_modo_estacion` las vuelve a instalar al
  arrancar el servidor. Al regenerar los datos para Rust, usar el corpus
  completo y comparar los productos/textos con esta vista efectiva; Rust aun
  no se ha sincronizado con esta reparacion.
- Se corrigieron en `ITEM9.XML` 18 descripciones de bolsos/huevos que tenian
  tabla de premios pero no el marcador `%s` para mostrarla. La fuente de
  Python y los dos PAK del cliente C estan sincronizados; incorporar esta
  correccion al siguiente refresh de datos para Rust.
- Los hooks, la pestaña y los recursos del mapa se verificaron en los archivos
  del cliente, pero falta la prueba visual en partida. No marcar el mapa como
  resuelto ni portarlo como cambio de servidor hasta confirmar su
  comportamiento en Python/cliente.
