from tempo import entradas

LIMITE_MINUTOS = 12 * 60
MODOS = ("inicio", "agora", "descartar")


def detectar(conn, inicio_sessao):
    e = entradas.atual(conn)
    if e and entradas.parse(e["inicio"]) < inicio_sessao:
        return e
    return None


def resolver(conn, modo, agora=None, id=None):
    """Resolve a entrada esquecida. Com id, só age se essa entrada ainda estiver aberta:
    se outra começou entre a pergunta e a resposta, não mexe em nada."""
    if modo not in MODOS:
        raise ValueError(f"modo inválido: {modo}")
    e = entradas.atual(conn) if id is None else entradas.por_id(conn, id)
    if not e or e["fim"] is not None:
        return
    if modo == "inicio":
        entradas.editar(conn, e["id"], fim=e["inicio"])
    elif modo == "agora":
        entradas.parar(conn, agora)
    else:
        entradas.apagar(conn, e["id"])


def passou_de_12h(entrada):
    return bool(entrada) and entrada["minutos"] >= LIMITE_MINUTOS
