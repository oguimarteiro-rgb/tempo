import pytest
from tempo import cadastros

def test_criar_e_listar_cliente(conn):
    cid = cadastros.criar(conn, "clientes", "Casttema", "#ff0000")
    lista = cadastros.listar(conn, "clientes")
    assert lista == [{"id": cid, "nome": "Casttema", "cor": "#ff0000", "arquivado": False}]

def test_arquivado_some_da_lista_padrao(conn):
    cid = cadastros.criar(conn, "clientes", "Viretto")
    cadastros.arquivar(conn, "clientes", cid)
    assert cadastros.listar(conn, "clientes") == []
    assert cadastros.listar(conn, "clientes", incluir_arquivados=True)[0]["arquivado"] is True

def test_renomear_e_trocar_cor(conn):
    cid = cadastros.criar(conn, "atividades", "Teste")
    cadastros.renomear(conn, "atividades", cid, "Teste 2")
    cadastros.trocar_cor(conn, "atividades", cid, "#123456")
    item = [a for a in cadastros.listar(conn, "atividades") if a["id"] == cid][0]
    assert (item["nome"], item["cor"]) == ("Teste 2", "#123456")

def test_tabela_invalida(conn):
    with pytest.raises(ValueError):
        cadastros.listar(conn, "usuarios")

def test_nome_duplicado(conn):
    cadastros.criar(conn, "clientes", "Hornero")
    with pytest.raises(ValueError):
        cadastros.criar(conn, "clientes", "Hornero")

def test_renomear_duplicado(conn):
    cadastros.criar(conn, "clientes", "Hornero")
    outro = cadastros.criar(conn, "clientes", "Viretto")
    with pytest.raises(ValueError):
        cadastros.renomear(conn, "clientes", outro, "Hornero")
