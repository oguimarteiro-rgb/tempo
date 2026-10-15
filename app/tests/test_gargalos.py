from datetime import date, datetime, timedelta, timezone
from tempo import gargalos

TZ = timezone(timedelta(hours=-3))

def e(dia, hora, minutos, cliente="Casttema", atividade="Edição", cor="#ff0000", cor_atividade="#3584e4",
      clientes=None, atividades=None):
    """clientes/atividades: listas de nomes; se omitidas, vêm do cliente/atividade único (vazio = nenhum)."""
    ini = datetime(2026, 10, dia, hora, 0, tzinfo=TZ)
    if clientes is None:
        clientes = [cliente] if cliente else []
    if atividades is None:
        atividades = [atividade] if atividade else []
    return {"id": 0, "inicio": ini.isoformat(), "fim": (ini + timedelta(minutes=minutos)).isoformat(),
            "cliente_id": 1, "atividade_id": 1, "descricao": "", "cliente": clientes[0] if clientes else "",
            "atividade": atividades[0] if atividades else "", "cor": cor, "cor_atividade": cor_atividade,
            "minutos": minutos,
            "clientes": [{"id": i + 1, "nome": n, "cor": cor} for i, n in enumerate(clientes)],
            "atividades": [{"id": i + 1, "nome": n, "cor": cor_atividade} for i, n in enumerate(atividades)],
            "cliente_ids": list(range(1, len(clientes) + 1)), "atividade_ids": list(range(1, len(atividades) + 1))}

def test_por_cliente_ordena_desc():
    r = gargalos.por_cliente([e(13, 9, 30, "A"), e(13, 10, 90, "B"), e(13, 12, 10, "A")])
    assert r == [("B", 90, "#ff0000"), ("A", 40, "#ff0000")]

def test_por_atividade():
    r = gargalos.por_atividade([e(13, 9, 30, atividade="Edição"), e(13, 10, 5, atividade="Reunião")])
    assert [x[0] for x in r] == ["Edição", "Reunião"]

def test_por_atividade_usa_cor_da_atividade():
    r = gargalos.por_atividade([e(13, 9, 30, atividade="Edição", cor="#ff0000", cor_atividade="#00ff00")])
    assert r == [("Edição", 30, "#00ff00")]

def test_por_dia_semana_sempre_7():
    r = gargalos.por_dia_semana([e(13, 9, 30)])  # 2026-10-13 é terça
    assert len(r) == 7 and r[1] == ("Ter", 30, "#3584e4") and r[0][1] == 0

def test_periodos():
    hoje = date(2026, 10, 13)
    assert gargalos.periodo("esta_semana", hoje) == (date(2026, 10, 12), date(2026, 10, 18))
    assert gargalos.periodo("semana_passada", hoje) == (date(2026, 10, 5), date(2026, 10, 11))
    assert gargalos.periodo("este_mes", hoje) == (date(2026, 10, 1), date(2026, 10, 31))
    assert gargalos.periodo("personalizado", hoje, date(2026, 1, 1), date(2026, 1, 3)) == (date(2026, 1, 1), date(2026, 1, 3))

def test_periodo_anterior():
    assert gargalos.periodo_anterior(date(2026, 10, 12), date(2026, 10, 18)) == (date(2026, 10, 5), date(2026, 10, 11))

def test_fmt_h():
    assert gargalos.fmt_h(380) == "6h20"
    assert gargalos.fmt_h(45) == "45min"
    assert gargalos.fmt_h(0) == "0min"
    assert gargalos.fmt_h(120) == "2h"

def test_leitura_atividade_que_mais_cresceu():
    anterior = [e(6, 9, 60, atividade="Administrativo"), e(6, 11, 60, atividade="Edição")]
    atual = [e(13, 9, 90, atividade="Administrativo"), e(13, 11, 60, atividade="Edição")]
    frases = gargalos.leituras(atual, anterior)
    assert any("Administrativo subiu 50%" in f for f in frases)

def test_leitura_cliente_dominante():
    frases = gargalos.leituras([e(13, 9, 380, "Hornero", "Edição")], [])
    assert "Hornero: 6h20, maior parte em Edição" in frases

def test_leitura_dia_fragmentado():
    atual = [e(13, h, 5) for h in range(9, 17)] + [e(14, 9, 60)]
    frases = gargalos.leituras(atual, [])
    assert any("Terça foi o dia mais fragmentado: 8 trocas de tarefa" in f for f in frases)

def test_leitura_total_e_media():
    atual = [e(13, 9, 240), e(14, 9, 240)]
    frases = gargalos.leituras(atual, [])
    assert any(f.startswith("Total de 8h em 2 dias, média de 4h por dia") for f in frases)

def test_sem_entradas_sem_leituras():
    assert gargalos.leituras([], []) == []


def test_sem_cliente_tem_nome_proprio():
    lista = [e(1, 9, 60, cliente=""), e(1, 10, 30, cliente="")]
    assert gargalos.por_cliente(lista)[0][0] == "Sem cliente"
    assert gargalos.por_atividade([e(1, 9, 60, atividade="")])[0][0] == "Sem atividade"


def test_cada_cliente_recebe_o_tempo_inteiro():
    r = gargalos.por_cliente([e(13, 9, 60, clientes=["Pessoal", "NP Hub"]), e(13, 11, 30, clientes=["NP Hub"])])
    assert r == [("NP Hub", 90, "#ff0000"), ("Pessoal", 60, "#ff0000")]


def test_cada_atividade_recebe_o_tempo_inteiro():
    r = gargalos.por_atividade([e(13, 9, 60, atividades=["Edição", "Roteiro"])])
    assert [(n, m) for n, m, _ in r] == [("Edição", 60), ("Roteiro", 60)]


def test_combinados_so_entradas_multiplas():
    lista = [e(13, 9, 60, clientes=["Pessoal", "NP Hub"]), e(13, 10, 30, clientes=["Pessoal", "NP Hub"]),
             e(13, 11, 20, atividades=["Edição", "Roteiro"]), e(13, 12, 45)]
    r = gargalos.combinados(lista)
    assert r == [("Pessoal + NP Hub · Edição", 90, "#ff0000"), ("Casttema · Edição + Roteiro", 20, "#ff0000")]
    assert gargalos.combinados([e(13, 12, 45)]) == []


def test_leitura_combinado():
    lista = [e(13, 9, 60, clientes=["Pessoal", "NP Hub"]), e(13, 12, 45)]
    frases = gargalos.leituras(lista, [])
    assert "Combinado: Pessoal + NP Hub · Edição 1h" in frases
    assert not any(f.startswith("Combinado") for f in gargalos.leituras([e(13, 12, 45)], []))
