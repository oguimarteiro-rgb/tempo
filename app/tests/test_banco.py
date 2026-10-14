import sqlite3
from tempo import banco

def test_abrir_cria_tabelas(conn):
    nomes = {r["name"] for r in conn.execute("select name from sqlite_master where type='table'")}
    assert {"clientes", "atividades", "entradas"} <= nomes

def test_atividades_padrao_inseridas_uma_vez(conn):
    nomes = [r["nome"] for r in conn.execute("select nome from atividades order by id")]
    assert nomes == ["Edição", "Captação", "Reunião", "Roteiro", "Administrativo", "Estudo", "Deslocamento"]

def test_abrir_duas_vezes_nao_duplica(tmp_path):
    p = str(tmp_path / "t.db")
    banco.abrir(p).close()
    c = banco.abrir(p)
    assert c.execute("select count(*) from atividades").fetchone()[0] == 7
    c.close()

def test_so_uma_entrada_aberta(conn):
    conn.execute("insert into entradas(inicio) values('2026-10-13T10:00:00-03:00')")
    try:
        conn.execute("insert into entradas(inicio) values('2026-10-13T11:00:00-03:00')")
        assert False, "aceitou duas entradas abertas"
    except sqlite3.IntegrityError:
        pass
