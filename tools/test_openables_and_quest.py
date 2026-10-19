"""Pruebas para objetos que se abren, progreso de mision y bolsas de la suerte."""
import pathlib
import sys
import types

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import bolsas
import inventario as inv
import misiones

class FakePersonaje:
    def __init__(self, char_id=9999, nombre="TestPlayer"):
        self.char_id = char_id
        self.entity_id = 9999
        self.nombre = nombre
        self.nivel = 90
        self.exp = 1000
        self.hp = 1000
        self.hp_max = 1000
        self.mp = 500
        self.mp_max = 500
        self.oro = 10000
        self.quests = [[976, 6]]  # En el paso 6 de la quest 976
        self.quests_completadas = []
        self.habilidades = []
        self.barra = []
        self.buffs = {}

class FakeSesion:
    def __init__(self):
        self.rol = 'mundo'
        self.usuario = 'test_user'
        self.personaje = FakePersonaje()
        self.inventario = {}
        self.cantidades = {}
        self.instancias = {}
        self.mejoras = {}
        self.enviados = []
        self.sp = 0

    def enviar(self, *pkgs):
        self.enviados.extend(pkgs)


def test_earth_fruit_openable_and_quest_progress():
    ses = FakeSesion()
    # Poner 5 Earth Fruits (12603) en la ranura 20
    ses.inventario[20] = 12603
    ses.cantidades[20] = 5

    # Simular ejecucion de 0x002E a traves de app._sacar / app._meter
    # o directamente probando la logica
    assert 12603 in bolsas.OBJETOS_MISION_OPENABLES
    info_m = bolsas.OBJETOS_MISION_OPENABLES[12603]
    assert info_m['recompensa'] == 12604
    assert info_m['qid'] == 976

    # Forzar exito
    import app
    # Probar 0x002E usando struct.pack('<I', 20)
    import struct
    cuerpo = struct.pack('<I', 20)
    
    # Parchear random para que salga exito (0.1 < 0.5)
    import random
    orig_random = random.random
    random.random = lambda: 0.1
    try:
        # Ejecutar 0x002E en app
        app._cantidades = lambda s: s.cantidades
        app._instancias = lambda s: s.instancias
        app._ranura_de_item = lambda s, r: r
        app.cuentas.guardar_inventario = lambda *args, **kwargs: None
        
        # Enviar 0x002E
        app_dispatch = False
        # Llamar directamente a la logica de 0x002E
        # Primero ver si sacar reduce la fruta
        app._sacar(ses, 20, 1)
        assert ses.cantidades[20] == 4
        dest = app._meter(ses, 12604, 1)
        assert dest is not None
        assert ses.inventario[dest] == 12604
        
        # Comprobar progreso de mision
        pkgs = misiones.verificar_progreso_recoleccion(ses, [12604])
        assert len(pkgs) > 0
        # Debe contener Collected Elite Core (1/10)
        textos = [p for p in pkgs if b'Collected' in p or b'Elite Core' in p]
        assert len(textos) > 0, "No se genero aviso de recoleccion para Elite Core"
        print("  OK: Earth Fruit -> Elite Core x1 (1/10) verificado con exito")
    finally:
        random.random = orig_random


def test_fire_heart_openable():
    assert 8396 in bolsas.OBJETOS_MISION_OPENABLES
    info = bolsas.OBJETOS_MISION_OPENABLES[8396]
    assert info['recompensa'] == 8397
    assert info['qid'] == 912
    print("  OK: Fire Heart configurado para Mutant Element (8397)")


def test_sealed_magic_stones():
    # Kyrio Magic Stone
    assert 60534 in bolsas.PIEDRAS_SELLADAS
    assert bolsas.PIEDRAS_SELLADAS[60534] == 63816
    assert 63813 in bolsas.PIEDRAS_SELLADAS
    assert bolsas.PIEDRAS_SELLADAS[63813] == 63816
    # Grand Angel Magic Stone
    assert bolsas.PIEDRAS_SELLADAS[35533] == 35530
    # Starfall Angel Magic Stone
    assert bolsas.PIEDRAS_SELLADAS[81301] == 81304
    print("  OK: Piedras magicas selladas desellan a sus gemelos correctos")


def test_extra_bags_from_drops_bolsas():
    # Angel's Egg(M) 3943 (cat 扭蛋, drop 772)
    assert bolsas.es_bolsa(3943), "Angel's Egg 3943 no es reconocido como bolsa"
    premio = bolsas.abrir(3943)
    assert premio is not None, "Angel's Egg 3943 no pudo abrirse"
    assert premio[0] > 0 and premio[1] > 0
    
    # Comprobar que hay miles de bolsas adicionales
    extra = bolsas._cargar_extra()
    assert len(extra) > 5000, f"Se esperaban mas de 5000 bolsas extra, hay {len(extra)}"
    print(f"  OK: {len(extra)} bolsas y huevos adicionales cargados y funcionales")


if __name__ == '__main__':
    test_earth_fruit_openable_and_quest_progress()
    test_fire_heart_openable()
    test_sealed_magic_stones()
    test_extra_bags_from_drops_bolsas()
    print("Todos los tests de openables y misiones pasaron exitosamente!")

