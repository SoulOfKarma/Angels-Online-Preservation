import copy
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'server'))
import cuentas
from accesos import Accesos
from recover_karmav6 import recover


def session(user='Karma'):
    return SimpleNamespace(usuario=user, desconectado=False)


def test_single_account_login_and_world_handoff():
    access = Accesos()
    login, duplicate, world = session(), session('kARMa'), session()
    assert access.login(login, login.usuario)
    assert not access.login(duplicate, duplicate.usuario)
    assert access.reservar(login, '127.0.0.1', 0)
    login.desconectado = True
    access.salir(login)
    assert not access.login(duplicate, duplicate.usuario)
    assert access.mundo(world, '127.0.0.1') == ('Karma', 0)
    assert access.mundo(session(), '127.0.0.1') is None
    access.salir(login)  # Closing old login must not release the world owner.
    assert not access.login(duplicate, duplicate.usuario)
    assert not access.reservar(login, '127.0.0.1', 0)
    world.desconectado = True
    access.salir(world)
    assert access.login(duplicate, duplicate.usuario)


def test_pending_ticket_expiration_and_nat_collision():
    now = [0]
    access = Accesos(lambda: now[0])
    a, b = session('a'), session('b')
    assert access.login(a, 'a') and access.login(b, 'b')
    assert access.reservar(a, 'ip', 1)
    assert not access.reservar(b, 'ip', 2)
    a.desconectado = True
    now[0] = 31
    assert access.mundo(session(), 'ip') is None
    assert access.login(session('a'), 'A')
    assert access.reservar(b, 'ip', 2)


def test_session_cannot_switch_accounts():
    access = Accesos()
    a = session('a')
    assert not access.reservar(a, 'ip', 0)
    assert access.login(a, 'a')
    assert not access.login(a, 'b')


def test_dispatcher_rejects_second_login_and_world_ticket_replay(monkeypatch):
    import app
    import login_server
    server = app.Servidor.__new__(app.Servidor)
    server.accesos = Accesos()
    first = session()
    assert server.accesos.login(first, first.usuario)
    packets = []
    second = session('karma')
    second.rol = 'login'
    second.enviar_crudo = packets.append
    monkeypatch.setattr(login_server, 'usuario_de_auth', lambda body: 'karma')
    monkeypatch.setattr(cuentas, 'guardar_muestra_auth', lambda *a: None)
    monkeypatch.setattr(cuentas, 'validar', lambda *a: ({'personajes':[]}, 'ok'))
    server.manejar(second, 2, None, None, ('ip', 123), b'')
    assert packets == [login_server.respuesta_error()]
    world = session()
    world.rol, world.entity_id = 'mundo', 0
    server.manejar(world, 2, None, None, ('ip', 456), b'')
    assert world.entity_id == 0


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(cuentas, 'DB_PATH', tmp_path/'accounts.db')
    monkeypatch.setattr(cuentas, '_notificar_cambio', lambda **kw: None)
    with sqlite3.connect(cuentas.DB_PATH) as c:
        c.execute('CREATE TABLE cuentas(usuario TEXT PRIMARY KEY COLLATE NOCASE, password TEXT)')
        c.execute('CREATE TABLE personajes(usuario TEXT COLLATE NOCASE,char_id INTEGER,ranura INTEGER,nombre TEXT,datos TEXT,PRIMARY KEY(usuario,ranura))')


def test_creation_does_not_replace_inventory_or_repeat_name(db):
    first = {'nombre':'Unique','ranura':0,'inventario':{'3':69572},'char_id':1007}
    cuentas.guardar_personaje_nuevo('a', first)
    with pytest.raises(ValueError, match='name'):
        cuentas.guardar_personaje_nuevo('b', {'nombre':'uNIQUE','ranura':0})
    with pytest.raises(ValueError, match='occupied'):
        cuentas.guardar_personaje_nuevo('a', {'nombre':'Different','ranura':0})
    with sqlite3.connect(cuentas.DB_PATH) as c:
        assert json.loads(c.execute('SELECT datos FROM personajes').fetchone()[0])['inventario'] == {'3':69572}
    second = {'nombre':'Other','ranura':0,'char_id':first['char_id']}
    cuentas.guardar_personaje_nuevo('b', second)
    assert second['char_id'] != first['char_id']


def test_recovery_preserves_progress_and_moved_stacks():
    old = {'char_id':1007,'inventario':{'0':1,'3':69572,'20':999,'22':25832},'cantidades':{'22':394},'mejoras':{'3':{'veces':15,'gemas':[72993]*5},'27':{'stale':True}}}
    current = {'char_id':1007,'nombre':'KarmaV6','nivel':434,'oro':8122,'habilidades':[[17,424,123]],'inventario':{'0':1,'3':19856,'20':25832,'21':42399,'376':10115},'cantidades':{'20':397,'21':400}}
    untouched = copy.deepcopy(current)
    fixed = recover(current, old)
    assert current == untouched
    assert fixed['nivel'] == 434 and fixed['habilidades'] == current['habilidades']
    assert fixed['inventario']['3'] == 69572
    assert fixed['mejoras']['3']['gemas'] == [72993]*5
    assert '27' not in fixed['mejoras']
    assert list(fixed['inventario'].values()).count(25832) == 1
    assert fixed['cantidades']['22'] == 397
    assert fixed['inventario']['20'] == 999
    assert fixed['inventario']['21'] == 42399
    assert fixed['oro'] == fixed['cantidades']['0'] == 8122
