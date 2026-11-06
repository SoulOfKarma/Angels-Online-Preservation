# Recuperacion de traducciones y mapa TW — 05/11/2026

Peticion del usuario: recuperar en el proyecto Python de F las traducciones
que ya existen en G y hacer que Sand Castle Tales se dibuje en el cliente.
Esta tanda no modifica Rust, cuentas, launcher ni Event Overview.

## Instalado y verificado

- Fuente: `G:\Ao Proyect Improved\AO 2`.
- Proyecto Python reparado: `F:\Ao Proyect\AO 2`.
- Cliente reparado: `C:\AO\Angels Online`.
- **67.619 atributos de texto** recuperados en **30 XML** de F. Se conservan
  IDs, filas nuevas, tipos, efectos, estadisticas y precios del destino.
- Se recuperaron la memoria de traduccion y el manual del aniversario 2026.
- En `corpus/content.db` de F cambiaron **5.303 celdas de texto de 4.793 filas**.
  La comparacion completa de **191.909 filas** confirma el mismo esquema y
  ningun otro cambio de valores ni filas.
- Cliente: **27.958 campos en update26.pak**, **2.443 en update26.pak.bak**.
  El respaldo ya conservaba mas traducciones que el PAK activo.
- Auditoria posterior: ningun campo visible que tenga traduccion inglesa en
  los XML de G sigue en chino en F. Esto recupera lo ya traducido; no completa
  los textos que siguen sin traducir en la propia fuente G.

Filas relacionadas con los martillos de la captura (`item7.xml`):

| ID | Nombre recuperado |
|---|---|
| 68369 | 60-star Lucky Hammer |
| 68629 | 60-star Lucky Enhanced Pestle |
| 68649 | 60-star Lucky Piercing Hammer |
| 68669 | Lvl 60 Lucky Ride Feed |

## Sand Castle Tales: causa y correccion

Los recursos ya estaban instalados. MAIN.L llama `game.setstagemappage(30)`
para el boton 25516, y el parche previo registra las tres resoluciones de la
region 29 (indice cero). Faltaba el **despacho de dibujo del ejecutable**:
en `0x5AA3E5`, `cmp dword ptr [ebp-8],29; ja 0x5AA596` descarta la pagina 30.
Quedaba visible la escena anterior, como en la captura.

`tools/parchear_angel_update32.py` incorpora `parchear_dibujo_region30`:

- pagina 30: llama al dibujante existente `0x5AC680` con region 29;
- demas paginas: switch original;
- seccion nueva `.twmap`, sin pisar el cargador de update32, sus recursos ni
  la proteccion de tooltips `.twfix`;
- firma estricta del codigo e instalacion idempotente.

Para ejecutables YA parcheados se usa `--solo-mapa`. El modo normal que
parte del IGG desempaquetado incluye tambien esta correccion. No aplicar el
modo normal al ejecutable ya parcheado.

Verificadas las tres MPC y las imagenes world88/world89/world90 instaladas.
`update27..32.pak` y MAIN.L no cambiaron. Las cuatro pestanas ya tienen
`appdata=5`, ancho 105 y separacion 15 px, y Switch Maps esta en x=617 en
G, F y el PAK instalado. No se cambiaron otros menus.

## Pruebas

```powershell
& 'C:\laragon\bin\python\python-3.10\python.exe' -I -X utf8 -m pytest tools/test_recuperar_update32.py tools/test_traducir.py tools/test_pase_y_mapa_tw.py -p no:faulthandler -q
```

**49 pruebas pasan**: textos, conservacion de mecanicas/filas, IDs reutilizados,
escapado XML, memoria, pase y pestanas. Se emulo el switch x86 real para
paginas -1 y 0..31: 0..29 y los invalidos conservan su resultado; 30 dibuja
region 29. Se verifican la pila y el puntero del objeto.

En Windows se desactiva el plugin faulthandler de pytest para evitar mensajes
VEH internos de Unicorn al reservar memoria. Con el plugin activo las mismas
49 pruebas pasaron, pero imprimieron esos mensajes.

La verificacion posterior comprueba los hashes de **40 archivos**, sus
respaldos y la base completa. No se ejecutaron validadores Rust.

## Respaldo y manifiesto vigente

```text
G:\Ao Proyect Improved\AO 2\work\tw_update32_nov2026\recuperacion_codex_20261105_final\manifiesto.json
```

Cada entrada de `files` identifica destino, hashes y archivos `before_NNN` /
`after_NNN`. Este es el lote instalado; las carpetas sin `_final` son
preparaciones previas.

```powershell
& 'C:\laragon\bin\python\python-3.10\python.exe' -I -X utf8 tools/verificar_recuperacion_update32.py work/tw_update32_nov2026/recuperacion_codex_20261105_final/manifiesto.json --instalado
```

Quedaron tambien en F los cuatro Python nuevos/actualizados: recuperador,
parche, verificador y pruebas. Para reconstruir otro lote usar
`recuperar_traducciones_update32.py preparar` con `--source`, `--project`,
`--client` y una carpeta nueva en `--output`. Preparar solo escribe en esa
carpeta. Instalar verifica hashes y bloqueos antes de escribir y restaura el
lote si falla una copia.

## Comprobacion pendiente en el juego

Abrir de nuevo el cliente local para cargar ejecutable y PAK corregidos.
Reiniciar el servidor Python de F si estaba abierto: puede conservar tablas
en memoria. Mirar los martillos y pulsar Sand Castle Tales. El dibujo se
verifico por emulacion del codigo real; **no se ha confirmado visualmente
en una partida**. No se detuvieron clientes ajenos.

Event Overview y los archivos del pase quedaron intactos. `server/pase.py`
de F ya contiene la recuperacion de listas vacias y coincide con G; su prueba
pasa. No se borro progreso ni se escribio en ninguna cuentas.db.
Sin commit ni push.
