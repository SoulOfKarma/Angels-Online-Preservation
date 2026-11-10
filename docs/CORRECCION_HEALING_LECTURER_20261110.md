# Healing Lecturer: Exposed Plot y Treatment for Food Poisoning — 10/11/2026

Instalado en el servidor Python de G y `F:\Ao Proyect\AO 2`, y en las tablas
del cliente local `C:\AO\Angels Online`. Sin modificar Rust ni cuentas reales.

## Causas

- Healing Lecturer, NPC 1919 / entidad 52 del Lyceum, comparte retrato 48 con
  las raices 60401 y 80015. `raiz_de_mision` no podia distinguirlas y rechazaba
  su arbol; el fallback mostraba el recordatorio inicial de recoger hierbas.
- La consulta del tipo de NPC tampoco encontraba los del mapa 41: login carga
  `lyceum.json` aparte de `PLANTILLAS_POR_STAGE`.
- Habia textos que llamaban al mismo personaje Medicine Lecturer, aunque su
  nombre de mapa es Healing Lecturer. Esto afectaba a Exposed Plot, al paso 2
  de Treatment y a otros recordatorios relacionados.
- La prueba de Exposed Plot descubrio que el plato 4579 se retiraba de la
  mochila en memoria, pero no se guardaba esa retirada; volvia al reconectar.

## Correccion

`app._npc_type_de` reconoce el Lyceum. La conversacion de misiones entrega a
`dialogos_mapa.arbol_de_mision_para` la raiz exacta por entidad o tipo del NPC
(`DIALOGO_DE_NPC[(41,1919)] = 60401`). Si no existe esa asociacion, conserva
la resolucion anterior por retrato. Las exclusiones del tutorial siguen vigentes.

El efecto de retirar objetos de mochila guarda tambien el inventario, igual
que ya hacia la retirada de tokens ocultos. No se cambiaron las condiciones
ni los premios del arbol oficial.

Se unifico Healing Lecturer en cinco mensajes (60406, 60407, 60510, 60514,
61007), en el paso 2 de quest 605 y en los JSON compilados correspondientes,
tanto en G como en F y sus salidas preparadas. Los dos PAK update26 del
cliente conservan todos los demas recursos, comprobados por CRC y contenido.

## Verificacion

- 28 pruebas pasan en G y F, incluidas las seis nuevas de raiz nativa,
  retrato compartido, Lyceum, tutorial y premios.
- `tools/probar_healing_lecturer.py`: cuatro escenarios TCP Python sobre
  copias SQLite TEMP. Entrega 3/5/5/1 materiales y avanza al Inspector;
  sin materiales no avanza; Exposed Plot consume el plato y concede 6.000
  EXP / 80 creditos; Treatment concede 18.000 EXP / 225 creditos / 8.000 oro.
- Segundas visitas no duplican premios ni repiten la entrega. Se conserva
  un token de otra mision y se comprueba inventario/progreso guardado.
- Evidencia final: `%TEMP%\ao_healing_lecturer__30_1rdb\resultado.json`,
  junto a logs y trazas de cada escenario. No se ejecuto Rust.
- Hashes verificados de los 18 archivos instalados; Python de G y F identico
  en los dos modulos corregidos. No se escribio en ninguna cuentas.db real.

Respaldo instalado y manifiestos:
`work/backup/healing_lecturer_20261110_codex_final/local.json` y `externo.json`.
La carpeta sin `_final` es una preparacion previa que no se instalo.
Las copias originales del servidor de F conservan tambien la version previa
equivalente de G, comprobada antes de instalar; no se sustituyeron otros
avances de Claude. Sin commit ni push.

El usuario debe reiniciar el servidor Python de F para cargar el cambio de
logica y reabrir el cliente para actualizar los nombres. Con sus materiales
ya recogidos puede hablar otra vez con Healing Lecturer y elegir entregarlos;
no necesita reiniciar la mision ni volver a recolectar.
