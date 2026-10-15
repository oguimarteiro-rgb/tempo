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

def test_dict_traz_cor_da_atividade(conn, ids):
    c, a = ids
    conn.execute("update atividades set cor = '#abcdef' where id = ?", (a,))
    conn.commit()
    eid = entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, a)
    e = entradas.por_id(conn, eid)
    assert e["cor"] == "#ff0000"          # cor do cliente continua
    assert e["cor_atividade"] == "#abcdef"


def test_cronometro_formata_hhmmss():
    assert entradas.cronometro(entradas.fmt(T0), T0 + timedelta(seconds=5)) == "00:00:05"
    assert entradas.cronometro(entradas.fmt(T0), T0 + timedelta(hours=1, minutes=2, seconds=3)) == "01:02:03"
    assert entradas.cronometro(entradas.fmt(T0), T0 + timedelta(hours=26)) == "26:00:00"
    assert entradas.cronometro(entradas.fmt(T0), T0 - timedelta(seconds=9)) == "00:00:00"


def test_iniciar_sem_cliente(conn, ids):
    _, a = ids
    eid = entradas.iniciar(conn, None, a, "reunião", agora=T0)
    e = entradas.atual(conn, agora=T0 + timedelta(minutes=10))
    assert e["id"] == eid and e["cliente_id"] is None and e["cliente"] == "" and e["minutos"] == 10
    assert entradas.recentes(conn)[0]["cliente_id"] is None


def test_recentes_desempata_pelo_id(conn, ids):
    c, a = ids
    a2 = cadastros.listar(conn, "atividades")[1]["id"]
    entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, a, "primeira")
    entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, a2, "mesma hora, depois")
    r = entradas.recentes(conn, 1)[0]
    assert r["atividade_id"] == a2 and r["ultimo_id"] == 2


def _ativ(conn, nome):
    return next(a["id"] for a in cadastros.listar(conn, "atividades") if a["nome"] == nome)


def test_iniciar_com_listas_guarda_ordem_e_principal(conn, ids):
    c, a = ids
    c2 = cadastros.criar(conn, "clientes", "NP Hub", "#00ff00")
    ed, ro = _ativ(conn, "Edição"), _ativ(conn, "Roteiro")
    eid = entradas.iniciar(conn, [c, c2], [ro, ed], "duas coisas", agora=T0)
    e = entradas.por_id(conn, eid)
    assert e["cliente_ids"] == [c, c2] and e["atividade_ids"] == [ro, ed]
    assert [x["nome"] for x in e["clientes"]] == ["Casttema", "NP Hub"]
    assert e["clientes"][1]["cor"] == "#00ff00"
    assert [x["nome"] for x in e["atividades"]] == ["Roteiro", "Edição"]
    assert e["cliente_id"] == c and e["cliente"] == "Casttema"      # principal = primeiro
    assert e["atividade_id"] == ro and e["atividade"] == "Roteiro"


def test_iniciar_com_int_continua_valendo(conn, ids):
    c, a = ids
    eid = entradas.iniciar(conn, c, a, agora=T0)
    e = entradas.por_id(conn, eid)
    assert e["cliente_ids"] == [c] and e["atividade_ids"] == [a]
    eid2 = entradas.iniciar(conn, None, a, agora=T0 + timedelta(minutes=1))
    assert entradas.por_id(conn, eid2)["clientes"] == [] and entradas.por_id(conn, eid2)["cliente"] == ""


def test_sem_atividade_e_erro(conn, ids):
    c, _ = ids
    with pytest.raises(ValueError, match="escolha pelo menos uma atividade"):
        entradas.iniciar(conn, c, [], agora=T0)
    with pytest.raises(ValueError, match="escolha pelo menos uma atividade"):
        entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, None)


def test_editar_troca_listas_e_principal(conn, ids):
    c, a = ids
    c2 = cadastros.criar(conn, "clientes", "NP Hub")
    eid = entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, a)
    entradas.editar(conn, eid, cliente_id=[c2, c], atividade_id=[a])
    e = entradas.por_id(conn, eid)
    assert e["cliente_ids"] == [c2, c] and e["cliente_id"] == c2
    entradas.editar(conn, eid, cliente_id=None)
    assert entradas.por_id(conn, eid)["clientes"] == [] and entradas.por_id(conn, eid)["cliente_id"] is None
    with pytest.raises(ValueError, match="escolha pelo menos uma atividade"):
        entradas.editar(conn, eid, atividade_id=[])


def test_apagar_leva_os_vinculos(conn, ids):
    c, a = ids
    eid = entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, a)
    entradas.apagar(conn, eid)
    assert conn.execute("select count(*) from entrada_clientes").fetchone()[0] == 0
    assert conn.execute("select count(*) from entrada_atividades").fetchone()[0] == 0


def test_rotulos(conn, ids):
    c, a = ids
    c2 = cadastros.criar(conn, "clientes", "NP Hub")
    ed, ro = _ativ(conn, "Edição"), _ativ(conn, "Roteiro")
    e = entradas.por_id(conn, entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), [c, c2], [ro, ed]))
    assert entradas.rotulo_clientes(e) == "Casttema + NP Hub"
    assert entradas.rotulo_atividades(e) == "Roteiro + Edição"
    assert entradas.rotulo(e) == "Casttema + NP Hub · Roteiro + Edição"
    so = entradas.por_id(conn, entradas.criar_manual(conn, T0 + timedelta(hours=2), T0 + timedelta(hours=3), None, ed))
    assert entradas.rotulo(so) == "Sem cliente · Edição"


def test_recentes_agrupa_por_combinacao(conn, ids):
    c, a = ids
    c2 = cadastros.criar(conn, "clientes", "NP Hub")
    entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, a, "só um")
    entradas.criar_manual(conn, T0 + timedelta(hours=1), T0 + timedelta(hours=2), [c, c2], a, "dois")
    entradas.criar_manual(conn, T0 + timedelta(hours=2), T0 + timedelta(hours=3), [c, c2], a, "dois de novo")
    r = entradas.recentes(conn)
    assert len(r) == 2
    assert r[0]["cliente_ids"] == [c, c2] and r[0]["atividade_ids"] == [a]
    assert r[0]["cliente"] == "Casttema + NP Hub" and r[0]["cliente_id"] == c
    assert r[1]["cliente_ids"] == [c]


def test_recentes_pula_combinacao_com_arquivado(conn, ids):
    c, a = ids
    c2 = cadastros.criar(conn, "clientes", "NP Hub")
    entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), [c, c2], a)
    cadastros.arquivar(conn, "clientes", c2)
    assert entradas.recentes(conn) == []
