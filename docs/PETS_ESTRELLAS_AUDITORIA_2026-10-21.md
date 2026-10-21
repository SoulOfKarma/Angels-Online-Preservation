# Auditoría de estrellas, mejoras y fusión de pets

Fecha: 2026-10-21. Alcance: diagnóstico y correcciones de progresión de Battlemaid +15 frente a Forest Devil sin intensificaciones. No se modificaron mascotas guardadas ni se aplicaron compensaciones retroactivas.

## Conclusión

El `1.6` de ambas capturas es compatible con sus bonos verdes y el cálculo actual del servidor. No significa que tengan los mismos atributos ni que una mejora `+15` equivalga a 15 estrellas. Sin embargo, hay problemas reales en cómo nuestra implementación obtiene los rangos de Battlemaid y limita su progresión por fusión.

No se recuperó una fórmula oficial completa de Improved Pet Feed. Por tanto, no se puede determinar todavía cuánto debería ganar exactamente esta Battlemaid al llegar a +15, ni aplicar una compensación fiable a pets existentes.

## Correcciones implementadas después de la auditoría

- **Fusión de atributos:** eliminado el tope de generación inicial. Una transferencia positiva ya aumenta el atributo aunque la principal supere ese rango. Se conserva la selección de hasta tres atributos por estrellas y la probabilidad de éxito configurada previamente; no se cambió la política de balance de éxito/transferencia.
- **Star-up:** los atributos elegidos proceden de los bonos presentes de la propia pet, incluidos los heredados por transformación, no de los rangos de una especie ajena. No se crean bonos ausentes. El campo general se recalcula desde los bonos resultantes, sin incrementarlo artificialmente por separado.
- **Límite de Star-up:** atributos que ya alcanzaron 8.0 no pierden bonos ni reciben incrementos artificiales al repetir la operación. Cantidades cero o negativas no cambian la pet.
- **Improved Pet Feed:** si faltaban bonos, el primer pienso ahora genera los iniciales y aplica además su incremento. Sigue respetando +15 y recalcula la estrella general.

Se mantienen provisionalmente los coeficientes de incremento de Improved Pet Feed y su fallback de rangos, pendientes de evidencia oficial. **No se declara arreglada la equivalencia de balance entre especies ni reconstruido el +15 antiguo de Battlemaid.** El cambio elimina bloqueos y desincronizaciones comprobados; no garantiza que cada Star-up aumente exactamente la misma cifra general cuando hay atributos ausentes o al máximo.

Pruebas: `python -m pytest tools/test_pet_progression.py tools/test_captured_pets.py -q -p no:cacheprovider`. Incluyen el caso de Battlemaid por encima de los rangos iniciales, selección de atributos, herencia, consistencia de estrellas, primer pienso, límite +15 y fusión fallida. Las pruebas no escriben en cuentas guardadas.

La batería histórica `python tools/test_mascotas.py` conserva seis fallos: guardar la mascota, ida/vuelta de HP, reconstrucción byte a byte, EXP de capturas, crecimiento por nivel y tope de vale. Se reprodujeron los mismos seis restaurando en memoria las dos funciones de progresión de HEAD, sin editar archivos. No se consideran una validación completa del sistema ni se declaran corregidos por este parche.

Para probar en el juego: reiniciar el servidor actualizado, usar una fusión exitosa con atributos elegibles y comprobar los bonos verdes del resultado. Las pets existentes conservan sus bonos anteriores; no se hace una migración al iniciar sesión. Si tenían una cifra general desincronizada, las operaciones corregidas la recalculan desde sus bonos (salvo operaciones rechazadas o fallidas).

## Fuentes y método

### Corrección posterior: combos de pet

La IA repetía `numero_de_dano` y `cierre_de_dano` (efecto de skill) por cada
subgolpe. El cliente volvía a reproducir la habilidad completa. Ahora la
primera pareja se mantiene y los N-1 subgolpes solo envían número flotante
y actualización de HP, también a los observadores de la pet.

El temporizador específico `server/pet_combos.py` conserva la pet, propietario
y objetivo originales, comprueba mapa/instancia y cancela golpes inválidos.
Registra el daño de cada subgolpe con el propietario correcto y procesa una
sola muerte. La IA espera al final de la ráfaga antes de iniciar otro ataque.

Full Buster VIII (6588; hijo 6905) declara seis golpes en el XML. Su ráfaga
AoE se comprime con la separación ya existente para estas habilidades;
los combos no AoE conservan su intervalo original. No se alteraron la
selección espacial de blancos de la pet, sus costes/cooldowns ni las
funciones compartidas de combos y el combate del personaje.

Validación: `python -m pytest tools/test_pet_combos.py tools/test_captured_pets.py tools/test_pet_progression.py -q -p no:cacheprovider`: **55 passed**.
Incluye la pareja inicial de paquetes extraída del AST real de la IA y los
cinco callbacks de Full Buster: una pareja de efecto, seis números de daño,
HP/atribución coherentes y transmisión a observadores. También se probaron
cambio de blanco, guardado/muerte de la pet, desconexión, mapa/instancia,
modo seguro, encantamiento, muerte del blanco y ausencia de subgolpes para
skills simples. La apariencia final queda pendiente de prueba en el cliente.

Se compararon hashes antes/después de esta corrección: sin cambios en el
prefijo anterior a la IA de pets ni en el sufijo desde la rama AoE del
personaje. Los cambios ajenos ya pendientes de `app.py` se preservaron.

### Auditoría de datos y binario

Se inspeccionaron XML extraídos, el código actual del servidor y pseudocódigo generado por REA/Ghidra. El análisis del cliente fue estático, no una observación de ejecución del servidor oficial. Se cerró el binario al terminar.

Binario analizado: `G:/REA/binarios/play_angel_unpacked.exe`, PE x86.

SHA-256: `2749eef56454aed55c06a80d18c2a6120896f0aac707f10006786d6b6c653af7`.

Se revisaron también los índices de los 27 PAK de `C:/AO/Angels Online`, en modo lectura. Entre los XML cuyos nombres coinciden con `pet`, `fuse`, `enhanc`, `strength`, `upgrade` o `refine`, no apareció una tabla adicional identificable de incrementos por intensificación. Esta búsqueda acotada no demuestra que la fórmula no exista bajo otro nombre o exclusivamente en el servidor oficial.

| Tabla vigente | Archivo extraído | Contenido relevante |
| --- | --- | --- |
| pet.xml | extracted_paks/update25/setting/eng/pet.xml | Especies, clases, etapas y rangos de bonos cuando existen |
| petattrib.xml | extracted_paks/update26/setting/eng/petattrib.xml | Atributos por tipo y nivel |
| pet_star.xml | extracted_paks/UPDATE7/setting/pet_star.xml | Umbrales de estrellas por atributo |
| fuse.xml | extracted_paks/update23/setting/fuse.xml | Combinaciones/resultados de fusión |
| serv_fuse.xml | extracted_paks/UPDATE9/setting/serv_fuse.xml | Resultados y pesos; no una matriz completa de ganancia por atributo |
| pet_inlay.xml | extracted_paks/update23/setting/pet_inlay.xml | Amplify; no confundir con Improved Pet Feed |

`system_eng.xml` carga las tablas de pet, atributos y estrellas anteriores. El item Improved Pet Feed, ID 7094, referencia la fórmula de uso 16, pero su fila no proporciona los incrementos por atributo.

## Qué confirmó REA

### Estrellas individuales y estrella general son datos distintos

`FUN_00716b10` convierte el bono verde de un atributo en estrellas usando sus umbrales. Los intervalos tienen límite inferior inclusivo y superior exclusivo; el resultado llega hasta 80 décimas (8.0).

`FUN_00514180` decodifica el bloque de bonos y, separadamente, la estrella general. En el objeto decodificado, los bonos empiezan en `+0xe4` y el campo general está en `+0x130`. Esto demuestra que el cliente recibe ambos datos por separado; **no demuestra que el servidor oficial calcule la estrella general como una media**.

Nuestro servidor sí usa una media entera de las ocho estrellas individuales. El contador de intensificación es otro dato separado. Tampoco corresponde multiplicar otra vez todos los stats por la estrella general: los bonos verdes ya se suman a los atributos utilizados en combate.

### La vista previa de fusión usa estrellas, no el máximo inicial de la especie

`FUN_00514580` ordena los ocho atributos de la asistente por sus estrellas individuales, de mayor a menor.

`FUN_005d3d30` examina esa lista y selecciona hasta tres atributos elegibles. Compara las estrellas del atributo de la principal con su estrella general más 10 décimas (1.0): es elegible si no supera ese umbral. Esta rutina no usa el máximo de generación inicial de `pet.xml` como tope.

Esto permite contrastar la elegibilidad de la vista previa. **No determina por sí solo la cantidad transferida ni el eventual límite del servidor oficial después de transferirla.**

La ayuda de fusión (`string.xml`, textos 2783–2785) distingue la fusión de atributos de la transformación, indica proporciones de transferencia diferentes por atributo y señala que la transformación conserva los atributos adicionales de la principal. No es correcto asumir que una Battlemaid transformada deba recibir una nueva tirada completa de bonos de especie.

### Evidencia conservada

Registros JSON locales en `docs/rea_evidence/` (directorio ignorado por Git):

| Función | Registro | Evidence ID |
| --- | --- | --- |
| 00716b10, umbrales | 1792622144305_procedure_pseudo_code.json | ev_5a73227613e20dec5a4e655fe4c1059528a79e78907b364f9e7b7dd715e7c194 |
| 005d3d30, elegibilidad | 1792622144341_procedure_pseudo_code.json | ev_6722ddc4c35806604f7276040284be80b06f0f7ec591471bb61f174d229654d0 |
| 00514180, decodificación | 1792622144368_procedure_pseudo_code.json | ev_0738d8db5ab5b45daae255f4de6e73831b076e2e981c4c1648cf143084d1d7d5 |
| 00514580, ordenación | 1792622214866_procedure_pseudo_code.json | ev_48be453d0a8140ccb5d4ebfad5d5ef73a9f08f789f1f25d57cbe66cf2c8f217c |
| 005d3020, requisitos | 1792622214854_procedure_pseudo_code.json | ev_e95c29b9ad110d344cbb5360ee0d2003247c2ec4e8e6bfa631552dad75d4c2b9c |
| 00716cb0, probabilidad mostrada | 1792622144376_procedure_pseudo_code.json | ev_e86d800cc718bfe381ee031191360bcd0f4e46c00fa5d4a55e19bf39b0dce15d |

La fórmula de probabilidad mostrada por el cliente está separada de la fórmula de compatibilidad actualmente usada por `fusion.exito_mascota`; tampoco deben confundirse con los incrementos de Improved Pet Feed.

## Reproducción del caso de las capturas

Orden: HP, MP, ataque, defensa, ataque mágico, defensa mágica, rigor, agilidad. Estrellas expresadas en décimas:

| Pet | Bonos verdes | Estrellas individuales | Media entera actual |
| --- | --- | --- | --- |
| Battlemaid +15 | 764, 449, 328, 365, 0, 0, 397, 360 | 7, 8, 7, 7, 0, 0, 36, 64 | floor(129/8) = 16 → 1.6 |
| Forest Devil +0 | 1230, 533, 558, 723, 310, 321, 250, 276 | 10, 9, 14, 18, 9, 11, 18, 43 | floor(132/8) = 16 → 1.6 |

Los vectores individuales se contrastaron con los umbrales XML. Battlemaid concentra muchos de sus bonos en rigor y agilidad, y tiene dos atributos sin bono. El promedio oculta esas diferencias.

Forest Devil Treesia, sprite 15561, sí tiene rangos propios de etapa alta. Nuestro flujo de evolución conserva por atributo el mayor valor entre el anterior y la nueva tirada; por ello, superar algún rango de generación final no demuestra por sí solo corrupción. La procedencia y evolución de cada pet importan para reconstruir lo ocurrido.

## Problemas encontrados en la implementación anterior

### 1. Rangos prestados sin fundamento específico para Battlemaid

`server/mascotas.py::rangos_bonos_de` no encuentra rangos propios para Battlemaid, sprite 3200 / gráfico 44181 (item 20012). Usa entonces la primera especie con rangos de su misma clase: Hydra 3227 / gráfico 44188, de etapa inicial. No confundir los gráficos de `pet.xml` con los IDs de items.

Rangos resultantes: HP 82–96; MP 47–59; ataque 37–43; defensa 33–53; rigor 37–53; agilidad 35–51. No incluye ataque ni defensa mágicos.

`mejorar_mascota` toma incrementos aleatorios aproximadamente equivalentes a la mitad de esos rangos. No se encontró evidencia oficial que justifique usar los rangos de esa Hydra para mejorar Battlemaid. Si no hay bonos previos, la primera mejora únicamente genera bonos iniciales, en vez de aplicar además el incremento normal.

No se debe resolver inventando rangos mayores para Battlemaid: hace falta separar generación, herencia, intensificación y fusión.

### 2. La fusión puede aceptar el proceso sin aumentar el atributo

`server/fusion.py::_fusion_mascota` limita el resultado al máximo de `rangos_bonos_de`, aunque estos sean rangos de generación inicial. Protege contra reducciones, pero puede bloquear por completo el crecimiento.

Ejemplo realista con los bonos de la captura: ataque 328, máximo prestado 43 y transferencia positiva de 100. La expresión actual `max(328, min(43, 328 + 100))` devuelve 328: no gana nada. Lo mismo ocurre con HP 764 frente a máximo 96 y agilidad 360 frente a máximo 51.

El bloqueo es reproducible en nuestro código. Ese tope no está respaldado por las rutinas de vista previa examinadas. El límite oficial posterior y los coeficientes exactos siguen pendientes.

### 3. Subidas de estrella pueden desincronizar número y atributos

`server/mascotas.py::subir_estrella` solo aumenta los atributos presentes en los rangos encontrados, pero fuerza la estrella general anterior más la cantidad solicitada, aunque la media de los ocho atributos no acompañe.

Reproducción en memoria: sprite 3200, estrella general inicial 2 décimas; bonos HP 92, MP 55, ataque 41, defensa 51, rigor 42 y agilidad 46. Con `random.seed(5)` y `subir_estrella(ficha, 10)`, el campo general termina en 12, mientras que recalcularlo desde los bonos da 9. No se escribió en la base de datos.

## Qué falta antes de corregir o compensar

1. Determinar la fórmula de intensificación oficial por atributos/clase y distinguirla de Amplify y Star-up Card. Los XML examinados no bastan para fijarla.
2. Determinar coeficientes y límites de transferencia oficiales; la vista previa solo prueba selección y elegibilidad.
3. Sustituir el fallback de especie y el tope inicial por reglas respaldadas, con pruebas para pets normales, evolucionadas, de fusión y capturadas.
4. Definir cuándo recalcular la estrella general, sin asumir que el promedio actual está probado como fórmula oficial.
5. Revisar la procedencia de las pets existentes antes de cualquier migración. No se pueden reconstruir tiradas perdidas únicamente desde el contador +15.

No se aplicaron migraciones ni compensaciones. El alcance implementado y las limitaciones pendientes se detallan al principio del documento.
