from tempo import entradas

LIMITE_MINUTOS = 12 * 60
MODOS = ("inicio", "agora", "descartar")


def detectar(conn, inicio_sessao):
    e = entradas.atual(conn)
    if e and entradas.parse(e["inicio"]) < inicio_sessao:
        return e
    return None


def resolver(conn, modo, agora=None):
    if modo not in MODOS:
        raise ValueError(f"modo inválido: {modo}")
    e = entradas.atual(conn)
    if not e:
        return
    if modo == "inicio":
        entradas.editar(conn, e["id"], fim=e["inicio"])
    elif modo == "agora":
        entradas.parar(conn, agora)
    else:
        entradas.apagar(conn, e["id"])


def passou_de_12h(entrada):
    return bool(entrada) and entrada["minutos"] >= LIMITE_MINUTOS
