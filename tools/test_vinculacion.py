"""Regresion de Rest Time: ciclos de equipo, objetos independientes y disco."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import inventario as inv
import cuentas


class VinculacionTest(unittest.TestCase):
    def test_kitsune(self):
        self.assertEqual(inv.vinculaciones_de(29484), (3, True))
        estado = {}
        self.assertTrue(inv.vincular_equipo(29484, 1001, estado))
        for _ in range(10):
            self.assertFalse(inv.vincular_equipo(29484, 1001, estado))
            for ranura in (10, 20):
                entrada = inv._entrada(1001, ranura, 29484, 1)
                self.assertEqual(inv.marcar_vinculacion(entrada, estado)[57], 2)
        otra = {}
        inv.vincular_equipo(29484, 1001, otra)
        inv.vincular_equipo(29484, 1002, estado)
        self.assertEqual(estado['vinculacion']['restantes'], 1)
        self.assertEqual(otra['vinculacion']['restantes'], 2)

    def test_persistencia(self):
        base, archivo = cuentas.BASE, cuentas.ARCHIVO
        with tempfile.TemporaryDirectory() as tmp:
            try:
                cuentas.BASE = pathlib.Path(tmp)
                cuentas.ARCHIVO = cuentas.BASE / 'cuentas.json'
                cuentas.guardar_documento({'cuentas': {'test': {'personajes': [
                    {'char_id': 1001, 'inventario': {'20': 29484}}]}}})
                estado = {}
                inv.vincular_equipo(29484, 1001, estado)
                cuentas.guardar_mejoras('test', 1001, {20: estado})
                cuentas.guardar_inventario('test', 1001, {20: 29484}, mejoras={20: estado})
                p = cuentas.cargar()['cuentas']['test']['personajes'][0]
                self.assertEqual(p['mejoras']['20']['vinculacion']['restantes'], 2)
            finally:
                cuentas.BASE, cuentas.ARCHIVO = base, archivo


if __name__ == '__main__':
    unittest.main()
