from datetime import datetime, timedelta, timezone, date
import pytest
from tempo import entradas, cadastros

TZ = timezone(timedelta(hours=-3))
T0 = datetime(2026, 10, 13, 10, 0, tzinfo=TZ)

@pytest.fixture
def ids(conn):
    c = cadastros.criar(conn, "clientes", "Casttema", "#ff0000")
    a = cadastros.listar(conn, "atividades")[0]["id"]
    return c, a

def test_iniciar_cria_entrada_aberta(conn, ids):
    c, a = ids
    eid = entradas.iniciar(conn, c, a, "reel 07", agora=T0)
    e = entradas.atual(conn)
    assert e["id"] == eid and e["fim"] is None and e["descricao"] == "reel 07"
    assert e["cliente"] == "Casttema" and e["cor"] == "#ff0000"

def test_iniciar_com_aberta_encerra_no_mesmo_instante(conn, ids):
    c, a = ids
    e1 = entradas.iniciar(conn, c, a, agora=T0)
    e2 = entradas.iniciar(conn, c, a, agora=T0 + timedelta(minutes=30))
    antiga = entradas.por_id(conn, e1)
    nova = entradas.por_id(conn, e2)
    assert antiga["fim"] == nova["inicio"]
    assert antiga["minutos"] == 30

def test_parar(conn, ids):
    c, a = ids
    assert entradas.parar(conn, agora=T0) is False
    entradas.iniciar(conn, c, a, agora=T0)
    assert entradas.parar(conn, agora=T0 + timedelta(minutes=5)) is True
    assert entradas.atual(conn) is None

def test_do_dia_e_no_periodo(conn, ids):
    c, a = ids
    entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, a)
    entradas.criar_manual(conn, T0 + timedelta(days=1), T0 + timedelta(days=1, hours=2), c, a, "amanhã")
    hoje = entradas.do_dia(conn, date(2026, 10, 13))
    assert [e["minutos"] for e in hoje] == [60]
    periodo = entradas.no_periodo(conn, date(2026, 10, 13), date(2026, 10, 14))
    assert [e["minutos"] for e in periodo] == [60, 120]

def test_criar_manual_rejeita_fim_antes(conn, ids):
    c, a = ids
    with pytest.raises(ValueError):
        entradas.criar_manual(conn, T0, T0, c, a)

def test_editar_e_apagar(conn, ids):
    c, a = ids
    eid = entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, a)
    entradas.editar(conn, eid, descricao="novo", fim=T0 + timedelta(hours=2))
    assert entradas.por_id(conn, eid)["minutos"] == 120
    assert entradas.por_id(conn, eid)["descricao"] == "novo"
    with pytest.raises(ValueError):
        entradas.editar(conn, eid, cor="#000")
    entradas.apagar(conn, eid)
    assert entradas.por_id(conn, eid) is None

def test_recentes_sao_combinacoes_distintas(conn, ids):
    c, a = ids
    c2 = cadastros.criar(conn, "clientes", "Hornero")
    for i, cli in enumerate([c, c2, c]):
        t = T0 + timedelta(hours=i)
        entradas.criar_manual(conn, t, t + timedelta(minutes=10), cli, a)
    rec = entradas.recentes(conn)
    assert [r["cliente"] for r in rec] == ["Casttema", "Hornero"]
    assert set(rec[0]) >= {"cliente_id", "atividade_id", "cliente", "atividade", "cor"}

def test_minutos_de_aberta_contam_ate_agora(conn, ids):
    c, a = ids
    entradas.iniciar(conn, c, a, agora=T0)
    e = entradas.atual(conn, agora=T0 + timedelta(minutes=42))
    assert e["minutos"] == 42
