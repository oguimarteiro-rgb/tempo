from datetime import date, datetime, timedelta, timezone
from tempo import cadastros, entradas, resumo

TZ = timezone(timedelta(hours=-3))
QUA = date(2026, 10, 14)   # quarta
SEX = date(2026, 10, 16)   # sexta
SAB = date(2026, 10, 17)


def t(dia, h, m=0):
    return datetime(dia.year, dia.month, dia.day, h, m, tzinfo=TZ)


def _ids(conn):
    c1 = cadastros.criar(conn, "clientes", "Casttema")
    c2 = cadastros.criar(conn, "clientes", "Hornero")
    ativ = {a["nome"]: a["id"] for a in cadastros.listar(conn, "atividades")}
    return c1, c2, ativ


def test_dia_sem_registro_nao_manda(conn):
    assert resumo.texto(conn, QUA, agora=t(QUA, 18)) is None


def test_fim_de_semana_silencio(conn):
    c1, _, ativ = _ids(conn)
    entradas.criar_manual(conn, t(SAB, 9), t(SAB, 10), c1, ativ["Edição"], "x")
    assert resumo.texto(conn, SAB, agora=t(SAB, 18)) is None


def test_resumo_do_dia(conn):
    c1, c2, ativ = _ids(conn)
    entradas.criar_manual(conn, t(QUA, 9), t(QUA, 12, 20), c1, ativ["Edição"], "reel")
    entradas.criar_manual(conn, t(QUA, 13), t(QUA, 13, 30), c2, ativ["Reunião"], "briefing")
    entradas.criar_manual(conn, t(QUA, 14), t(QUA, 14, 30), c2, ativ["Reunião"], "retorno")
    entradas.criar_manual(conn, t(QUA, 15), t(QUA, 16, 10), None, ativ["Administrativo"], "")
    txt = resumo.texto(conn, QUA, agora=t(QUA, 18))
    linhas = txt.splitlines()
    assert linhas[0] == "Tempo de hoje (qua 14/10): 5h30"
    assert linhas[1] == "Casttema 3h20 · Sem cliente 1h10 · Hornero 1h"
    assert linhas[2] == "Edição 3h20 · Administrativo 1h10 · Reunião 1h"
    assert linhas[3] == "Mais fragmentado: Reunião, 2 blocos (1h)"
    assert "Ainda rodando" not in txt and "Semana" not in txt


def test_tarefa_aberta_entra_no_total_e_avisa(conn):
    c1, _, ativ = _ids(conn)
    entradas.iniciar(conn, c1, ativ["Edição"], "cor", agora=t(QUA, 16, 50))
    txt = resumo.texto(conn, QUA, agora=t(QUA, 18))
    assert txt.splitlines()[0] == "Tempo de hoje (qua 14/10): 1h10"
    assert txt.splitlines()[-1] == "Ainda rodando: Casttema · Edição desde 16:50 (não esquece de parar)"


def test_sexta_traz_a_semana_com_comparacao(conn):
    c1, c2, ativ = _ids(conn)
    seg = SEX - timedelta(days=4)
    for d in range(5):  # 2h por dia esta semana
        entradas.criar_manual(conn, t(seg + timedelta(days=d), 9), t(seg + timedelta(days=d), 11), c1, ativ["Edição"], "")
    for d in range(5):  # 1h30 por dia na semana passada
        dia = seg - timedelta(days=7 - d)
        entradas.criar_manual(conn, t(dia, 9), t(dia, 10, 30), c2, ativ["Edição"], "")
    txt = resumo.texto(conn, SEX, agora=t(SEX, 18))
    assert "Semana: 10h, Casttema levou mais tempo (10h), +2h30 que a semana passada" in txt


def test_semana_igual_e_menor(conn):
    c1, _, ativ = _ids(conn)
    seg = SEX - timedelta(days=4)
    entradas.criar_manual(conn, t(SEX, 9), t(SEX, 10), c1, ativ["Edição"], "")
    entradas.criar_manual(conn, t(seg - timedelta(days=7), 9), t(seg - timedelta(days=7), 10), c1, ativ["Edição"], "")
    assert "igual à semana passada" in resumo.texto(conn, SEX, agora=t(SEX, 18))
    entradas.criar_manual(conn, t(seg - timedelta(days=6), 9), t(seg - timedelta(days=6), 9, 30), c1, ativ["Edição"], "")
    assert "-30min que a semana passada" in resumo.texto(conn, SEX, agora=t(SEX, 18))
