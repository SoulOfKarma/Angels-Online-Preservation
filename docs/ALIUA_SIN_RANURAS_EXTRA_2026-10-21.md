# Aliua: conservar las ranuras actuales de habilidades

Por petición del usuario, completar la misión 1491 (Surpass Your Limits)
no concede ranuras ni una habilidad aleatoria. Las ramas 7, 8 y 9 siguen
administradas exclusivamente por `skills.py`, en niveles 301, 351 y 401.
El Supreme Power no aumenta ese límite ni agrega una décima habilidad.

La implementación recibida ya marcaba el poder sin conceder ramas. Se
separó esa recompensa en `supremo.conceder_poder`, que solo escribe la
marca persistente `logros_cont['supremo'] = 1`. No modifica la lista de
habilidades, su orden, niveles, EXP ni el banco de habilidades. Tampoco
rellena slots que falten: esa sigue siendo tarea del sistema por nivel.

Se conserva el flujo existente de misión, requisitos, entrega de materiales,
logro 3715, título y guardado. No se cambiaron BC/Super BC, otras misiones
ni el sistema global de slots. El texto oficial del diálogo no se reescribió;
las referencias a habilidades del Supreme Power no activan esa recompensa
en este servidor.

Pruebas: `python -m pytest tools/test_aliua_skill_slots.py -q -p no:cacheprovider`
— **14 passed**. Comprueban listas de 6/7/8/9 habilidades, repetición del
premio, límites por nivel y ejecución del diálogo de entrega/reclamación con
nueve habilidades, preservando también sus niveles y experiencia.

No requiere migración de cuentas y no elimina ni cambia habilidades ya
aprendidas. Reiniciar el servidor para cargar la separación explícita.

Actualizacion 22/10: se incorpora la etiqueta PLV mediante el bit de estado
del cliente, sin alterar nivel real ni ranuras. Ver
[PLV y competiciones](PLV_Y_COMPETICIONES_2026-10-22.md).
