# Vários clientes e atividades por entrada: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** uma entrada do Tempo pode ter vários clientes e várias atividades; cada um recebe o tempo inteiro nas métricas, e a linha "Combinado" mostra quanto rodou em modo múltiplo.

**Architecture:** duas tabelas de vínculo com ordem (`entrada_clientes`, `entrada_atividades`); as colunas `cliente_id`/`atividade_id` de `entradas` seguem guardando o principal (primeiro da lista). Toda escrita passa por `tempo.entradas`, que aceita int, None ou lista. Métricas, resumo, CSV, serviço D-Bus, app GTK e extensão leem as listas novas.

**Tech Stack:** Python 3 + SQLite + PyGObject (GTK4/libadwaita), GNOME Shell 50 (GJS), pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-varios-clientes-atividades.md`

## Global Constraints

- Idioma de textos de interface, comentários e commits: pt-BR. Nunca usar travessão `—`.
- pytest roda **de dentro de `app/`**: `cd ~/tempo/app && python3 -m pytest -q` (da raiz dá ModuleNotFoundError).
- Smokes GTK: `cd ~/tempo && timeout 90 env GTK_A11Y=none dbus-run-session -- python3 app/tests/smoke_janela.py`.
- Compatibilidade: dicionários de entrada mantêm `cliente`, `atividade`, `cliente_id`, `atividade_id`, `cor`, `cor_atividade` (principal). Métodos D-Bus existentes não mudam de assinatura.
- Lista vazia de atividades é erro: `ValueError("escolha pelo menos uma atividade")`.
- Rótulos: "Sem cliente" quando sem cliente; nomes unidos por " + "; clientes e atividades separados por " · ".
- Subagentes não chamam serviço pago (claude -p, OpenRouter, Trello real) nem fazem `git push`.
- Não rodar `pkill -f` com padrão que case a própria linha de comando. O serviço real do Tempo não precisa ser reiniciado durante as tarefas (só no fim, pelo controlador).

---

### Task 1: tabelas de vínculo no banco

**Files:**
- Modify: `app/tempo/banco.py`
- Test: `app/tests/test_banco.py`

**Interfaces:**
- Produces: tabelas `entrada_clientes(entrada_id, cliente_id, ordem)` e `entrada_atividades(entrada_id, atividade_id, ordem)`; `banco.abrir()` preenche vínculos de linhas antigas a partir das colunas.

- [ ] **Step 1: escrever o teste que falha**

Acrescentar em `app/tests/test_banco.py`:

```python
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
    assert c.execute("select entrada_id, cliente_id, ordem from entrada_clientes order by entrada_id").fetchall() == [(1, 7, 0)]
    assert c.execute("select entrada_id, atividade_id from entrada_atividades order by entrada_id").fetchall() == [(1, 3), (2, 3)]
    # abrir de novo não duplica
    c.close(); c = banco.abrir(caminho)
    assert c.execute("select count(*) from entrada_atividades").fetchone()[0] == 2
```

- [ ] **Step 2: rodar e ver falhar**

Run: `cd ~/tempo/app && python3 -m pytest -q tests/test_banco.py`
Expected: FAIL (tabelas não existem).

- [ ] **Step 3: implementar**

Em `app/tempo/banco.py`, acrescentar ao fim do `SCHEMA` (antes das aspas de fechamento):

```sql
create table if not exists entrada_clientes(
  entrada_id integer not null references entradas(id) on delete cascade,
  cliente_id integer not null references clientes(id),
  ordem integer not null default 0,
  primary key(entrada_id, cliente_id)
);
create table if not exists entrada_atividades(
  entrada_id integer not null references entradas(id) on delete cascade,
  atividade_id integer not null references atividades(id),
  ordem integer not null default 0,
  primary key(entrada_id, atividade_id)
);
```

E em `abrir()`, logo depois de `conn.executescript(SCHEMA)`:

```python
    # Banco de antes das listas: cada entrada vira vínculo único a partir das colunas (idempotente).
    conn.execute("insert or ignore into entrada_clientes(entrada_id, cliente_id, ordem) "
                 "select id, cliente_id, 0 from entradas where cliente_id is not null")
    conn.execute("insert or ignore into entrada_atividades(entrada_id, atividade_id, ordem) "
                 "select id, atividade_id, 0 from entradas where atividade_id is not null")
    conn.commit()
```

- [ ] **Step 4: rodar e ver passar**

Run: `cd ~/tempo/app && python3 -m pytest -q`
Expected: tudo PASS (73 + 2).

- [ ] **Step 5: commit**

```bash
cd ~/tempo && git add app/tempo/banco.py app/tests/test_banco.py && git commit -m "Banco: tabelas de vínculo entrada-clientes e entrada-atividades"
```

---

### Task 2: `entradas` grava e lê listas

**Files:**
- Modify: `app/tempo/entradas.py`
- Test: `app/tests/test_entradas.py`

**Interfaces:**
- Consumes: tabelas da Task 1.
- Produces: `iniciar(conn, clientes, atividades, descricao="", agora=None)`, `criar_manual(conn, inicio, fim, clientes, atividades, descricao="")`, `editar(conn, id, cliente_id=..., atividade_id=..., ...)` aceitando int | None | list; dicionário com `clientes`, `atividades` (listas de `{"id","nome","cor"}`), `cliente_ids`, `atividade_ids`; `rotulo_clientes(e)`, `rotulo_atividades(e)`, `rotulo(e)`; `recentes()` por combinação com `cliente_ids`/`atividade_ids`.

- [ ] **Step 1: escrever os testes que falham**

Acrescentar em `app/tests/test_entradas.py`:

```python
def _ativ(conn, nome):
    return next(a["id"] for a in cadastros.listar(conn, "atividades") if a["nome"] == nome)


def test_iniciar_com_listas_guarda_ordem_e_principal(conn, ids):
    c, a = ids
    c2 = cadastros.criar(conn, "clientes", "NP Hub", "#00ff00")
    ed, ro = _ativ(conn, "Edição"), _ativ(conn, "Roteiro")
    eid = entradas.iniciar(conn, [c, c2], [ro, ed], "duas coisas", agora=T0)
    e = entradas.por_id(conn, eid)
    assert e["cliente_ids"] == [c, c2] and e["atividade_ids"] == [ro, ed]
    assert [x["nome"] for x in e["clientes"]] == ["Casttema", "NP Hub"]
    assert e["clientes"][1]["cor"] == "#00ff00"
    assert [x["nome"] for x in e["atividades"]] == ["Roteiro", "Edição"]
    assert e["cliente_id"] == c and e["cliente"] == "Casttema"      # principal = primeiro
    assert e["atividade_id"] == ro and e["atividade"] == "Roteiro"


def test_iniciar_com_int_continua_valendo(conn, ids):
    c, a = ids
    eid = entradas.iniciar(conn, c, a, agora=T0)
    e = entradas.por_id(conn, eid)
    assert e["cliente_ids"] == [c] and e["atividade_ids"] == [a]
    eid2 = entradas.iniciar(conn, None, a, agora=T0 + timedelta(minutes=1))
    assert entradas.por_id(conn, eid2)["clientes"] == [] and entradas.por_id(conn, eid2)["cliente"] == ""


def test_sem_atividade_e_erro(conn, ids):
    c, _ = ids
    with pytest.raises(ValueError, match="escolha pelo menos uma atividade"):
        entradas.iniciar(conn, c, [], agora=T0)
    with pytest.raises(ValueError, match="escolha pelo menos uma atividade"):
        entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, None)


def test_editar_troca_listas_e_principal(conn, ids):
    c, a = ids
    c2 = cadastros.criar(conn, "clientes", "NP Hub")
    eid = entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, a)
    entradas.editar(conn, eid, cliente_id=[c2, c], atividade_id=[a])
    e = entradas.por_id(conn, eid)
    assert e["cliente_ids"] == [c2, c] and e["cliente_id"] == c2
    entradas.editar(conn, eid, cliente_id=None)
    assert entradas.por_id(conn, eid)["clientes"] == [] and entradas.por_id(conn, eid)["cliente_id"] is None
    with pytest.raises(ValueError, match="escolha pelo menos uma atividade"):
        entradas.editar(conn, eid, atividade_id=[])


def test_apagar_leva_os_vinculos(conn, ids):
    c, a = ids
    eid = entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, a)
    entradas.apagar(conn, eid)
    assert conn.execute("select count(*) from entrada_clientes").fetchone()[0] == 0
    assert conn.execute("select count(*) from entrada_atividades").fetchone()[0] == 0


def test_rotulos(conn, ids):
    c, a = ids
    c2 = cadastros.criar(conn, "clientes", "NP Hub")
    ed, ro = _ativ(conn, "Edição"), _ativ(conn, "Roteiro")
    e = entradas.por_id(conn, entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), [c, c2], [ro, ed]))
    assert entradas.rotulo_clientes(e) == "Casttema + NP Hub"
    assert entradas.rotulo_atividades(e) == "Roteiro + Edição"
    assert entradas.rotulo(e) == "Casttema + NP Hub · Roteiro + Edição"
    so = entradas.por_id(conn, entradas.criar_manual(conn, T0 + timedelta(hours=2), T0 + timedelta(hours=3), None, ed))
    assert entradas.rotulo(so) == "Sem cliente · Edição"


def test_recentes_agrupa_por_combinacao(conn, ids):
    c, a = ids
    c2 = cadastros.criar(conn, "clientes", "NP Hub")
    entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), c, a, "só um")
    entradas.criar_manual(conn, T0 + timedelta(hours=1), T0 + timedelta(hours=2), [c, c2], a, "dois")
    entradas.criar_manual(conn, T0 + timedelta(hours=2), T0 + timedelta(hours=3), [c, c2], a, "dois de novo")
    r = entradas.recentes(conn)
    assert len(r) == 2
    assert r[0]["cliente_ids"] == [c, c2] and r[0]["atividade_ids"] == [a]
    assert r[0]["cliente"] == "Casttema + NP Hub" and r[0]["cliente_id"] == c
    assert r[1]["cliente_ids"] == [c]


def test_recentes_pula_combinacao_com_arquivado(conn, ids):
    c, a = ids
    c2 = cadastros.criar(conn, "clientes", "NP Hub")
    entradas.criar_manual(conn, T0, T0 + timedelta(hours=1), [c, c2], a)
    cadastros.arquivar(conn, "clientes", c2)
    assert entradas.recentes(conn) == []
```

- [ ] **Step 2: rodar e ver falhar**

Run: `cd ~/tempo/app && python3 -m pytest -q tests/test_entradas.py`
Expected: FAIL (KeyError `cliente_ids`, TypeError em lista, etc.).

- [ ] **Step 3: implementar**

Reescrever as partes abaixo de `app/tempo/entradas.py` (o resto fica igual):

```python
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
    cliente_ids = _ids(campos.pop("cliente_id")) if "cliente_id" in campos else atual_e["cliente_ids"]
    atividade_ids = _ids(campos.pop("atividade_id")) if "atividade_id" in campos else atual_e["atividade_ids"]
    _exigir_atividade(atividade_ids)
    if campos:
        valores = {k: (fmt(v) if k in ("inicio", "fim") and v is not None else v) for k, v in campos.items()}
        sets = ", ".join(f"{k} = ?" for k in valores)
        conn.execute(f"update entradas set {sets} where id = ?", (*valores.values(), id))
    _gravar_vinculos(conn, id, cliente_ids, atividade_ids)
    conn.commit()


def apagar(conn, id):
    conn.execute("delete from entrada_clientes where entrada_id = ?", (id,))
    conn.execute("delete from entrada_atividades where entrada_id = ?", (id,))
    conn.execute("delete from entradas where id = ?", (id,))
    conn.commit()


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
```

Atenção: o teste antigo `test_recentes` (empate no mesmo segundo, ordem por id) continua valendo com essa implementação porque a consulta ordena por `inicio desc, id desc`. Se algum teste antigo passar `atividade_id=None` pra `iniciar`/`criar_manual`, ajuste o teste pra passar uma atividade real: atividade vazia agora é erro por decisão do spec.

- [ ] **Step 4: rodar e ver passar**

Run: `cd ~/tempo/app && python3 -m pytest -q`
Expected: PASS. Se `test_esquecida.py`, `test_resumo.py` ou `test_servico.py` quebrarem por causa do `_dict` novo, leia o erro: só devem quebrar se construírem entradas sem atividade.

- [ ] **Step 5: commit**

```bash
cd ~/tempo && git add app/tempo/entradas.py app/tests/test_entradas.py && git commit -m "Entradas: listas de clientes e atividades, rótulos e recentes por combinação"
```

---

### Task 3: gargalos contam cada item e mostram "Combinado"

**Files:**
- Modify: `app/tempo/gargalos.py`
- Test: `app/tests/test_gargalos.py`

**Interfaces:**
- Consumes: entradas com `clientes`/`atividades` (Task 2).
- Produces: `por_cliente`, `por_atividade` somando pra cada item; `combinados(entradas) -> [(rotulo, minutos, cor)]`; `leituras()` com frase "Combinado: ...".

- [ ] **Step 1: ajustar o helper dos testes e escrever os que falham**

Em `app/tests/test_gargalos.py`, substituir a função `e(...)` por:

```python
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
```

E acrescentar os testes:

```python
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
```

- [ ] **Step 2: rodar e ver falhar**

Run: `cd ~/tempo/app && python3 -m pytest -q tests/test_gargalos.py`
Expected: FAIL (`combinados` não existe; por_cliente soma só o principal).

- [ ] **Step 3: implementar**

Em `app/tempo/gargalos.py`, trocar `_agrupar`, `por_cliente`, `por_atividade` por:

```python
def _itens(e, chave):
    """[(nome, cor)] de cada cliente/atividade da entrada; sem nenhum, o nome 'Sem ...'."""
    lista = e[chave + "s"]
    if not lista:
        return [(SEM[chave], e["cor"] if chave == "cliente" else e.get("cor_atividade", COR_PADRAO))]
    return [(i["nome"], i["cor"]) for i in lista]


def _agrupar(entradas, chave):
    mins = defaultdict(int)
    cores = {}
    for e in entradas:
        for nome, cor in _itens(e, chave):
            mins[nome] += e["minutos"]   # tempo inteiro pra cada item: decisão do spec
            cores.setdefault(nome, cor)
    return sorted(((k, v, cores[k]) for k, v in mins.items()), key=lambda x: -x[1])


def por_cliente(entradas):
    return _agrupar(entradas, "cliente")


def por_atividade(entradas):
    return _agrupar(entradas, "atividade")


def _multipla(e):
    return len(e["clientes"]) > 1 or len(e["atividades"]) > 1


def combinados(entradas):
    """Tempo em modo múltiplo, agrupado pelo rótulo completo, só das entradas com mais de um item."""
    from tempo.entradas import rotulo
    mins, cores = defaultdict(int), {}
    for e in entradas:
        if not _multipla(e):
            continue
        k = rotulo(e)
        mins[k] += e["minutos"]
        cores.setdefault(k, e["cor"])
    return sorted(((k, v, cores[k]) for k, v in mins.items()), key=lambda x: -x[1])
```

Em `_leitura_cliente`, trocar a linha do filtro por:

```python
    do_cliente = [e for e in atual if nome in [n for n, _ in _itens(e, "cliente")]]
```

Acrescentar antes de `leituras`:

```python
def _leitura_combinado(atual):
    grupos = combinados(atual)[:3]
    if not grupos:
        return None
    return "Combinado: " + ", ".join(f"{nome} {fmt_h(mins)}" for nome, mins, _ in grupos)
```

E incluir `_leitura_combinado(atual)` na lista de `leituras`, logo depois de `_leitura_cliente(atual)`.

- [ ] **Step 4: rodar e ver passar**

Run: `cd ~/tempo/app && python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
cd ~/tempo && git add app/tempo/gargalos.py app/tests/test_gargalos.py && git commit -m "Gargalos: cada cliente e atividade recebe o tempo inteiro, leitura Combinado"
```

---

### Task 4: resumo do Telegram e CSV

**Files:**
- Modify: `app/tempo/resumo.py`, `app/tempo/exportar.py`
- Test: `app/tests/test_resumo.py`, `app/tests/test_exportar.py`

**Interfaces:**
- Consumes: `gargalos.combinados`, `entradas.rotulo`.
- Produces: linha "Combinado: ..." no resumo; CSV com nomes unidos por " + ".

- [ ] **Step 1: escrever os testes que falham**

Em `app/tests/test_resumo.py`, acrescentar:

```python
def test_resumo_mostra_combinado_e_rotulo_completo(conn):
    c1, c2, ativ = _ids(conn)
    entradas.criar_manual(conn, t(QUA, 9), t(QUA, 10), [c1, c2], ativ["Edição"], "dois")
    entradas.criar_manual(conn, t(QUA, 10), t(QUA, 11), c1, ativ["Reunião"], "um")
    entradas.iniciar(conn, [c1, c2], [ativ["Edição"], ativ["Roteiro"]], "aberta", agora=t(QUA, 17, 30))
    txt = resumo.texto(conn, QUA, agora=t(QUA, 18))
    linhas = txt.splitlines()
    assert linhas[0] == "Tempo de hoje (qua 14/10): 2h30"
    assert "Casttema 2h30 · Hornero 1h30" == linhas[1]
    assert "Combinado: Casttema + Hornero · Edição 1h, Casttema + Hornero · Edição + Roteiro 30min" in linhas
    assert linhas[-1].startswith("Ainda rodando: Casttema + Hornero · Edição + Roteiro desde 17:30")
```

Em `app/tests/test_exportar.py`, trocar `test_csv` por:

```python
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
```

- [ ] **Step 2: rodar e ver falhar**

Run: `cd ~/tempo/app && python3 -m pytest -q tests/test_resumo.py tests/test_exportar.py`
Expected: FAIL.

- [ ] **Step 3: implementar**

`app/tempo/exportar.py`, a linha do `writerow` do laço vira:

```python
        w.writerow([e["inicio"], e["fim"] or "", e["minutos"],
                    " + ".join(c["nome"] for c in e["clientes"]),
                    " + ".join(a["nome"] for a in e["atividades"]), e["descricao"]])
```

`app/tempo/resumo.py`, em `texto()`: depois de montar `linhas` (as três primeiras) e antes de `frag`, acrescentar:

```python
    comb = gargalos.combinados(dia)
    if comb:
        linhas.append("Combinado: " + ", ".join(f"{nome} {gargalos.fmt_h(mins)}" for nome, mins, _ in comb))
```

E a linha do "Ainda rodando" vira:

```python
        linhas.append(f"Ainda rodando: {entradas.rotulo(aberta)} desde {aberta['inicio'][11:16]} (não esquece de parar)")
```

- [ ] **Step 4: rodar e ver passar**

Run: `cd ~/tempo/app && python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
cd ~/tempo && git add app/tempo/resumo.py app/tempo/exportar.py app/tests/test_resumo.py app/tests/test_exportar.py && git commit -m "Resumo e CSV: linha Combinado e nomes unidos por +"
```

---

### Task 5: serviço D-Bus `IniciarVarios`

**Files:**
- Modify: `app/tempo/servico.py`
- Test: `app/tests/test_servico.py`

**Interfaces:**
- Produces: método D-Bus `IniciarVarios(ai cliente_ids, ai atividade_ids, s descricao) -> i`; JSON de `EntradaAtual`/`Recentes` já carrega `cliente_ids`/`atividade_ids` (vem do Task 2).

- [ ] **Step 1: escrever o teste que falha**

Em `app/tests/test_servico.py`:

```python
def test_iniciar_varios(conn, sv):
    c1 = cadastros.criar(conn, "clientes", "Casttema")
    c2 = cadastros.criar(conn, "clientes", "NP Hub")
    ativ = [a["id"] for a in cadastros.listar(conn, "atividades")[:2]]
    (eid,) = sv.chamar("IniciarVarios", ([c1, c2], ativ, "duas"))
    e = json.loads(sv.chamar("EntradaAtual", ())[0])
    assert e["id"] == eid and e["cliente_ids"] == [c1, c2] and e["atividade_ids"] == ativ
    assert json.loads(sv.sinais[-1])["cliente_ids"] == [c1, c2]
    rec = json.loads(sv.chamar("Recentes", ())[0])
    assert rec[0]["cliente_ids"] == [c1, c2] and rec[0]["cliente"] == "Casttema + NP Hub"


def test_iniciar_varios_sem_atividade_e_erro(conn, sv):
    with pytest.raises(ValueError, match="escolha pelo menos uma atividade"):
        sv.chamar("IniciarVarios", ([], [], ""))
```

- [ ] **Step 2: rodar e ver falhar**

Run: `cd ~/tempo/app && python3 -m pytest -q tests/test_servico.py`
Expected: FAIL (método desconhecido).

- [ ] **Step 3: implementar**

Em `app/tempo/servico.py`, no XML, logo depois do `</method>` de `Iniciar`:

```xml
  <method name="IniciarVarios">
    <arg type="ai" name="cliente_ids" direction="in"/>
    <arg type="ai" name="atividade_ids" direction="in"/>
    <arg type="s" name="descricao" direction="in"/>
    <arg type="i" name="id" direction="out"/>
  </method>
```

Em `ASSINATURAS`, acrescentar `"IniciarVarios": "(i)"`. Em `chamar`, depois do bloco de `Iniciar`:

```python
        if nome == "IniciarVarios":
            cids, aids, desc = args
            eid = entradas.iniciar(self.conn, list(cids), list(aids), desc)
            self.notificar()
            return (eid,)
```

- [ ] **Step 4: rodar e ver passar**

Run: `cd ~/tempo/app && python3 -m pytest -q`
Expected: PASS (inclui `test_processo_real_responde_no_dbus`, que sobe o serviço de verdade num barramento próprio).

- [ ] **Step 5: commit**

```bash
cd ~/tempo && git add app/tempo/servico.py app/tests/test_servico.py && git commit -m "Serviço: IniciarVarios no D-Bus"
```

---

### Task 6: widget `SeletorMultiplo` e aba Hoje

**Files:**
- Create: `app/tempo/janela/seletor.py`
- Modify: `app/tempo/janela/hoje.py`, `app/tempo/janela/janela.py:65`
- Test: `app/tests/smoke_janela.py`

**Interfaces:**
- Produces: `SeletorMultiplo(Gtk.MenuButton)` com `set_itens(itens, selecionados)`, `get_selecionados() -> [ids]`, `set_selecionados(ids)`, sinal `"mudou"`; `itens` são dicts `{"id","nome"}`. Rótulo do botão: "Sem cliente" / "Pessoal" / "Pessoal +1" (ou o `vazio` passado no construtor quando nada marcado).
- Consumes: `entradas.iniciar/criar_manual/editar` com listas; `entradas.rotulo`.

- [ ] **Step 1: escrever o smoke que falha**

Em `app/tests/smoke_janela.py`, logo depois do bloco `rs = linhas() ... assert pag.total...` (os primeiros asserts da lista), acrescentar:

```python
# --- seletores múltiplos (cartão da aba Hoje) ---
from tempo.janela.seletor import SeletorMultiplo
nph = cadastros.criar(c, "clientes", "NP Hub", "#33d17a")
rot = next(a["id"] for a in cadastros.listar(c, "atividades") if a["nome"] == "Roteiro")
jan.atualizar()
cart = pag.cartao
assert isinstance(cart.cli, SeletorMultiplo) and isinstance(cart.ati, SeletorMultiplo)
assert cart.cli.get_selecionados() == [cid], cart.cli.get_selecionados()   # segue a tarefa mais recente
cart.cli.set_selecionados([cid, nph]); cart.ati.set_selecionados([aid, rot])
assert cart.cli.get_label() == "Casttema +1" and cart.ati.get_label() == "Edição +1", (cart.cli.get_label(), cart.ati.get_label())
cart.nome.set_text("duas coisas"); cart.iniciar(); bombear()
e_multi = entradas.atual(c)
assert e_multi["cliente_ids"] == [cid, nph] and e_multi["atividade_ids"] == [aid, rot], e_multi
assert cart.legenda.get_text() == "Casttema + NP Hub · Edição + Roteiro · duas coisas", cart.legenda.get_text()
entradas.parar(c); jan.atualizar()
assert linhas()[-1].get_title() == "Casttema + NP Hub · Edição + Roteiro", linhas()[-1].get_title()
# sem atividade marcada: Iniciar desabilita
cart.ati.set_selecionados([])
assert cart.ati.get_label() == "Atividade" and not cart.btn_iniciar.get_sensitive()
cart.ati.set_selecionados([aid]); assert cart.btn_iniciar.get_sensitive()
# diálogo edita as listas
d_m = DialogoEntrada(jan, app, entradas.do_dia(c, t.date())[-1], jan.atualizar)
assert d_m.cli.get_selecionados() == [cid, nph]
d_m.cli.set_selecionados([nph]); d_m.ati.set_selecionados([rot]); d_m._on_resp(None, "salvar")
ult = entradas.do_dia(c, t.date())[-1]
assert ult["cliente_ids"] == [nph] and ult["atividade_ids"] == [rot], ult
d_v = DialogoEntrada(jan, app, ult, jan.atualizar)
d_v.ati.set_selecionados([]); d_v._on_resp(None, "salvar")
assert d_v.erro.get_text() == "Não salvou: escolha pelo menos uma atividade", d_v.erro.get_text()
entradas.apagar(c, ult["id"]); jan.atualizar()
```

Atenção: esse bloco cria uma entrada a mais no dia e depois apaga; os asserts seguintes do arquivo (contagem de linhas, totais) devem continuar valendo. Se algum contar linhas, rode o smoke e ajuste o número esperado com o motivo no assert.

- [ ] **Step 2: rodar e ver falhar**

Run: `cd ~/tempo && timeout 90 env GTK_A11Y=none dbus-run-session -- python3 app/tests/smoke_janela.py`
Expected: falha em `from tempo.janela.seletor import SeletorMultiplo`.

- [ ] **Step 3: criar o widget**

`app/tempo/janela/seletor.py`:

```python
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GObject, Gtk


class SeletorMultiplo(Gtk.MenuButton):
    """Botão que abre uma lista de caixas de marcação. Rótulo: 'Pessoal', 'Pessoal +1' ou o texto vazio."""

    __gsignals__ = {"mudou": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, vazio, **kw):
        super().__init__(**kw)
        self._vazio = vazio
        self._itens = []
        self._caixas = {}
        self._quieto = False
        self._lista = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=6, margin_bottom=6,
                              margin_start=6, margin_end=6)
        rolagem = Gtk.ScrolledWindow(child=self._lista, propagate_natural_height=True, propagate_natural_width=True,
                                     max_content_height=320, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.set_popover(Gtk.Popover(child=rolagem))
        self._rotular()

    def set_itens(self, itens, selecionados=()):
        """itens: [{"id", "nome"}] na ordem de exibição (a ordem dos marcados segue essa lista)."""
        while (f := self._lista.get_first_child()) is not None:
            self._lista.remove(f)
        self._itens, self._caixas = list(itens), {}
        self._quieto = True
        for it in self._itens:
            caixa = Gtk.CheckButton(label=it["nome"], active=it["id"] in selecionados)
            caixa.connect("toggled", lambda *_: self._mudou())
            self._caixas[it["id"]] = caixa
            self._lista.append(caixa)
        self._quieto = False
        self._rotular()

    def get_selecionados(self):
        return [it["id"] for it in self._itens if self._caixas[it["id"]].get_active()]

    def set_selecionados(self, ids):
        self._quieto = True
        for it in self._itens:
            self._caixas[it["id"]].set_active(it["id"] in ids)
        self._quieto = False
        self._mudou()

    def _mudou(self):
        if self._quieto:
            return
        self._rotular()
        self.emit("mudou")

    def _rotular(self):
        nomes = [it["nome"] for it in self._itens if self._caixas.get(it["id"]) and self._caixas[it["id"]].get_active()]
        if not nomes:
            self.set_label(self._vazio)
        elif len(nomes) == 1:
            self.set_label(nomes[0])
        else:
            self.set_label(f"{nomes[0]} +{len(nomes) - 1}")
```

- [ ] **Step 4: usar o widget no cartão da aba Hoje**

Em `app/tempo/janela/hoje.py`:

Importar: `from tempo.janela.seletor import SeletorMultiplo`.

No `__init__` de `CartaoTimer`, trocar as duas linhas dos `Gtk.DropDown` por:

```python
        self.cli = SeletorMultiplo(SEM_CLIENTE, tooltip_text="Clientes")
        self.ati = SeletorMultiplo("Atividade", tooltip_text="Atividades")
        self.ati.connect("mudou", lambda *_: self._habilitar())
```

E `self._cid, self._aid = None, None` vira `self._cids, self._aids = [], []`.

Em `atualizar()`, a montagem da legenda vira:

```python
            partes = [entradas.rotulo(e)]
            if e["descricao"]:
                partes.append(e["descricao"])
            self.legenda.set_text(" · ".join(partes))
```

`_carregar_opcoes` inteira vira:

```python
    def _carregar_opcoes(self):
        """Seleção: se rodou tarefa nova desde a última carga (por aqui, pela barra ou pelo diálogo), segue ela;
        senão fica o que está nos seletores. Item lembrado que foi arquivado some da marcação."""
        ultimo = entradas.recentes(self.app.conn, 1)
        marca = ultimo[0]["ultimo_id"] if ultimo else None
        if marca != self._marca:
            self._marca = marca
            if ultimo:
                self._cids, self._aids = ultimo[0]["cliente_ids"], ultimo[0]["atividade_ids"]
        elif self._atividades:
            self._cids, self._aids = self.cli.get_selecionados(), self.ati.get_selecionados()
        self._clientes = cadastros.listar(self.app.conn, "clientes")
        self._atividades = cadastros.listar(self.app.conn, "atividades")
        self.cli.set_itens(self._clientes, self._cids)
        self.ati.set_itens(self._atividades, self._aids)
        self._habilitar()
```

`_habilitar` vira:

```python
    def _habilitar(self):
        self.btn_iniciar.set_sensitive(bool(self.ati.get_selecionados()) and bool(self.nome.get_text().strip()))
```

`iniciar` vira:

```python
    def iniciar(self):
        if not self.nome.get_text().strip():
            return  # o nome é obrigatório; Enter vazio não faz nada
        aids = self.ati.get_selecionados()
        if not aids:
            self.get_root().toast("Marque pelo menos uma atividade antes de iniciar")
            return
        entradas.iniciar(self.app.conn, self.cli.get_selecionados(), aids, self.nome.get_text())
        self.nome.set_text("")
        self.app.servico.notificar()  # avisa a barra do GNOME e redesenha a janela
```

Em `PaginaHoje.atualizar`, o título da linha vira `title=entradas.rotulo(e)`.

- [ ] **Step 5: usar o widget no diálogo**

Ainda em `hoje.py`, em `DialogoEntrada.__init__`, trocar o bloco de `self.clientes = ...` até o `set_selected` de `ati_idx` por:

```python
        self.clientes = self._itens("clientes", (entrada or {}).get("cliente_ids", []))
        self.atividades = self._itens("atividades", (entrada or {}).get("atividade_ids", []))
        self.cli = self._linha("Clientes", SEM_CLIENTE, self.clientes, v.get("cliente_ids", (entrada or {}).get("cliente_ids", [])))
        self.ati = self._linha("Atividades", "Atividade", self.atividades, v.get("atividade_ids", (entrada or {}).get("atividade_ids", [])))
```

(e o laço `for w in (self.desc, self.cli, self.ati, ...)` passa a adicionar `self._linha_cli` e `self._linha_ati` no lugar de `self.cli`/`self.ati`; veja abaixo.)

Substituir `_itens` e `_combo` por:

```python
    def _itens(self, tabela, ids_da_entrada):
        """Ativos, mais os arquivados da própria entrada (no fim), para Salvar não perder o vínculo."""
        itens = cadastros.listar(self.app.conn, tabela)
        faltam = [i for i in ids_da_entrada if all(it["id"] != i for it in itens)]
        if faltam:
            for i in cadastros.listar(self.app.conn, tabela, incluir_arquivados=True):
                if i["id"] in faltam:
                    itens.append(dict(i, nome=f"{i['nome']} (arquivado)"))
        return itens

    def _linha(self, titulo, vazio, itens, selecionados):
        seletor = SeletorMultiplo(vazio, valign=Gtk.Align.CENTER)
        seletor.set_itens(itens, selecionados)
        linha = Adw.ActionRow(title=titulo)
        linha.add_suffix(seletor)
        linha.set_activatable_widget(seletor)
        if titulo == "Clientes":
            self._linha_cli = linha
        else:
            self._linha_ati = linha
        return seletor
```

O laço que adiciona ao grupo vira `for w in (self.desc, self._linha_cli, self._linha_ati, self.ini, self.fim):`.

Em `_on_resp`, no ramo `salvar`, trocar o trecho de `if not self.atividades:` até `aid = ...` por:

```python
                cids = self.cli.get_selecionados()
                aids = self.ati.get_selecionados()
```

e usar `cids`/`aids` nos lugares de `cid`/`aid` (`entradas.iniciar(self.app.conn, cids, aids, ...)`, `campos = dict(descricao=..., cliente_id=cids, atividade_id=aids, inicio=ini)`, `entradas.criar_manual(self.app.conn, ini, fim, cids, aids, ...)`). A validação "escolha pelo menos uma atividade" vem de `tempo.entradas` e cai no mesmo `except ValueError`.

Em `app/tempo/janela/janela.py`, a linha 65 do diálogo de tarefa esquecida vira:

```python
            body=f"'{entradas.rotulo(e)}' está rodando desde {e['inicio'][11:16]} de {e['inicio'][8:10]}/{e['inicio'][5:7]}. O que fazer?",
```

(garanta `from tempo import entradas` no topo; remova o import de `SEM_CLIENTE` se ficar sem uso.)

- [ ] **Step 6: rodar smokes e testes**

Run:
```bash
cd ~/tempo && timeout 90 env GTK_A11Y=none dbus-run-session -- python3 app/tests/smoke_janela.py && \
timeout 90 env GTK_A11Y=none dbus-run-session -- python3 app/tests/smoke_gargalos.py && \
timeout 90 env GTK_A11Y=none dbus-run-session -- python3 app/tests/smoke_cadastros.py && cd app && python3 -m pytest -q
```
Expected: os três smokes terminam sem AssertionError e pytest PASS. O smoke antigo tem `assert d.clientes[d.cli.get_selected()]["id"] == cid`: trocar por `assert d.cli.get_selecionados() == [cid]`.

- [ ] **Step 7: commit**

```bash
cd ~/tempo && git add app/tempo/janela/seletor.py app/tempo/janela/hoje.py app/tempo/janela/janela.py app/tests/smoke_janela.py && git commit -m "App: seletores múltiplos de cliente e atividade no cartão e no diálogo"
```

---

### Task 7: extensão do Shell com marcação múltipla

**Files:**
- Modify: `extensao/extension.js` (classe `Indicador`: `_montarMenu`, `_nomeSel`, `_rotuloSub`, `_atualizarTrocar`, `_padrao`, `_preencher`, `_preencherRecentes`, `_iniciarOuParar`, `_trocarTarefa`, `_aplicar`, `_atualizarRotulo`)
- Test: `app/tests/teste_extensao_headless.sh` (já existe; passa a chamar `IniciarVarios`)

**Interfaces:**
- Consumes: D-Bus `IniciarVarios(ai, ai, s)`; JSON com `cliente_ids`, `atividade_ids`, `clientes`, `atividades`.
- Produces: estado `this._clientesSel` e `this._atividadesSel` (arrays de ids, na ordem das listas).

- [ ] **Step 1: trocar o teste headless pra usar o método novo**

Em `app/tests/teste_extensao_headless.sh`, a linha `$S.Iniciar 0 2 "segunda"` vira:

```bash
$S.IniciarVarios "[]" "[1, 2]" "segunda" >/dev/null; echo "$(date +%T) iniciou 2" >> "$T/passos.log"; sleep 4
```

Rodar agora (`bash app/tests/teste_extensao_headless.sh`) deve falhar só se o serviço instalado for o antigo; se passar, siga (o teste cobre criação do cartão sem erro de JS, não a marcação).

- [ ] **Step 2: estado em listas**

No construtor de `Indicador`, trocar `this._clienteSel = null; this._atividadeSel = null;` por `this._clientesSel = []; this._atividadesSel = [];`.

Substituir `_nomeSel`, `_rotuloSub`, `_atualizarTrocar`, `_padrao`, `_preencher` por:

```js
    // Rótulo curto da seleção: '(nenhum)', 'Pessoal' ou 'Pessoal +1'. Sem cliente marcado: 'Sem cliente'.
    _rotuloSel(tipo) {
        const itens = tipo === 'cliente' ? this._clientes : this._atividades;
        const ids = tipo === 'cliente' ? this._clientesSel : this._atividadesSel;
        const nomes = itens.filter(i => ids.includes(i.id)).map(i => i.nome);
        if (nomes.length === 0) return tipo === 'cliente' ? SEM_CLIENTE : '(nenhuma)';
        return nomes.length === 1 ? nomes[0] : `${nomes[0]} +${nomes.length - 1}`;
    }

    _rotuloSub(sub, tipo) {
        sub.label.text = `${tipo === 'cliente' ? 'Cliente' : 'Atividade'}: ${this._rotuloSel(tipo)}`;
        this._atualizarTrocar();
    }

    _atualizarTrocar() {
        this._trocar.visible = this._entrada != null;
        this._trocar.label.text = `Trocar para ${this._rotuloSel('cliente')} · ${this._rotuloSel('atividade')}`;
    }

    // Padrão quando nada está marcado: a última combinação usada (recentes), senão a primeira atividade.
    _padrao(tipo) {
        const r = this._recentesLista?.[0];
        if (r) return tipo === 'cliente' ? [...r.cliente_ids] : [...r.atividade_ids];
        if (tipo === 'atividade' && this._atividades[0]) return [this._atividades[0].id];
        return [];
    }

    _preencher(sub, itens, tipo) {
        if (this._destruido) return;
        sub.menu.removeAll();
        const validos = new Set(itens.map(i => i.id));
        let sel = (tipo === 'cliente' ? this._clientesSel : this._atividadesSel).filter(id => validos.has(id));
        if (sel.length === 0 && this._recentesLista !== null) sel = this._padrao(tipo).filter(id => validos.has(id));
        if (tipo === 'cliente') this._clientesSel = sel; else this._atividadesSel = sel;
        this._rotuloSub(sub, tipo);
        for (const it of itens) {
            const item = new PopupMenu.PopupMenuItem(it.nome);
            item.setOrnament(sel.includes(it.id) ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
            item.connect('activate', () => {
                const atual = tipo === 'cliente' ? this._clientesSel : this._atividadesSel;
                // marca/desmarca; a ordem dos marcados segue a ordem da lista (o primeiro é o principal)
                const novo = atual.includes(it.id) ? atual.filter(id => id !== it.id) : [...atual, it.id];
                const ordenado = itens.map(i => i.id).filter(id => novo.includes(id));
                if (tipo === 'cliente') this._clientesSel = ordenado; else this._atividadesSel = ordenado;
                item.setOrnament(ordenado.includes(it.id) ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
                this._rotuloSub(sub, tipo);
            });
            sub.menu.addMenuItem(item);
        }
    }
```

Em `_recarregar`, a linha `this._clientes = [{id: 0, nome: SEM_CLIENTE}, ...JSON.parse(r[0])];` vira `this._clientes = JSON.parse(r[0]);` (sem cliente agora é "nada marcado").

O menu precisa ficar aberto ao marcar: um `PopupMenuItem` comum emite `activate`, e o `PopupMenuBase` fecha a árvore inteira nesse sinal. Então os itens dos submenus são de uma classe própria que, ao ser ativada, emite um sinal próprio em vez de `activate`. Colocar no topo do arquivo, antes de `Cartao`:

```js
// Item de submenu que marca/desmarca sem fechar o menu (o activate padrão fecharia a árvore inteira).
const ItemMarcavel = GObject.registerClass({
    Signals: {'marcou': {}},
}, class ItemMarcavel extends PopupMenu.PopupMenuItem {
    activate(_event) {
        this.emit('marcou');
    }
});
```

No `_preencher` acima, trocar `new PopupMenu.PopupMenuItem(it.nome)` por `new ItemMarcavel(it.nome)` e `item.connect('activate', ...)` por `item.connect('marcou', ...)`. Garanta `import GObject from 'gi://GObject';` no topo (já deve existir por causa do `registerClass` das outras classes).

- [ ] **Step 3: recentes, iniciar, trocar, aplicar, rótulo da barra**

`_preencherRecentes` vira:

```js
    _preencherRecentes(lista) {
        if (this._destruido) return;
        this._recentesLista = lista;
        this._recentes.removeAll();
        for (const r of lista) {
            const item = new PopupMenu.PopupMenuItem(`${r.cliente || SEM_CLIENTE} · ${r.atividade}`);
            item.connect('activate', () => this._proxy?.IniciarVariosRemote(r.cliente_ids, r.atividade_ids, '', () => {}));
            this._recentes.addMenuItem(item);
        }
        if (this._atividadesSel.length === 0 && lista.length > 0) {
            this._clientesSel = [...lista[0].cliente_ids];
            this._atividadesSel = [...lista[0].atividade_ids];
        }
        if (this._atividadesSel.length === 0 && this._atividades[0]) this._atividadesSel = [this._atividades[0].id];
        this._rotuloSub(this._subCli, 'cliente');
        this._rotuloSub(this._subAti, 'atividade');
    }
```

`_iniciarOuParar` e `_trocarTarefa`:

```js
    _iniciarOuParar() {
        if (!this._proxy) return;
        if (this._entrada) {
            this._proxy.PararRemote(() => {});
        } else {
            this._trocarTarefa();
        }
    }

    // Inicia a combinação marcada (com timer rodando, o serviço fecha a anterior sem intervalo).
    _trocarTarefa() {
        if (!this._proxy) return;
        if (this._atividadesSel.length === 0) {
            Main.notify('Tempo', 'Marque pelo menos uma atividade antes de iniciar.');
            return;
        }
        this._proxy.IniciarVariosRemote(this._clientesSel, this._atividadesSel, this._desc.get_text(), (_r, e) => {
            if (!this._destruido && !e) this._desc.set_text('');
        });
    }
```

Em `_aplicar`, as duas linhas `this._clienteSel = ...; this._atividadeSel = ...;` viram:

```js
            this._clientesSel = [...(this._entrada.cliente_ids ?? [])];
            this._atividadesSel = [...(this._entrada.atividade_ids ?? [])];
```

Em `_atualizarRotulo`, a linha do texto vira:

```js
        const nomes = (this._entrada.clientes?.length ? this._entrada.clientes : this._entrada.atividades ?? []).map(i => i.nome);
        const quem = nomes.length > 1 ? `${nomes[0]} +${nomes.length - 1}` : (nomes[0] ?? '');
        this._rotulo.text = `▶ ${fmtDuracao(seg)} · ${quem}${aviso}`;
```

Em `Cartao.mostrar(entrada)` (se a legenda do cartão usa `entrada.cliente`/`entrada.atividade`), trocar pelo mesmo critério: `${(entrada.clientes?.map(c => c.nome).join(' + ')) || SEM_CLIENTE} · ${(entrada.atividades?.map(a => a.nome).join(' + ')) || ''}`.

- [ ] **Step 4: verificar sintaxe, instalar e rodar o headless**

```bash
cd ~/tempo && node --check extensao/extension.js 2>/dev/null || gjs -m -c "import('./extensao/extension.js').catch(e => { print(e); })" 2>&1 | head -5
./instalar.sh > /dev/null && bash app/tests/teste_extensao_headless.sh
```
Expected: sem erro de sintaxe; headless "ok (cartão apareceu 2 vezes)". O `instalar.sh` avisa que o serviço antigo continua rodando: **não** reinicie o serviço real nesta tarefa (o controlador faz no fim).

Limite declarado: a marcação no submenu e o fechamento do menu só se confirmam com o oguim relogando (o Shell não recarrega código de extensão ao vivo). Registrar no relatório.

- [ ] **Step 5: commit**

```bash
cd ~/tempo && git add extensao/extension.js app/tests/teste_extensao_headless.sh && git commit -m "Extensão: marcação múltipla de clientes e atividades, IniciarVarios"
```

---

### Task 8: documentação

**Files:**
- Modify: `README.md`, `docs/roteiro-manual.md`

- [ ] **Step 1: README**

Na lista de funcionalidades do app e da extensão, acrescentar (sem travessão):

```
- Uma entrada pode ter vários clientes e várias atividades (vibecoding + edição + roteiro,
  pessoal + NP Hub). Nos Gargalos e no resumo do Telegram cada um recebe o tempo inteiro, e a
  linha "Combinado" mostra quanto rodou em modo múltiplo. O primeiro marcado é o principal.
```

Nas instruções do menu da barra, trocar a frase dos seletores por: "seletores **Cliente** e **Atividade** com marcação múltipla (clicar marca e desmarca, o menu fica aberto)".

- [ ] **Step 2: roteiro manual**

Acrescentar um passo depois do 3b:

```
3c. **Vários ao mesmo tempo.** No menu da barra, abra Cliente, marque dois clientes (o menu
    deve continuar aberto), marque duas atividades e clique Iniciar.
    - Esperado: a barra mostra `▶ 00:0x · Pessoal +1`; na aba Hoje a linha mostra
      "Pessoal + NP Hub · Edição + Roteiro"; em Gargalos, "Combinado: ..." nas leituras e cada
      cliente com o tempo inteiro.
    - Clique no botão de clientes do cartão da aba Hoje: abre a lista de caixas; desmarque tudo
      e o rótulo volta a "Sem cliente".
```

- [ ] **Step 3: commit**

```bash
cd ~/tempo && git add README.md docs/roteiro-manual.md && git commit -m "Docs: vários clientes e atividades por entrada"
```

---

## Auto-revisão

- Spec → tarefas: modelo de dados (T1, T2), rótulos (T2), gargalos + Combinado (T3), resumo e CSV (T4), D-Bus (T5), app GTK (T6), extensão (T7), docs (T8). Entradas antigas: backfill em T1.
- Nomes cruzados: `rotulo`, `rotulo_clientes`, `rotulo_atividades`, `combinados`, `IniciarVarios`, `SeletorMultiplo.set_itens/get_selecionados/set_selecionados/"mudou"`, `cliente_ids/atividade_ids`, `clientes/atividades` são os mesmos em todas as tarefas.
- Risco conhecido: `editar` passa a exigir atividade mesmo quando só muda o `fim` (lê a entrada antes). O `esquecida.resolver(modo="inicio")` chama `editar(fim=...)` numa entrada que sempre tem atividade: ok.
