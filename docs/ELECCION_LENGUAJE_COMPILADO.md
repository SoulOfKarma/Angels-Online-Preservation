# Eleccion de un lenguaje compilado para el servidor de Angels Online

## Objetivo

Este documento deja una guia para decidir si, cuando el emulador tenga la
mayor parte de las funciones del Angels Online de IGG, conviene migrar el
servidor actual de Python a un lenguaje compilado.

La conclusion corta es:

> No conviene reescribir el proyecto solamente porque Python sea interpretado.
> Primero se mide. Si el servidor realmente queda limitado por CPU, la opcion
> mas equilibrada para una migracion completa es **Rust**; para una migracion
> mas sencilla y rapida, **Go**; y para conservar productividad y mejorar solo
> las partes pesadas, **Python + Rust** es probablemente el mejor primer paso.

El cliente original no necesita ser reescrito. La eleccion afecta al servidor,
sus herramientas, parsers y servicios auxiliares. El protocolo binario que ve
`Angel.exe` debe permanecer exactamente igual.

## Compilado no significa automaticamente mas rapido

El rendimiento total depende de donde se gasta el tiempo:

- espera de sockets y red;
- consultas y escrituras SQLite;
- serializacion de paquetes;
- IA, movimiento y busqueda de caminos;
- calculo de combate, buffs, mascotas y drops;
- carga y busqueda en XML/JSON;
- exceso de mensajes o trabajo repetido por cada tick.

Si el cuello de botella es SQLite, el disco o un algoritmo ineficiente, cambiar
de lenguaje sin corregirlo puede producir poca diferencia. Un buen indice, una
cache o eliminar un bucle repetido puede valer mas que una reescritura total.

Tambien hay que separar tres conceptos:

- **Compilar o empaquetar Python** con PyInstaller/Nuitka facilita distribuirlo,
  pero no garantiza una mejora grande del servidor.
- **Compilar JavaScript/TypeScript** o acelerar su comprobador de tipos, como
  en el ejemplo de Bun, no demuestra que sea la solucion adecuada para este
  servidor. La velocidad del type checker no equivale al rendimiento del juego.
- **Reescribir la logica en un lenguaje nativo** si puede mejorar CPU, memoria y
  concurrencia, pero aumenta el costo de desarrollo y el riesgo de regresiones.

## Requisitos particulares de este proyecto

La tecnologia elegida debe manejar bien:

1. TCP asincrono y muchas sesiones simultaneas.
2. Lectura y escritura binaria little-endian sin alterar un solo byte.
3. Tareas periodicas para IA, combate, regeneracion, spawns y buffs.
4. Estado compartido entre jugadores, mapas, pets, summons y mercenarios.
5. SQLite y migraciones de datos confiables.
6. XML, JSON y archivos extraidos de `.pak`.
7. Pruebas de paquetes byte por byte y reproduccion de sesiones grabadas.
8. Desarrollo en Windows y ejecucion sencilla para un servidor privado.
9. Diagnostico claro: logs, trazas, capturas y posibilidad de comparar Python
   contra la nueva implementacion.

## Opciones principales

| Lenguaje | Rendimiento | Dificultad de migracion | Seguridad de memoria | Concurrencia | Comentario |
|---|---:|---:|---:|---:|---|
| Rust | Muy alto | Alta | Muy alta | Muy buena | Mejor candidato tecnico a largo plazo. Excelente para protocolos y simulacion, pero exige aprender ownership y diseñar cuidadosamente el estado compartido. |
| Go | Alto | Media-baja | Alta | Excelente y sencilla | El camino mas corto hacia un servidor compilado mantenible. Goroutines y canales encajan bien con sesiones y mapas. Menos control fino que Rust. |
| C# / .NET | Alto | Media | Alta | Muy buena | Muy comodo en Windows, gran biblioteca, buen async/await y depuracion. El GC puede producir pausas, normalmente controlables para este tipo de juego. |
| C++ | Muy alto | Muy alta | Baja si no se disciplina | Muy buena | Maximo control y afinidad historica con clientes de juegos, pero es la opcion con mayor riesgo de corrupcion de memoria y errores dificiles. |
| Java / Kotlin | Alto | Media | Alta | Muy buena | Ecosistema maduro para servidores. La JVM consume mas memoria y no aporta una ventaja clara frente a Go o C# para este proyecto. |
| Zig | Muy alto | Alta | Media | Manual | Interesante para binarios pequenos y control de bajo nivel, pero el ecosistema y las APIs de servidor son menos maduros. No seria mi primera opcion. |

## Recomendacion

### Primera opcion: Python + Rust de forma gradual

Mantener Python como capa de logica mientras se extraen a Rust solamente los
modulos que las mediciones demuestren costosos:

- codec y armado/lectura de paquetes;
- simulacion de combate masiva;
- IA y actualizacion espacial de monstruos;
- pathfinding y consultas de proximidad;
- parsers grandes de XML/PAK;
- calculos repetidos de stats, efectos y drops.

Rust puede exponerse a Python mediante PyO3/maturin. Esto conserva toda la
logica ya verificada y permite comparar resultados antes de reemplazarla. Si la
parte nativa falla, el modulo Python puede seguir como implementacion de
referencia durante la transicion.

Ventajas:

- menor riesgo de romper sistemas ya reparados;
- beneficios de rendimiento donde realmente importan;
- migracion comprobable modulo por modulo;
- permite aprender Rust sin detener el desarrollo funcional.

Desventaja principal: durante un tiempo se mantienen dos lenguajes y una
frontera Python/Rust. Conviene pasar datos en bloques, no llamar a Rust una vez
por cada atributo o monstruo, para que el costo de esa frontera no anule la
mejora.

### Segunda opcion: reescritura gradual completa en Rust

Es la mejor meta si se desea un servidor nativo, muy eficiente y mantenible a
largo plazo. Una arquitectura razonable seria:

- Tokio para red y tareas asincronas;
- `bytes` o lectores propios para el protocolo little-endian;
- Serde para datos estructurados;
- SQLx o rusqlite para persistencia;
- un actor o tarea propietaria por mapa para evitar bloqueos globales;
- canales para comunicar login, mundo, mapas y persistencia.

No se debe empezar copiando `app.py` linea por linea. Primero se definen
limites claros: transporte, sesion, mundo, inventario, combate, quests y datos.

### Alternativa pragmatica: Go

Go es recomendable si la prioridad es terminar antes y que mas desarrolladores
puedan mantener el servidor. Facilita un proceso por mapa o una goroutine por
sesion, produce un ejecutable sencillo y tiene herramientas muy buenas para
detectar carreras y perfilar.

Su rendimiento deberia sobrar para una poblacion moderada. Pierde parte del
control y de las garantias de Rust, y el recolector de basura existe, pero la
simplicidad puede compensarlo ampliamente.

### Alternativa natural para Windows: C#

C# seria una decision perfectamente valida si el equipo se siente mas comodo
con Visual Studio y .NET. Su `async/await`, `Span<byte>`, canales y herramientas
de diagnostico sirven muy bien para un servidor binario. Es mas productivo que
C++ y normalmente mas facil de incorporar que Rust.

## Lenguajes que no elegiria como primera opcion

- **C++**: solo si existe experiencia fuerte en el equipo o una necesidad
  concreta de interoperar con codigo nativo existente. Para una reescritura
  desde Python, Rust ofrece rendimiento semejante con mas protecciones.
- **Zig**: prometedor, pero hoy implicaria construir mas infraestructura propia.
- **JavaScript/TypeScript/Bun**: puede funcionar para servicios web o paneles,
  pero cambiar Python por JS no entrega el salto de seguridad y control que
  justificaria reescribir el nucleo del mundo.
- **Nuitka/Cython como reescritura total**: pueden acelerar o distribuir partes,
  pero deben tratarse como optimizaciones medibles, no como garantia automatica.

## Arquitectura recomendada antes de migrar

Aunque el codigo siga en Python, conviene separar estas fronteras:

```text
Cliente AO
    |
    v
Transporte TCP y codec de paquetes
    |
    v
Sesion y validacion de peticiones
    |
    +----> Servicio de login/cuentas
    |
    +----> Mundo y mapas
              |
              +----> Combate, IA, pets y summons
              +----> Inventario, drops y exchange
              +----> Quests, NPC y portales
    |
    v
Persistencia y logs
```

Cada modulo debe comunicarse con estructuras conocidas y no depender de
variables globales internas de otro modulo. Esa separacion facilita mover una
pieza a Rust, Go o C# sin cambiar simultaneamente todo el servidor.

## Plan de decision y migracion

### Fase 1: estabilizar y medir Python

Antes de elegir lenguaje:

1. Completar las funciones principales de IGG.
2. Crear pruebas reproducibles con sesiones grabadas.
3. Simular 50, 100, 250 y 500 jugadores/bots.
4. Medir CPU total, memoria, latencia de tick, paquetes por segundo y tiempo de
   consultas SQLite.
5. Perfilar con `cProfile`, `py-spy` u otra herramienta que muestre funciones
   concretas, no solo uso general de CPU.

Metas sugeridas, que deben ajustarse al hardware real:

- tick de mapa estable y sin acumulacion de tareas;
- percentil 99 de respuesta inferior a 100 ms para acciones normales;
- ningun bloqueo largo del event loop;
- memoria estable durante una prueba prolongada;
- cero divergencias en paquetes frente a las pruebas de referencia.

### Fase 2: prototipo comparable

Implementar en el lenguaje candidato una pieza pequena pero representativa:

- decodificar y volver a codificar un conjunto de opcodes;
- cargar monstruos y ejecutar sus ticks;
- procesar una simulacion de combate;
- leer datos XML y consultar SQLite.

Ejecutar exactamente los mismos datos en Python y en el prototipo. Comparar:

- resultado byte por byte;
- tiempo por operacion;
- memoria;
- facilidad para depurar y modificar;
- cantidad de codigo y errores introducidos.

### Fase 3: migracion por componentes

Orden sugerido:

1. Codec binario y tipos de protocolo.
2. Indice espacial, IA y pathfinding.
3. Combate, buffs, pets, summons y mercenarios.
4. Inventario, drops, crafting y exchange.
5. Mapas, NPC, quests y eventos.
6. Sesiones/login y persistencia.
7. Retiro de la implementacion Python solamente cuando las pruebas comparativas
   cubran el comportamiento migrado.

El orden puede cambiar despues del perfilado. Si el codec consume 2 % y la IA
70 %, se empieza por la IA.

## Estrategia para no romper compatibilidad

El mayor activo del proyecto no es el lenguaje: es el conocimiento ya obtenido
del protocolo y de los datos oficiales. Debe conservarse mediante:

- archivos de captura inmutables como casos de prueba;
- pruebas golden de paquetes completos;
- tablas de opcodes compartidas o generadas desde una sola fuente;
- enteros con tamanos explicitos (`u8`, `u16`, `u32`, `i32`);
- endianess declarada en cada lectura/escritura;
- tests de inventario, combate, captura, mascotas, NPC y mapas;
- comparacion paralela: Python produce A, el nuevo nucleo produce B, y el test
  exige que A y B sean equivalentes;
- migraciones versionadas de la base de datos;
- logs con IDs de sesion, personaje, mapa y entidad.

Nunca se debe usar una reescritura como oportunidad para “limpiar” a la vez el
protocolo, cambiar IDs y alterar reglas. Primero se reproduce el comportamiento;
despues se refactoriza con pruebas que lo protejan.

## Riesgos principales

1. **Reescritura eterna**: mientras se porta codigo, Python sigue cambiando y
   ambas versiones se separan.
2. **Regresiones invisibles**: un paquete puede tener el tamaño correcto pero
   un offset equivocado y cerrar el cliente.
3. **Concurrencia incorrecta**: mas hilos no equivalen a mas rendimiento; pueden
   duplicar drops, ataques o guardados.
4. **Estado global**: compartir todas las entidades bajo un gran mutex elimina
   buena parte de la ventaja de un lenguaje rapido.
5. **Persistencia**: una implementacion veloz que pierde progreso al cerrarse no
   es una mejora.
6. **Optimizar demasiado pronto**: portar modulos que apenas consumen CPU roba
   tiempo a sistemas del juego aun incompletos.

## Decision propuesta

Cuando el servidor alcance una cobertura funcional suficientemente alta:

1. Congelar una bateria amplia de pruebas y capturas.
2. Ejecutar una prueba de carga seria en Python.
3. Si Python cumple la poblacion esperada, mantenerlo y optimizar puntos
   concretos.
4. Si la CPU limita el servidor, construir un modulo Rust para el cuello de
   botella principal.
5. Tras dos o tres modulos exitosos, decidir entre mantener el modelo hibrido o
   completar la migracion.

Eleccion recomendada segun prioridad:

- **Maxima robustez y rendimiento a largo plazo:** Rust.
- **Menor tiempo de desarrollo para un ejecutable compilado:** Go.
- **Mejor experiencia y herramientas en Windows:** C#/.NET.
- **Menor riesgo inmediato:** mantener Python y acelerar con Rust solo lo que
  las mediciones justifiquen.

Para este proyecto, mi recomendacion concreta es comenzar con **Python + Rust**
y no autorizar una reescritura completa hasta tener benchmarks que demuestren
el beneficio y pruebas capaces de detectar incompatibilidades del protocolo.

