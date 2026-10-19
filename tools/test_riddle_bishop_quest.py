"""Regression test for Riddle Bishop quest item drops (Nature is Crying for Help - Quest 976 step 4)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'server'))

import misiones


class MockPersonaje:
    def __init__(self, char_id=1001, stage=72):
        self.char_id = char_id
        self.nombre = 'TestAngel'
        self.stage = stage
        self.quests = [(976, 4)]
        self.inventario = {}
        self.cantidades = {}


class MockSesion:
    def __init__(self):
        self.personaje = MockPersonaje()
        self.inventario = {}
        self.cantidades = {}
        self.envios = []

    def enviar(self, *pkgs):
        self.envios.extend(pkgs)


def test_riddle_bishop_drops_black_crystal():
    misiones._cargar_db()
    ses = MockSesion()

    # Riddle Bishop (npc_type 911) must drop Black Crystal (item 12602)
    drops = misiones.verificar_botin_mision(ses, 911, 'Riddle Bishop')
    assert drops == [(12602, 1)], f"Expected [(12602, 1)], got {drops}"

    # Name variations from client texts (e.g. Riddle City Bishop) must also work
    drops_alias = misiones.verificar_botin_mision(ses, 911, 'Riddle City Bishop')
    assert drops_alias == [(12602, 1)], f"Expected [(12602, 1)], got {drops_alias}"

    drops_name_only = misiones.verificar_botin_mision(ses, 0, 'Riddle Bishop')
    assert drops_name_only == [(12602, 1)], f"Expected [(12602, 1)], got {drops_name_only}"


def test_riddle_bishop_drops_stop_at_cap():
    misiones._cargar_db()
    ses = MockSesion()
    ses.inventario = {20: 12602}
    ses.cantidades = {20: 80}

    # When player already has 80 Black Crystals, drop must cease
    drops = misiones.verificar_botin_mision(ses, 911, 'Riddle Bishop')
    assert drops == [], f"Expected empty drops at 80/80 cap, got {drops}"


def test_black_crystal_progress_notification():
    misiones._cargar_db()
    ses = MockSesion()
    ses.inventario = {20: 12602}
    ses.cantidades = {20: 1}

    # Picking up Black Crystal must generate progress notifications (aviso & quest log)
    pkgs = misiones.verificar_progreso_recoleccion(ses, [12602])
    assert len(pkgs) == 2
    assert int.from_bytes(pkgs[0][:2], 'little') == 0x000D  # Aviso MSG_TEXTO
    assert int.from_bytes(pkgs[1][:2], 'little') == 0x0021  # Quest log sync


def test_lorin_npc_interaction_and_delivery():
    misiones._cargar_db()
    ses = MockSesion()

    # Under 80: must be recoleccion_incompleta
    ses.inventario = {20: 12602}
    ses.cantidades = {20: 79}
    proc, tipo, datos = misiones.interactuar_npc(ses, 'Assistant Lorin')
    assert proc is True
    assert tipo == 'recoleccion_incompleta'

    # At 80: must advance quest to step 5 and consume Black Crystals
    ses.cantidades[20] = 80
    proc, tipo, datos = misiones.interactuar_npc(ses, 'Assistant Lorin')
    assert proc is True
    assert tipo == 'avanzada'
    assert datos.get('nuevo_paso') == 5
    assert ses.personaje.quests == [(976, 5)]
    assert ses.inventario.get(20) == 0 or 20 not in ses.inventario


if __name__ == '__main__':
    test_riddle_bishop_drops_black_crystal()
    test_riddle_bishop_drops_stop_at_cap()
    test_black_crystal_progress_notification()
    test_lorin_npc_interaction_and_delivery()
    print("All Riddle Bishop quest tests passed successfully!")

