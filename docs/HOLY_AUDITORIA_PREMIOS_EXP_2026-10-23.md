# Holy: auditoria de EXP y Skill EXP

Se revisa el comportamiento existente, sin cambiar importes ni formulas y sin tocar cuentas reales.

## Formula actualmente configurada

`server/competicion_premios.py::_holy_exp` y `server/plantillas/competiciones_config.json::holy_exp` implementan una politica propia, explicitamente etiquetada como NO oficial IGG.

Sea f = min(max(puntuacion personal,0),500)/500 y v = 1 si gana su equipo y tiene puntos; en otro caso v = 0:

- EXP = salto de EXP entre su nivel y el siguiente * (5 + 5*f + 5*v) / 100.
- Skill EXP para cada habilidad = EXP requerida por su nivel actual de habilidad * (25 + 50*f + 25*v) / 100.
- Los calculos usan enteros y se congelan al cerrar la ronda. La recompensa depende del nivel del personaje; Skill EXP depende tambien del nivel de cada habilidad.
- Derrota y empate dan EXP y Skill EXP. Sin puntos, incluso el ganador recibe la base (5% y25%). A500 puntos, el ganador recibe15% y100%; el perdedor o empate10% y75%.
- En empate ambos equipos usan la misma regla, pero NO necesariamente reciben la misma cantidad: nivel y puntos individuales pueden variar. La politica actual tambien bonifica puntos a los perdedores.
- Se requiere presencia al cierre, al menos dos competidores y cierre no cancelado. Observadores no cobran. Entrega automatica con ledger idempotente; no duplica al reintentar. En el nivel tope pueden limitarse los incrementos por las curvas/caps existentes.

## Datos originales y alcance de REA

XML `string.xml`2276/2277 diferencia anuncio de victoria con mucha EXP de anuncio sin victoria con algo de EXP; no contiene cantidades. `msg.xml`7748 vincula puntos a premios. `expprize.xml` tiene44 filas, dos tipos, pero no se demostro que Holy las consuma: no se aplica esa tabla por semejanza de nombre.

REA/Ghidra se ejecuto sobre G:/Angel.exe, SHA256 7c1f8cc16e2032081dc15ccc1a67de668803f62d8252ab570d1f4724c162d6e9b, sin ejecutar el juego. Evidencia local en docs/rea_evidence (ignorada por Git):

- 1792770476820_search_strings.json: Holy/Battlefield solo devuelve nombres de UI/campo, no formula de premio.
- 1792770512068_search_strings.json: expprize|bufprize|Holy.*Exp sin resultados. Una busqueda negativa no prueba ausencia absoluta.
- 1792770477091_procedure_pseudo_code.json, FUN_005ffe10: TEAMID y contadores suministrados por el servidor; sub9 actualiza estado/UI.
- 1792770512117_procedure_pseudo_code.json, FUN_00669350: visibilidad de marcador y cambio del canal de chat, sin calculo de EXP.
- 1792770512153_procedure_pseudo_code.json, FUN_005c4dd0: almacena un campo de estado, sin formula.
- 1792770529422_procedure_pseudo_code.json, FUN_005f3d70: decodifica013B a partir de valores recibidos y los pasa al marcador; no calcula premios.

No se recupero una formula oficial de premios en las rutas examinadas. No se dispone del ejecutable del servidor oficial; no se afirma haber demostrado que ninguna otra funcion del cliente pueda aportar datos.

La guia oficial japonesa https://alo-nhn.ujj.co.jp/playguide/gamesystem/pvp_ss.php publica tablas EXP/Skill EXP de80 a210 (actualizacion2013/11/14): derrota base, victoria minima2x y maxima3x. Indica que un ganador sin puntos cobra como derrota; los perdedores no varian por puntos. Es otra region y no determina IGG410..471 ni una regla de empate publicada. No se extrapolo ni sustituyo la configuracion actual.

## Verificacion

`tools/test_holy_runtime_regressions.py`:25 pruebas aprobadas. Diez casos nuevos comprueban entrega real en SQLite temporal, EXP y Skill EXP para ambos lados, victorias1/2, empates con puntos iguales y diferentes, cero puntos, niveles70/410 y reintento sin duplicacion. Los personajes de prueba reciben una EXP inicial coherente con su nivel para no confundir la normalizacion de datos con el premio. No se han cambiado las reglas de produccion ni reiniciado el servidor.
