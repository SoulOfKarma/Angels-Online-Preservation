"""Los totems de faccion: vivo abre su saludo, muerto abre el de revivir.

Cada totem lleva dos disparadores: pulsar (d=2) -> 1001 "The vine which
symbolizes..." y alma pulsa (d=6) -> 2001, que ofrece "Revival" o dice
"You are not the angel of this totem". Vivo se disparaban los dos y el
segundo pisaba al primero (Bluesand Realm y Lyceum, 26/10/2026).
"""
import pathlib
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import eventos as ev
import eventos_mundo as evm
import login


def _casos(stage):
    d = ev.del_stage(stage)
    por_evento = {}
    for x in d['disparadores']:
        dlg = [p[0] for a, p in x['haz'] if a == 25 and p]
        if dlg and not x['si']:
            por_evento.setdefault(x['ev'], {}).setdefault(x['d'], []).extend(dlg)
    casos = []
    for tile, (evento, *_resto) in d['objetos'].items():
        modos = por_evento.get(evento, {})
        if ev.PULSAR in modos and ev.ALMA_PULSA in modos:
            casos.append((tuple(map(int, tile.split(','))), modos[ev.PULSAR], modos[ev.ALMA_PULSA]))
    return casos


def _ses(stage, muerto):
    p = login.Personaje(nivel=425, hp=100, hp_max=1000, mp=100, mp_max=1000, stage=stage)
    return SimpleNamespace(personaje=p, inventario=p.inventario, rol='mundo', entity_id=p.entity_id,
                           monstruos={}, usuario=None, muerto=muerto,
                           enviar=lambda *x: None, enviar_inmediato=lambda *x: None)


@pytest.mark.parametrize('stage', [425, 41])
def test_totem_vivo_solo_saluda_y_muerto_revive(stage):
    casos = _casos(stage)
    assert casos, 'no hay totems con los dos disparadores en %d' % stage
    for tile, vivo, alma in casos:
        dlg_vivo = [e[1] for e in evm.al_pulsar(_ses(stage, False), tile) if e[0] == 'dialogo']
        dlg_alma = [e[1] for e in evm.al_pulsar(_ses(stage, True), tile) if e[0] == 'dialogo']
        assert dlg_vivo == vivo, (stage, tile, dlg_vivo)
        assert dlg_alma == alma, (stage, tile, dlg_alma)
