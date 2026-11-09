"""Identidad de sesion de los callbacks; no importa cuentas ni abre SQLite."""
import gc
import pathlib
import sys
import unittest
import weakref
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import tarjetas_puesto as tarjetas


class Sesion:
    def __init__(self, usuario='Cuenta', char_id=10):
        self.usuario = usuario
        self.personaje = SimpleNamespace(char_id=char_id)


class Callbacks(unittest.TestCase):
    def setUp(self):
        tarjetas._SESIONES.clear()

    def test_reconexion_invalida_anterior(self):
        vieja, nueva = Sesion(), Sesion('cUENTA')
        tarjetas.registrar(vieja)
        tarjetas.registrar(nueva)
        self.assertFalse(tarjetas.vigente(vieja))
        self.assertTrue(tarjetas.vigente(nueva))

    def test_doble_reconexion_no_resucita_sesiones(self):
        sesiones = [Sesion() for _ in range(3)]
        for sesion in sesiones:
            tarjetas.registrar(sesion)
        self.assertEqual([tarjetas.vigente(s) for s in sesiones], [False, False, True])

    def test_otro_personaje_no_anula_su_callback_offline(self):
        a, b = Sesion(), Sesion(char_id=11)
        tarjetas.registrar(a)
        tarjetas.registrar(b)
        self.assertTrue(tarjetas.vigente(a))
        self.assertTrue(tarjetas.vigente(b))

    def test_otra_cuenta_no_anula(self):
        a, b = Sesion(), Sesion('Otra')
        tarjetas.registrar(a)
        tarjetas.registrar(b)
        self.assertTrue(tarjetas.vigente(a))

    def test_registrar_misma_sesion_es_idempotente(self):
        a = Sesion()
        tarjetas.registrar(a)
        tarjetas.registrar(a)
        self.assertTrue(tarjetas.vigente(a))

    def test_no_retiene_la_sesion_y_el_callback_viejo_sigue_anulado(self):
        vieja, nueva = Sesion(), Sesion()
        tarjetas.registrar(vieja)
        tarjetas.registrar(nueva)
        ref = weakref.ref(nueva)
        del nueva
        gc.collect()
        self.assertIsNone(ref())
        self.assertFalse(tarjetas.vigente(vieja))
        self.assertEqual(len(tarjetas._SESIONES), 0)


if __name__ == '__main__':
    unittest.main()
