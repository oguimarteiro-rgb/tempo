from tempo import exportar

def test_csv():
    ent = [{"inicio": "2026-10-13T10:00:00-03:00", "fim": "2026-10-13T11:00:00-03:00", "minutos": 60,
            "clientes": [{"id": 1, "nome": "Casttema", "cor": "#f00"}, {"id": 2, "nome": "NP Hub", "cor": "#0f0"}],
            "atividades": [{"id": 1, "nome": "Edição", "cor": "#00f"}], "descricao": 'reel "07", final'}]
    txt = exportar.csv_texto(ent)
    linhas = txt.splitlines()
    assert linhas[0] == "inicio,fim,duracao_min,cliente,atividade,descricao"
    assert linhas[1] == '2026-10-13T10:00:00-03:00,2026-10-13T11:00:00-03:00,60,Casttema + NP Hub,Edição,"reel ""07"", final"'


def test_csv_sem_cliente_fica_vazio():
    ent = [{"inicio": "2026-10-13T10:00:00-03:00", "fim": None, "minutos": 5, "clientes": [],
            "atividades": [{"id": 1, "nome": "Edição", "cor": "#00f"}], "descricao": ""}]
    assert exportar.csv_texto(ent).splitlines()[1] == "2026-10-13T10:00:00-03:00,,5,,Edição,"


def test_csv_vazio_so_cabecalho():
    assert exportar.csv_texto([]).splitlines() == ["inicio,fim,duracao_min,cliente,atividade,descricao"]
