from datetime import datetime, date, timedelta

CAMPOS_EDITAVEIS = {"inicio", "fim", "cliente_id", "atividade_id", "descricao"}

SELECT = """
select e.*, c.nome as cliente, c.cor as cor, a.nome as atividade
from entradas e
left join clientes c on c.id = e.cliente_id
left join atividades a on a.id = e.atividade_id
"""


def agora_local():
    return datetime.now().astimezone()


def fmt(dt):
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.isoformat(timespec="seconds")


def parse(s):
    return datetime.fromisoformat(s)


def _dict(row, agora=None):
    fim = row["fim"]
    ini = parse(row["inicio"])
    fim_dt = parse(fim) if fim else (agora or agora_local())
    return {
        "id": row["id"], "inicio": row["inicio"], "fim": fim,
        "cliente_id": row["cliente_id"], "atividade_id": row["atividade_id"],
        "descricao": row["descricao"], "cliente": row["cliente"] or "",
        "atividade": row["atividade"] or "", "cor": row["cor"] or "#3584e4",
        "minutos": int((fim_dt - ini).total_seconds() // 60),
    }


def atual(conn, agora=None):
    row = conn.execute(SELECT + " where e.fim is null").fetchone()
    return _dict(row, agora) if row else None


def por_id(conn, id, agora=None):
    row = conn.execute(SELECT + " where e.id = ?", (id,)).fetchone()
    return _dict(row, agora) if row else None


def iniciar(conn, cliente_id, atividade_id, descricao="", agora=None):
    agora = agora or agora_local()
    parar(conn, agora)
    cur = conn.execute(
        "insert into entradas(inicio, cliente_id, atividade_id, descricao) values(?,?,?,?)",
        (fmt(agora), cliente_id, atividade_id, descricao.strip()),
    )
    conn.commit()
    return cur.lastrowid


def parar(conn, agora=None):
    agora = agora or agora_local()
    cur = conn.execute("update entradas set fim = ? where fim is null", (fmt(agora),))
    conn.commit()
    return cur.rowcount > 0


def criar_manual(conn, inicio, fim, cliente_id, atividade_id, descricao=""):
    if parse(fmt(fim)) <= parse(fmt(inicio)):
        raise ValueError("fim precisa ser depois do início")
    cur = conn.execute(
        "insert into entradas(inicio, fim, cliente_id, atividade_id, descricao) values(?,?,?,?,?)",
        (fmt(inicio), fmt(fim), cliente_id, atividade_id, descricao.strip()),
    )
    conn.commit()
    return cur.lastrowid


def editar(conn, id, **campos):
    invalidos = set(campos) - CAMPOS_EDITAVEIS
    if invalidos:
        raise ValueError(f"campos inválidos: {sorted(invalidos)}")
    if not campos:
        return
    valores = {k: (fmt(v) if k in ("inicio", "fim") and v is not None else v) for k, v in campos.items()}
    sets = ", ".join(f"{k} = ?" for k in valores)
    conn.execute(f"update entradas set {sets} where id = ?", (*valores.values(), id))
    conn.commit()


def apagar(conn, id):
    conn.execute("delete from entradas where id = ?", (id,))
    conn.commit()


def _limites(de, ate):
    ini = datetime.combine(de, datetime.min.time()).astimezone()
    fim = datetime.combine(ate + timedelta(days=1), datetime.min.time()).astimezone()
    return fmt(ini), fmt(fim)


def do_dia(conn, dia, agora=None):
    ini, fim = _limites(dia, dia)
    rows = conn.execute(SELECT + " where e.inicio >= ? and e.inicio < ? order by e.inicio", (ini, fim))
    return [_dict(r, agora) for r in rows]


def no_periodo(conn, de, ate):
    ini, fim = _limites(de, ate)
    rows = conn.execute(
        SELECT + " where e.fim is not null and e.inicio >= ? and e.inicio < ? order by e.inicio", (ini, fim)
    )
    return [_dict(r) for r in rows]


def recentes(conn, n=5):
    rows = conn.execute(
        """
        select e.cliente_id, e.atividade_id, c.nome as cliente, c.cor as cor, a.nome as atividade,
               max(e.inicio) as ultimo
        from entradas e
        left join clientes c on c.id = e.cliente_id
        left join atividades a on a.id = e.atividade_id
        where (c.arquivado is null or c.arquivado = 0) and (a.arquivado is null or a.arquivado = 0)
        group by e.cliente_id, e.atividade_id
        order by ultimo desc limit ?
        """,
        (n,),
    )
    return [
        {"cliente_id": r["cliente_id"], "atividade_id": r["atividade_id"], "cliente": r["cliente"] or "",
         "atividade": r["atividade"] or "", "cor": r["cor"] or "#3584e4"}
        for r in rows
    ]
