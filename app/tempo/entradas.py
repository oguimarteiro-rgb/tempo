from datetime import datetime, date, timedelta

CAMPOS_EDITAVEIS = {"inicio", "fim", "cliente_id", "atividade_id", "descricao"}

SELECT = """
select e.*, c.nome as cliente, c.cor as cor, a.nome as atividade, a.cor as cor_atividade
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


def cronometro(inicio_iso, agora=None):
    """Tempo corrido desde o início como HH:MM:SS (horas não viram dias)."""
    seg = max(0, int(((agora or agora_local()) - parse(inicio_iso)).total_seconds()))
    return f"{seg // 3600:02d}:{seg % 3600 // 60:02d}:{seg % 60:02d}"


def _ids(valor):
    """int, None ou lista -> lista de ids sem repetição, na ordem dada."""
    if valor is None:
        return []
    if isinstance(valor, int):
        return [valor]
    vistos = []
    for v in valor:
        if v is not None and v not in vistos:
            vistos.append(v)
    return vistos


def _exigir_atividade(atividade_ids):
    if not atividade_ids:
        raise ValueError("escolha pelo menos uma atividade")


def _gravar_vinculos(conn, eid, cliente_ids, atividade_ids):
    """Grava as listas e deixa as colunas da entrada apontando pro principal (primeiro)."""
    conn.execute("delete from entrada_clientes where entrada_id = ?", (eid,))
    conn.execute("delete from entrada_atividades where entrada_id = ?", (eid,))
    conn.executemany("insert into entrada_clientes(entrada_id, cliente_id, ordem) values(?,?,?)",
                     [(eid, cid, i) for i, cid in enumerate(cliente_ids)])
    conn.executemany("insert into entrada_atividades(entrada_id, atividade_id, ordem) values(?,?,?)",
                     [(eid, aid, i) for i, aid in enumerate(atividade_ids)])
    conn.execute("update entradas set cliente_id = ?, atividade_id = ? where id = ?",
                 (cliente_ids[0] if cliente_ids else None, atividade_ids[0] if atividade_ids else None, eid))


def _vinculos(conn, eids):
    """{entrada_id: ([clientes], [atividades])} com {"id","nome","cor"} na ordem gravada."""
    por = {eid: ([], []) for eid in eids}
    if not eids:
        return por
    marcas = ",".join("?" * len(eids))
    for r in conn.execute(f"select ec.entrada_id, c.id, c.nome, c.cor from entrada_clientes ec "
                          f"join clientes c on c.id = ec.cliente_id where ec.entrada_id in ({marcas}) "
                          f"order by ec.entrada_id, ec.ordem", list(eids)):
        por[r[0]][0].append({"id": r[1], "nome": r[2], "cor": r[3]})
    for r in conn.execute(f"select ea.entrada_id, a.id, a.nome, a.cor from entrada_atividades ea "
                          f"join atividades a on a.id = ea.atividade_id where ea.entrada_id in ({marcas}) "
                          f"order by ea.entrada_id, ea.ordem", list(eids)):
        por[r[0]][1].append({"id": r[1], "nome": r[2], "cor": r[3]})
    return por


def _dict(row, vinc, agora=None):
    fim = row["fim"]
    ini = parse(row["inicio"])
    fim_dt = parse(fim) if fim else (agora or agora_local())
    clientes, atividades = vinc
    return {
        "id": row["id"], "inicio": row["inicio"], "fim": fim,
        "cliente_id": row["cliente_id"], "atividade_id": row["atividade_id"],
        "descricao": row["descricao"], "cliente": row["cliente"] or "",
        "atividade": row["atividade"] or "", "cor": row["cor"] or "#3584e4",
        "cor_atividade": row["cor_atividade"] or "#3584e4",
        "minutos": int((fim_dt - ini).total_seconds() // 60),
        "clientes": clientes, "atividades": atividades,
        "cliente_ids": [c["id"] for c in clientes], "atividade_ids": [a["id"] for a in atividades],
    }


def _dicts(conn, rows, agora=None):
    rows = list(rows)
    vinc = _vinculos(conn, [r["id"] for r in rows])
    return [_dict(r, vinc[r["id"]], agora) for r in rows]


def rotulo_clientes(e):
    return " + ".join(c["nome"] for c in e["clientes"]) or "Sem cliente"


def rotulo_atividades(e):
    return " + ".join(a["nome"] for a in e["atividades"]) or "Sem atividade"


def rotulo(e):
    return f"{rotulo_clientes(e)} · {rotulo_atividades(e)}"


def atual(conn, agora=None):
    row = conn.execute(SELECT + " where e.fim is null").fetchone()
    return _dicts(conn, [row], agora)[0] if row else None


def por_id(conn, id, agora=None):
    row = conn.execute(SELECT + " where e.id = ?", (id,)).fetchone()
    return _dicts(conn, [row], agora)[0] if row else None


def iniciar(conn, clientes, atividades, descricao="", agora=None):
    cliente_ids, atividade_ids = _ids(clientes), _ids(atividades)
    _exigir_atividade(atividade_ids)
    agora = agora or agora_local()
    parar(conn, agora)
    cur = conn.execute("insert into entradas(inicio, descricao) values(?,?)", (fmt(agora), descricao.strip()))
    _gravar_vinculos(conn, cur.lastrowid, cliente_ids, atividade_ids)
    conn.commit()
    return cur.lastrowid


def parar(conn, agora=None):
    agora = agora or agora_local()
    cur = conn.execute("update entradas set fim = ? where fim is null", (fmt(agora),))
    conn.commit()
    return cur.rowcount > 0


def criar_manual(conn, inicio, fim, clientes, atividades, descricao=""):
    cliente_ids, atividade_ids = _ids(clientes), _ids(atividades)
    _exigir_atividade(atividade_ids)
    if parse(fmt(fim)) <= parse(fmt(inicio)):
        raise ValueError("fim precisa ser depois do início")
    cur = conn.execute("insert into entradas(inicio, fim, descricao) values(?,?,?)",
                       (fmt(inicio), fmt(fim), descricao.strip()))
    _gravar_vinculos(conn, cur.lastrowid, cliente_ids, atividade_ids)
    conn.commit()
    return cur.lastrowid


def editar(conn, id, **campos):
    invalidos = set(campos) - CAMPOS_EDITAVEIS
    if invalidos:
        raise ValueError(f"campos inválidos: {sorted(invalidos)}")
    if not campos:
        return
    atual_e = por_id(conn, id)
    if atual_e is None:
        return
    campos_originais = set(campos)
    mexe_vinculos = "cliente_id" in campos or "atividade_id" in campos
    cliente_ids = _ids(campos.pop("cliente_id")) if "cliente_id" in campos else atual_e["cliente_ids"]
    atividade_ids = _ids(campos.pop("atividade_id")) if "atividade_id" in campos else atual_e["atividade_ids"]
    if "atividade_id" in campos_originais:
        _exigir_atividade(atividade_ids)
    if campos:
        valores = {k: (fmt(v) if k in ("inicio", "fim") and v is not None else v) for k, v in campos.items()}
        sets = ", ".join(f"{k} = ?" for k in valores)
        conn.execute(f"update entradas set {sets} where id = ?", (*valores.values(), id))
    if mexe_vinculos:
        _gravar_vinculos(conn, id, cliente_ids, atividade_ids)
    conn.commit()


def apagar(conn, id):
    conn.execute("delete from entrada_clientes where entrada_id = ?", (id,))
    conn.execute("delete from entrada_atividades where entrada_id = ?", (id,))
    conn.execute("delete from entradas where id = ?", (id,))
    conn.commit()


def _limites(de, ate):
    ini = datetime.combine(de, datetime.min.time()).astimezone()
    fim = datetime.combine(ate + timedelta(days=1), datetime.min.time()).astimezone()
    return fmt(ini), fmt(fim)


def do_dia(conn, dia, agora=None):
    ini, fim = _limites(dia, dia)
    rows = conn.execute(SELECT + " where e.inicio >= ? and e.inicio < ? order by e.inicio", (ini, fim))
    return _dicts(conn, rows, agora)


def no_periodo(conn, de, ate):
    ini, fim = _limites(de, ate)
    rows = conn.execute(
        SELECT + " where e.fim is not null and e.inicio >= ? and e.inicio < ? order by e.inicio", (ini, fim)
    )
    return _dicts(conn, rows)


def recentes(conn, n=5, amostra=60):
    """Últimas combinações distintas (mesmos clientes e atividades, na mesma ordem), da mais nova pra mais
    velha. Combinação com item arquivado fica de fora."""
    rows = conn.execute(SELECT + " order by e.inicio desc, e.id desc limit ?", (amostra,)).fetchall()
    arquivados_c = {r["id"] for r in conn.execute("select id from clientes where arquivado = 1")}
    arquivados_a = {r["id"] for r in conn.execute("select id from atividades where arquivado = 1")}
    vistas, saida = set(), []
    for e in _dicts(conn, rows):
        chave = (tuple(e["cliente_ids"]), tuple(e["atividade_ids"]))
        if chave in vistas:
            continue
        vistas.add(chave)
        if set(e["cliente_ids"]) & arquivados_c or set(e["atividade_ids"]) & arquivados_a:
            continue
        saida.append({
            "cliente_id": e["cliente_id"], "atividade_id": e["atividade_id"],
            "cliente_ids": e["cliente_ids"], "atividade_ids": e["atividade_ids"],
            "cliente": " + ".join(c["nome"] for c in e["clientes"]),
            "atividade": " + ".join(a["nome"] for a in e["atividades"]),
            "cor": e["cor"], "ultimo": e["inicio"], "ultimo_id": e["id"],
        })
        if len(saida) == n:
            break
    return saida
