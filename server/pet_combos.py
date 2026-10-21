"""Golpes posteriores de un combo de pet; no interviene en ataques del jugador.

El primer golpe y su efecto se envian desde la IA. Repetir numero_de_dano /
cierre_de_dano aqui vuelve a lanzar la skill completa en el cliente.
"""
import asyncio

import combate
import presencia


def programar_subgolpes(ses, ficha, entidad, objetivo, dano, combo, *,
                        es_aoe, al_morir, loop=None):
    """Programa N-1 danos sin recastear. Devuelve la duracion de la rafaga.

    Los callbacks conservan la pet, propietario, mapa y blanco originales;
    nunca leen el objetivo mutable de la IA para decidir a quien golpear.
    """
    golpes = int((combo or {}).get('golpes', 1))
    if golpes <= 1 or objetivo.hp <= 0:
        return 0.0
    propietario = ses.personaje
    stage = propietario.stage
    mapa = presencia.clave_de_mapa(ses, stage)
    separacion = (combate.separacion_aoe(combo) if es_aoe else
                  max(0.05, combo.get('intervalo_ms', 200) / 1000.0))
    dano = int(dano)

    def subgolpe():
        if (getattr(ses, 'personaje', None) is not propietario
                or getattr(ses, 'muerto', False)
                or propietario.stage != stage
                or presencia.clave_de_mapa(ses, stage) != mapa
                or getattr(propietario, 'mascota', None) is not ficha
                or not ficha.get('fuera') or int(ficha.get('hp') or 0) <= 0
                or getattr(ses, 'pet_entity_id', None) != entidad
                or getattr(propietario, 'mascota_orden', 1) == 2
                or not getattr(objetivo, 'vivo', False) or objetivo.hp <= 0
                or getattr(objetivo, 'encantado', False)):
            return
        monstruos = getattr(ses, 'monstruos', ()) or ()
        actuales = monstruos.values() if isinstance(monstruos, dict) else monstruos
        if not any(m is objetivo for m in actuales):
            return
        # El callback corre fuera del tick de esta sesion. Otro jugador puede
        # haber dejado su propio contexto de atribucion entre ambos golpes.
        anterior = combate.ATACANTE[0]
        combate.ATACANTE[0] = ses
        try:
            objetivo.registrar_dano(min(objetivo.hp, dano), es_pet=True)
            objetivo.hp = max(0, objetivo.hp - dano)
            paquetes = (
                combate.numero_flotante(objetivo.entity_id, dano),
                combate.atributo(objetivo.entity_id,
                                objetivo.porcentaje if objetivo.hp > 0 else 0),
            )
            ses.enviar_inmediato(*paquetes)
            presencia.notificar_companero_accion(ses, *paquetes)
            if objetivo.hp <= 0:
                al_morir(objetivo)
        finally:
            combate.ATACANTE[0] = anterior

    loop = loop if loop is not None else asyncio.get_event_loop()
    for indice in range(1, golpes):
        loop.call_later(separacion * indice, subgolpe)
    return separacion * (golpes - 1)
