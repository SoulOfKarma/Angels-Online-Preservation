"""Pruebas de reparto de misiones en grupo (party) al matar monstruos.

Cubre:
  1. Modo Share (0): bajas, objetos de mision (incluso para quien no gano el
     botin normal), progreso de recoleccion y _pasos_tras_botin para ambos.
  2. Modo Alone (1): cuando A mata mobs para ayudar a B (B hizo 0 de dano),
     B igual recibe conteo de baja, objetos de mision, progreso de recoleccion
     y avance de paso tras el botin, SIN quitarle EXP/oro/botin normal a A.
  3. Viceversa: B mata un mob de la mision que solo tiene A.
  4. Mision 1491 (Aliua, Pearl Cockatrice 20817) y Little Slarm en stage 57
     (npc_type 224) tambien cuentan para companeros del grupo en la sala.
  5. Companero en otro mapa NO recibe bajas ni objetos de mision.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app
import equipos
import misiones


class FakeSesion:
    def __init__(self, char_id, nombre, stage, quests=None, sala=None):
        self.addr = f'test-{char_id}'
        self.usuario = None
        self.cerrada = False
        self.entity_id = 100000 + char_id
        self.oro = 0
        self.inventario = {}
        self.cantidades = {}
        self.instancias = {}
        self.mejoras = {}
        self.mascotas = {}
        self.quest_kills = {}
        self.slarm_kills = 0
        self._sala = sala
        self.monstruos = sala.monstruos if sala is not None else {}
        self.personaje = SimpleNamespace(
            char_id=char_id,
            entity_id=self.entity_id,
            nombre=nombre,
            stage=stage,
            nivel=50,
            exp=0,
            hp=1000,
            mp=500,
            hp_max=1000,
            mp_max=500,
            sp=0,
            oro=0,
            habilidades={},
            banco=[],
            class_id=1,
            buffs={},
            mascota=None,
            quests=list(quests or []),
            quest_kills=self.quest_kills,
            inventario=self.inventario,
            cantidades=self.cantidades,
            tile_x=10,
            tile_y=10,
        )
        self.enviados = []
        self.volcados = 0

    def enviar(self, *pkts):
        self.enviados.extend(pkts)

    def enviar_inmediato(self, *pkts):
        self.enviados.extend(pkts)

    def volcar(self):
        self.volcados += 1


class FakeSala:
    def __init__(self, stage):
        self.stage = stage
        self.monstruos = {}
        self.sesiones = []


def _hacer_monstruo(eid, npc_type, nombre, dano_por=None):
    return SimpleNamespace(
        entity_id=eid,
        npc_type=npc_type,
        nombre=nombre,
        nivel=10,
        vivo=False,
        vida_combate=1,
        dano_por=dict(dano_por or {}),
        dano_jugador=100,
        dano_pet=0,
        en_combate_con=None,
        generado=False,
        es_estructura_hb=False,
        es_totem_tw=False,
    )


def _armar_grupo(sesiones, modo=0):
    equipos._GRUPOS.clear()
    equipos._DE_QUIEN.clear()
    equipos._PENDIENTES.clear()
    equipos._MODOS.clear()
    lider = sesiones[0].personaje.char_id
    equipos._GRUPOS[lider] = list(sesiones)
    equipos._MODOS[lider] = modo
    for s in sesiones:
        equipos._DE_QUIEN[s.personaje.char_id] = lider


class TestEquipoMisiones(unittest.TestCase):
    def tearDown(self):
        equipos._GRUPOS.clear()
        equipos._DE_QUIEN.clear()
        equipos._PENDIENTES.clear()
        equipos._MODOS.clear()

    def _correr_muerte(self, killer, monstruo):
        pasos_llamados = []

        def fake_pasos(ses, m, addr):
            pasos_llamados.append(ses.personaje.char_id)

        with patch.object(app, '_logros_muerte', side_effect=lambda s, a, t: app._aliua_baja(s, t)), \
             patch.object(app, '_eventos_al_morir', return_value=None), \
             patch.object(app, '_pasos_tras_botin', side_effect=fake_pasos), \
             patch.object(app, '_stats_ses', return_value=b'\x00\x00'), \
             patch('combate.botin_items', return_value=[]), \
             patch('lyceum_services.straw_drop_monstruo', return_value=[]), \
             patch('league_war.monster_dead', return_value=False):
            app._procesar_muerte_monstruo(killer, monstruo, killer.entity_id, killer.addr, espera=0.0)
        return pasos_llamados

    def test_modo_alone_ayudar_companero_da_baja_item_y_pasos(self):
        """En modo Alone (1), A mata mob para la mision de B sin que B pegue:
        B recibe kill count (1_1 -> npc 19), item de recoleccion (1607_3 -> item 80422)
        y corre _pasos_tras_botin, pero NO le quita EXP ni oro a A."""
        sala = FakeSala(stage=101)
        a = FakeSesion(1, 'HelperA', 101, quests=[], sala=sala)
        b = FakeSesion(2, 'QuestB', 101, quests=[(1, 1), (1607, 3)], sala=sala)
        sala.sesiones = [a, b]
        _armar_grupo([a, b], modo=1)

        # 1) Mision de caceria (1_1: npc_type 19)
        m_hunt = _hacer_monstruo(5001, 19, 'Slime', dano_por={1: 100})
        pasos_hunt = self._correr_muerte(a, m_hunt)
        self.assertEqual(b.personaje.quest_kills.get('1_1'), 1)
        self.assertIn(1, pasos_hunt)
        self.assertIn(2, pasos_hunt)

        # 2) Mision de recoleccion (1607_3: npc_type 23863 suelta item 80422)
        exp_a_antes, oro_a_antes = a.personaje.exp, a.oro
        exp_b_antes, oro_b_antes = b.personaje.exp, b.oro
        m_rec = _hacer_monstruo(5002, 23863, 'Wild Grass Demon', dano_por={1: 100})
        pasos_rec = self._correr_muerte(a, m_rec)

        # B recibio el objeto de mision 80422 aunque hizo 0 de dano en modo Alone
        self.assertIn(80422, b.inventario.values())
        # Y B no robo EXP ni oro de A
        self.assertEqual(b.personaje.exp, exp_b_antes)
        self.assertEqual(b.oro, oro_b_antes)
        self.assertGreater(a.personaje.exp, exp_a_antes)
        # _pasos_tras_botin corrio para ambos
        self.assertIn(1, pasos_rec)
        self.assertIn(2, pasos_rec)

    def test_modo_share_ambos_reciben_item_y_viceversa(self):
        """En modo Share (0), ambos tienen la misma mision 1607_3 y matan
        alternadamente: ambos reciben su item 80422 en cada baja."""
        sala = FakeSala(stage=101)
        a = FakeSesion(1, 'PlayerA', 101, quests=[(1607, 3)], sala=sala)
        b = FakeSesion(2, 'PlayerB', 101, quests=[(1607, 3)], sala=sala)
        sala.sesiones = [a, b]
        _armar_grupo([a, b], modo=0)

        m1 = _hacer_monstruo(5010, 23863, 'Wild Grass Demon', dano_por={1: 100})
        pasos1 = self._correr_muerte(a, m1)
        self.assertIn(80422, a.inventario.values())
        self.assertIn(80422, b.inventario.values())
        self.assertIn(1, pasos1)
        self.assertIn(2, pasos1)

        # Viceversa: B mata y ambos suman a 2
        m2 = _hacer_monstruo(5011, 23863, 'Wild Grass Demon', dano_por={2: 100})
        self._correr_muerte(b, m2)
        cnt_a = sum(a.cantidades.get(r, 1) for r, it in a.inventario.items() if it == 80422)
        cnt_b = sum(b.cantidades.get(r, 1) for r, it in b.inventario.items() if it == 80422)
        self.assertEqual(cnt_a, 2)
        self.assertEqual(cnt_b, 2)

    def test_aliua_1491_y_slarm_stage57_cuentan_en_grupo(self):
        """Quest 1491 (Pearl Cockatrice 20817 -> token 8783) y Little Slarm
        (stage 57, npc 224) cuentan para el companero de grupo en la sala."""
        sala = FakeSala(stage=57)
        a = FakeSesion(1, 'KillerA', 57, quests=[], sala=sala)
        b = FakeSesion(2, 'MateB', 57, quests=[(1491, 1)], sala=sala)
        sala.sesiones = [a, b]
        _armar_grupo([a, b], modo=1)

        m_aliua = _hacer_monstruo(5020, 20817, 'Pearl Cockatrice', dano_por={1: 100})
        self._correr_muerte(a, m_aliua)
        self.assertEqual(misiones.obtener_token_mision(b, 8783), 1)

        m_slarm = _hacer_monstruo(5021, 224, 'Little Slarm', dano_por={1: 100})
        self._correr_muerte(a, m_slarm)
        self.assertEqual(a.slarm_kills, 1)
        self.assertEqual(b.slarm_kills, 1)

    def test_companero_en_otro_mapa_no_recibe_credito(self):
        """Un companero de grupo que esta en otro mapa no recibe bajas ni items."""
        sala_a = FakeSala(stage=101)
        sala_b = FakeSala(stage=102)
        a = FakeSesion(1, 'PlayerA', 101, quests=[], sala=sala_a)
        b = FakeSesion(2, 'PlayerB', 102, quests=[(1, 1), (1607, 3)], sala=sala_b)
        sala_a.sesiones = [a]
        sala_b.sesiones = [b]
        _armar_grupo([a, b], modo=0)

        m1 = _hacer_monstruo(5030, 19, 'Slime', dano_por={1: 100})
        self._correr_muerte(a, m1)
        self.assertEqual(b.personaje.quest_kills.get('1_1', 0), 0)

        m2 = _hacer_monstruo(5031, 23863, 'Wild Grass Demon', dano_por={1: 100})
        self._correr_muerte(a, m2)
        self.assertNotIn(80422, b.inventario.values())


if __name__ == '__main__':
    unittest.main()
