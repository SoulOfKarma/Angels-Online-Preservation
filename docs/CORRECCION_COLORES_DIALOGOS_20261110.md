# Colores de dialogos IGG — 10/11/2026

Instalado en G, en `F:\Ao Proyect\AO 2` y en el cliente
`C:\AO\Angels Online`. Sin cambios de Rust ni bases de datos.

El `2Medicine Lecturer` visible en el mensaje 60407 venia de
`/c$ 2Medicine Lecturer/c*`: el espacio rompe el marcador. Se corrigieron
tambien los mensajes 42906, 50607, 84940 y 84941.

Otros cuatro mensajes omitian por completo el color: 5394, 5395, 89911 y
89927. El MSG.XML oficial de Taiwan confirma el color 2 para sus textos
de nivel 50/51 y pesca. Se completo el marcador conservando el ingles IGG.

Importante: `/c$25 Pink Diamonds/c*` es correcto. El 2 selecciona el color
y el 5 es la cantidad visible. No se cambio a 25 diamantes ni se borro el 5.

Se actualizaron exclusivamente los nueve campos `文字` de msg.xml:

- vista vigente `extracted_paks/update26/setting/eng/msg.xml` de G y F;
- sus salidas preparadas `work/salida/setting_update26/setting/eng/msg.xml`;
- el recurso de mensajes de `update26.pak` y `update26.pak.bak` del cliente.

Los demas recursos de ambos PAK se verificaron byte a byte y por CRC.
Se reviso que los PAK 27–32 no taparan los mensajes reparados.

`tools/colores_texto.py` centraliza la correccion. `traducir.py` y
`tw_migracion.py` la aplican tambien a textos ingleses y salidas de la memoria
para que una reconstruccion no recupere el error antiguo. Esas herramientas,
el preparador y las pruebas quedaron tambien en F.

**22 pruebas pasan en G y en F.** Los mensajes vigentes ya no contienen
`/c$ `; `%1`, cantidades, escapes, tipos y el resto del texto se conservan.
Se comprobaron los hashes de los 11 archivos instalados y de los respaldos.

Los ocho archivos de servidor comprobados (app, misiones, dialogos_mapa y
plantillas/eventos, tanto G como F) siguen exactamente como los dejo Claude:
no se modificaron arboles de quest, premios ni precargas. No se ejecutaron
validadores Rust. Sin commit ni push.

Respaldo, manifiestos local/externo y verificacion final:

```text
work/backup/colores_dialogo_20261110_codex/
  local.json
  externo.json
  informe.json
  verificado.json
  before_NNN / after_NNN
```

Pruebas:

```powershell
& 'C:\laragon\bin\python\python-3.10\python.exe' -B -I -X utf8 -m pytest tools/test_colores_texto.py tools/test_traducir.py -p no:cacheprovider -q
```

Para ver el cambio, reabrir el cliente local, que carga msg.xml en memoria.
Si el servidor de F seguia abierto desde antes de los cambios de Claude,
reiniciarlo como indico el. El arreglo de color no sustituye esos cambios.
