"""Restore character social UI after the native map-loading reset."""
import logging

log=logging.getLogger('social')


def loaded(session,sessions):
    if not getattr(session,'personaje',None):return
    import amigos,correo,chatrooms,minigames
    # Keep each service independent: a failed room restore cannot hide mail.
    for service in (
        lambda:amigos.sincronizar(session,sessions,notify=True),
        lambda:correo.loaded(session),
        lambda:chatrooms.loaded(session),
        lambda:minigames.loaded(session),
    ):
        try:service()
        except Exception:log.exception('Could not restore a social service after map loading')
