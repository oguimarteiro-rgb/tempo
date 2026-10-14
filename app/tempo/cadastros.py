import sqlite3

TABELAS = ("clientes", "atividades")


def _validar(tabela):
    if tabela not in TABELAS:
        raise ValueError(f"tabela inválida: {tabela}")


def _dict(row):
    return {"id": row["id"], "nome": row["nome"], "cor": row["cor"], "arquivado": bool(row["arquivado"])}


def listar(conn, tabela, incluir_arquivados=False):
    _validar(tabela)
    sql = f"select * from {tabela}"
    if not incluir_arquivados:
        sql += " where arquivado = 0"
    return [_dict(r) for r in conn.execute(sql + " order by nome collate nocase")]


def criar(conn, tabela, nome, cor="#3584e4"):
    _validar(tabela)
    try:
        cur = conn.execute(f"insert into {tabela}(nome, cor) values(?, ?)", (nome.strip(), cor))
    except sqlite3.IntegrityError:
        raise ValueError(f"já existe {tabela[:-1]} chamado {nome!r}") from None
    conn.commit()
    return cur.lastrowid


def renomear(conn, tabela, id, nome):
    _validar(tabela)
    try:
        conn.execute(f"update {tabela} set nome = ? where id = ?", (nome.strip(), id))
    except sqlite3.IntegrityError:
        raise ValueError(f"já existe {tabela[:-1]} chamado {nome!r}") from None
    conn.commit()


def trocar_cor(conn, tabela, id, cor):
    _validar(tabela)
    conn.execute(f"update {tabela} set cor = ? where id = ?", (cor, id))
    conn.commit()


def arquivar(conn, tabela, id, arquivado=True):
    _validar(tabela)
    conn.execute(f"update {tabela} set arquivado = ? where id = ?", (1 if arquivado else 0, id))
    conn.commit()
