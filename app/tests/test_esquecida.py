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

def test_entrada_do_mesmo_segundo_da_sessao_nao_e_esquecida(conn, tmp_path):
    from tempo import sessao
    c = cadastros.criar(conn, "clientes", "Casttema")
    a = cadastros.listar(conn, "atividades")[0]["id"]
    agora = T0.replace(microsecond=700000)
    inicio = sessao.inicio_sessao(tmp_path, agora=agora)
    entradas.iniciar(conn, c, a, agora=agora)  # gravada truncada em segundos
    assert inicio.microsecond == 0
    assert esquecida.detectar(conn, inicio) is None


def test_resolver_com_id_age_so_na_entrada_detectada(conn, aberta):
    detectada = esquecida.detectar(conn, inicio_sessao=T0 + timedelta(hours=8))
    c = cadastros.criar(conn, "clientes", "Viretto")
    a = cadastros.listar(conn, "atividades")[0]["id"]
    nova = entradas.iniciar(conn, c, a, agora=T0 + timedelta(hours=9))  # fecha a antiga
    antiga_antes = entradas.por_id(conn, aberta)
    esquecida.resolver(conn, "descartar", id=detectada["id"])
    assert entradas.por_id(conn, nova) is not None
    assert entradas.atual(conn)["id"] == nova
    assert entradas.por_id(conn, aberta) == antiga_antes
    assert antiga_antes["fim"] is not None


def test_resolver_com_id_inexistente_nao_faz_nada(conn, aberta):
    esquecida.resolver(conn, "inicio", id=aberta + 99)
    assert entradas.atual(conn)["id"] == aberta
    assert entradas.por_id(conn, aberta)["fim"] is None


def test_resolver_com_id_da_aberta_age(conn, aberta):
    esquecida.resolver(conn, "agora", agora=T0 + timedelta(hours=1), id=aberta)
    assert entradas.por_id(conn, aberta)["minutos"] == 60
