from datetime import datetime, timedelta, timezone
import pytest
from tempo import entradas, esquecida, cadastros

TZ = timezone(timedelta(hours=-3))
T0 = datetime(2026, 10, 13, 10, 0, tzinfo=TZ)

@pytest.fixture
def aberta(conn):
    c = cadastros.criar(conn, "clientes", "Casttema")
    a = cadastros.listar(conn, "atividades")[0]["id"]
    return entradas.iniciar(conn, c, a, agora=T0)

def test_detecta_aberta_de_sessao_anterior(conn, aberta):
    e = esquecida.detectar(conn, inicio_sessao=T0 + timedelta(hours=8))
    assert e["id"] == aberta

def test_nao_detecta_aberta_desta_sessao(conn, aberta):
    assert esquecida.detectar(conn, inicio_sessao=T0 - timedelta(minutes=1)) is None

def test_resolver_inicio(conn, aberta):
    esquecida.resolver(conn, "inicio")
    e = entradas.por_id(conn, aberta)
    assert e["fim"] == e["inicio"] and e["minutos"] == 0

def test_resolver_agora(conn, aberta):
    esquecida.resolver(conn, "agora", agora=T0 + timedelta(hours=2))
    assert entradas.por_id(conn, aberta)["minutos"] == 120

def test_resolver_descartar(conn, aberta):
    esquecida.resolver(conn, "descartar")
    assert entradas.por_id(conn, aberta) is None

def test_modo_invalido(conn, aberta):
    with pytest.raises(ValueError):
        esquecida.resolver(conn, "pular")

def test_passou_de_12h(conn, aberta):
    curta = entradas.atual(conn, agora=T0 + timedelta(hours=11))
    longa = entradas.atual(conn, agora=T0 + timedelta(hours=12))
    assert esquecida.passou_de_12h(curta) is False
    assert esquecida.passou_de_12h(longa) is True
