# Entrega de pets — 21/10/2026

El usuario autorizó publicar las correcciones de esta sesión y los cambios
previos pendientes. No se incluyen cuentas, logs, PAK, ejecutables, claves
ni la carpeta local de evidencias REA. No se modifica BC/Super BC.

## Correcciones de esta sesión

- Progresión: la fusión ya no usa los máximos iniciales como tope de stats;
  Star-up trabaja con los atributos presentes/heredados y recalcula la cifra
  general; el primer Improved Pet Feed aplica también su incremento.
  [Auditoría y límites pendientes](PETS_ESTRELLAS_AUDITORIA_2026-10-21.md).
- Combos de pet: un solo efecto de skill, seguido de los golpes de daño;
  objetivo/contexto fijados, cancelación de callbacks inválidos y atribución
  del daño al propietario. Las rutinas de combos del personaje no se alteran.
- Equip Pet: slot 558, requisito 5.0+ estrellas, validación en ambos sentidos
  del intercambio, bonos reales de equipo, retirada del bono al desequipar,
  persistencia de metadatos y vinculación al propietario sin doble consumo.
  [Equipo, crecimiento y evidencia REA](PET_EQUIP_Y_CRECIMIENTO_2026-10-21.md).
- Crecimiento: se contrastó con XML el salto base de Battlemaid al 121 y se
  probó que `dar_exp` lo aplica. No se añadió un multiplicador nuevo.

## Cambios previos incluidos con autorización

Ya estaban modificados al comenzar las reparaciones anteriores:

- Títulos/logros: paquete incremental 0x001D código 56, evitando reconstruir
  el personaje del cliente con 0x0002 al obtener un título.
- Movimiento de pets: búsqueda acotada de caminos transitables, segmentos
  rectos seguros al atacar/seguir y alcance corriendo antes de teleportar.
- Actualización de la nota de pendientes de eventos y pase, con la
  corrección sobre títulos nuevos.

Se incluyen sin atribuirlos a la investigación de estrellas. Las pruebas
añadidas verifican el paquete de título y las primitivas de caminos; no
representan una validación visual completa de esos cambios en el cliente.

## Verificación de la entrega

```text
python -m pytest tools/test_pet_equipment.py tools/test_pet_combos.py tools/test_pet_progression.py tools/test_captured_pets.py tools/test_extended_inventory_slots.py tools/test_pet_release_regressions.py -q -p no:cacheprovider
```

Resultado: **85 passed**. Además, comprobación sintáctica de los Python
modificados y `git diff --check`.

Fallos conocidos fuera de esta corrección:

- Seis casos de `tools/test_mascotas.py`, reproducidos también con las
  funciones anteriores de progresión: guardado/despawn, HP ida/vuelta,
  reconstrucción de entrada, EXP de capturas, crecimiento de una prueba
  antigua y tope de un vale.
- Dos casos de `tools/test_passive_stats_and_sp.py` que leen offsets de
  resistencias como SP; se reprodujeron con las funciones de inventario de
  HEAD. No se cambiaron esos tests para ocultar los fallos.

## Activación y límites

Reiniciar el servidor. No se aplica una migración ni se recalculan las
tiradas antiguas de mascotas +15 al iniciar sesión. Las operaciones nuevas
usan las correcciones; equipar/desequipar recalcula los stats del personaje.

Los coeficientes oficiales de intensificación y una posible explosión
especial de verdes por nivel siguen sin determinarse. La regla de Equip
Pet del 20% de verdes procede de una referencia comunitaria original, no
de una fórmula recuperada del servidor oficial; se documenta como tal.
Los informes distinguen pruebas del servidor, análisis estático y pruebas
visuales todavía pendientes.
