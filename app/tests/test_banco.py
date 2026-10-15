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


def test_tabelas_de_vinculo_existem(conn):
    nomes = {r[0] for r in conn.execute("select name from sqlite_master where type = 'table'")}
    assert {"entrada_clientes", "entrada_atividades"} <= nomes


def test_abrir_preenche_vinculos_de_entradas_antigas(tmp_path):
    import sqlite3
    caminho = str(tmp_path / "velho.db")
    velho = sqlite3.connect(caminho)
    velho.executescript("""
        create table clientes(id integer primary key, nome text not null unique, cor text not null default '#3584e4', arquivado integer not null default 0);
        create table atividades(id integer primary key, nome text not null unique, cor text not null default '#3584e4', arquivado integer not null default 0);
        create table entradas(id integer primary key, inicio text not null, fim text, cliente_id integer references clientes(id), atividade_id integer references atividades(id), descricao text not null default '');
        insert into clientes(id, nome) values(7, 'Casttema');
        insert into atividades(id, nome) values(3, 'Edição');
        insert into entradas(id, inicio, fim, cliente_id, atividade_id) values(1, '2026-10-13T10:00:00-03:00', '2026-10-13T11:00:00-03:00', 7, 3);
        insert into entradas(id, inicio, fim, cliente_id, atividade_id) values(2, '2026-10-13T12:00:00-03:00', '2026-10-13T13:00:00-03:00', null, 3);
    """)
    velho.commit(); velho.close()
    c = banco.abrir(caminho)
    assert [tuple(r) for r in c.execute("select entrada_id, cliente_id, ordem from entrada_clientes order by entrada_id")] == [(1, 7, 0)]
    assert [tuple(r) for r in c.execute("select entrada_id, atividade_id from entrada_atividades order by entrada_id")] == [(1, 3), (2, 3)]
    # abrir de novo não duplica
    c.close(); c = banco.abrir(caminho)
    assert c.execute("select count(*) from entrada_atividades").fetchone()[0] == 2
