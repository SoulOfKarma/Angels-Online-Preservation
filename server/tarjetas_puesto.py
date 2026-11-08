"""Una reconexion invalida los callbacks de tarjeta de la ficha anterior.

El ultimo callback sigue vivo al desconectar, pero nunca puede guardar una
mochila anterior a un nuevo login. El registro debil no retiene sesiones.
"""
import weakref

_SESIONES = weakref.WeakValueDictionary()


def registrar(ses):
    clave = (ses.usuario.casefold(), ses.personaje.char_id)
    anterior = _SESIONES.get(clave)
    if anterior is not None and anterior is not ses:
        anterior._tarjetas_obsoleta = True
    ses._tarjetas_obsoleta = False
    _SESIONES[clave] = ses


def vigente(ses):
    return not getattr(ses, '_tarjetas_obsoleta', False)
