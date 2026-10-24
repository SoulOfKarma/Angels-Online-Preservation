# Recuperación y accesos, 2026-10-22

Karma confirmó que el servidor estaba detenido antes de aplicar cambios.

## Recuperación acotada

- Destino: cuenta `karmav3`, ranura 0, char_id 1007, KarmaV6, Archer 434.
- Fuente: `data/cuentas_backup_skills_pre.db`, misma cuenta/ranura/ID, antes llamado KarmaV4, nivel 433. También hay copias coincidentes en los respaldos pre_quest_kills/restaurado_karmav3.
- Equipo y Fashion restaurados con sus metadatos originales: ocho piezas +15, gemas y vinculaciones. Bolsa final: 36 entradas contando equipo y casillas de servicio.
- Se mantienen nombre, nivel 434, EXP, ramas y progreso de habilidades, hechizos aprendidos, barra actual, misiones, logros y oro actual (8.122). No se restauran hechizos antiguos ajenos a sus ramas.
- Objetos nuevos de bolsa se conservan; las pilas movidas se concilian sin sumarlas dos veces. Se descarta un metadato huérfano de la copia, sin objeto asociado.
- Copia reversible de ambas filas previas: `data/backups/manual_karmav6_20261022_221918.json`. No contiene contraseñas de cuenta.
- La otra copia del nombre en cuenta `karmav2`, ranura 2, nivel 420, ahora se llama KarmaV7; no se altera su inventario.
- La pérdida ya existía en todos los respaldos rotativos recientes. No se determinó qué operación original la produjo. `/skillclear` solo modifica hechizos/barra. No atribuirle la pérdida sin evidencia.

`tools/recover_karmav6.py` es una recuperación específica, no un comando GM general. Sin `--apply-offline` solo muestra el plan. Rechaza volver a aplicar una vez renombrado el segundo personaje.

## Protecciones

Antes no había propietario exclusivo de cuenta en el dispatcher. Ahora `server/accesos.py` reserva la cuenta, sin distinguir mayúsculas, desde el login validado hasta la desconexión. Un segundo login es rechazado sin expulsar al primero. La conexión de mundo recibe esa propiedad mediante un traspaso de un solo uso que caduca a los 30 segundos. Cerrar el viejo socket de login no libera la sesión de mundo.

El protocolo de traspaso heredado se identifica por IP. Para dos clientes tras la misma IP se rechaza un segundo traspaso pendiente en vez de sobrescribir el primero: reintentar tras completar la primera carga. Esto no sustituye un ticket criptográfico que el cliente actual no transmite.

Creación: transacción `BEGIN IMMEDIATE`, nombre global no repetido (casefold), ranura libre e INSERT sin REPLACE. Antes un paquete de creación para una ranura ocupada podía reemplazar toda la ficha. Esto era un riesgo comprobado; no prueba que haya sido la causa de esta pérdida. Los nuevos char_id se asignan globalmente; los IDs repetidos heredados no se migran aquí.

## Prueba de eventos

Para nivel 434, cinco minutos de inscripción:

```text
/aastart 30 434 5
/aa enter
```

Arena de nivel 401+, mapa 240, combate de 30 minutos. Durante inscripción se entra al área de espera y al empezar se pasa al área de combate. Si se ejecuta `enter` desde fuera de Sign-up Office, el primer uso lleva a ese mapa y hay que repetirlo una vez cargado. El comando start no teletransporta por sí solo.

La entrada normal cuesta 8.000.000; el personaje recuperado mantiene 8.122 de oro actual y necesitará fondos para la prueba. No se ha fabricado oro ni cambiado la tarifa.

```text
/hbstart 60 5
/hb enter
```

Holy, mapa 112, combate de 60 minutos, con piedra/pase válido. Mismo paso previo de lobby si no está ya en Sign-up Office. Ambos eventos usan sus funciones de registro, combate y cierre, no un teleport GM que omita la inscripción. Para pruebas sucesivas usar `/aa finish` o `/hb finish` durante combate; `/aastop 434` y `/hbstop` cancelan sin premios.

Los cambios de código requieren arrancar el servidor actualizado. No se ha afirmado haber probado dos clientes reales ni arrancado una ronda real desde esta recuperación.

Verificación: 163 pruebas aprobadas (acceso/recuperación, Arena/Holy, admisión por diálogos, premios, avisos, mapas y Outpost), compilación Python y `git diff --check`. Lectura posterior de SQLite confirma ambas filas y las ocho piezas +15.
