from tempo import exportar

def test_csv():
    ent = [{"inicio": "2026-10-13T10:00:00-03:00", "fim": "2026-10-13T11:00:00-03:00", "minutos": 60,
            "cliente": "Casttema", "atividade": "Edição", "descricao": 'reel "07", final'}]
    txt = exportar.csv_texto(ent)
    linhas = txt.splitlines()
    assert linhas[0] == "inicio,fim,duracao_min,cliente,atividade,descricao"
    assert linhas[1] == '2026-10-13T10:00:00-03:00,2026-10-13T11:00:00-03:00,60,Casttema,Edição,"reel ""07"", final"'

def test_csv_vazio_so_cabecalho():
    assert exportar.csv_texto([]).splitlines() == ["inicio,fim,duracao_min,cliente,atividade,descricao"]
