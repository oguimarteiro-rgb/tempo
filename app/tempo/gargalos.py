from collections import Counter, defaultdict
from datetime import date, timedelta, datetime

DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
DIAS_LONGO = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
COR_PADRAO = "#3584e4"
LIMIAR_CRESCIMENTO = 0.25


def total_minutos(entradas):
    return sum(e["minutos"] for e in entradas)


def fmt_h(minutos):
    h, m = divmod(int(minutos), 60)
    if h == 0:
        return f"{m}min"
    if m == 0:
        return f"{h}h"
    return f"{h}h{m:02d}"


def _agrupar(entradas, chave, cor_de):
    mins = defaultdict(int)
    cores = {}
    for e in entradas:
        k = e[chave] or "(sem)"
        mins[k] += e["minutos"]
        cores.setdefault(k, cor_de(e))
    return sorted(((k, v, cores[k]) for k, v in mins.items()), key=lambda x: -x[1])


def por_cliente(entradas):
    return _agrupar(entradas, "cliente", lambda e: e["cor"])


def por_atividade(entradas):
    return _agrupar(entradas, "atividade", lambda e: e.get("cor_atividade", COR_PADRAO))


def _dia_semana(e):
    return datetime.fromisoformat(e["inicio"]).weekday()


def por_dia_semana(entradas):
    mins = [0] * 7
    for e in entradas:
        mins[_dia_semana(e)] += e["minutos"]
    return [(DIAS[i], mins[i], COR_PADRAO) for i in range(7)]


def periodo(nome, hoje, de=None, ate=None):
    if nome == "esta_semana":
        ini = hoje - timedelta(days=hoje.weekday())
        return ini, ini + timedelta(days=6)
    if nome == "semana_passada":
        ini = hoje - timedelta(days=hoje.weekday() + 7)
        return ini, ini + timedelta(days=6)
    if nome == "este_mes":
        ini = hoje.replace(day=1)
        prox = (ini.replace(day=28) + timedelta(days=4)).replace(day=1)
        return ini, prox - timedelta(days=1)
    if nome == "personalizado":
        return de, ate
    raise ValueError(f"período inválido: {nome}")


def periodo_anterior(de, ate):
    tamanho = (ate - de).days + 1
    return de - timedelta(days=tamanho), de - timedelta(days=1)


def _leitura_crescimento(atual, anterior):
    if not anterior:
        return None
    a = {k: v for k, v, _ in por_atividade(atual)}
    b = {k: v for k, v, _ in por_atividade(anterior)}
    melhor = None
    for k, v in a.items():
        base = b.get(k, 0)
        if base == 0:
            continue
        cresc = (v - base) / base
        if cresc >= LIMIAR_CRESCIMENTO and (melhor is None or cresc > melhor[1]):
            melhor = (k, cresc)
    if not melhor:
        return None
    return f"{melhor[0]} subiu {round(melhor[1] * 100)}% em relação ao período anterior"


def _leitura_cliente(atual):
    clientes = por_cliente(atual)
    if not clientes:
        return None
    nome, mins, _ = clientes[0]
    do_cliente = [e for e in atual if (e["cliente"] or "(sem)") == nome]
    atividade = por_atividade(do_cliente)[0][0]
    return f"{nome}: {fmt_h(mins)}, maior parte em {atividade}"


def _leitura_fragmentacao(atual):
    por_dia = Counter(datetime.fromisoformat(e["inicio"]).date() for e in atual)
    if not por_dia:
        return None
    dia, trocas = por_dia.most_common(1)[0]
    if trocas < 4:
        return None
    return f"{DIAS_LONGO[dia.weekday()]} foi o dia mais fragmentado: {trocas} trocas de tarefa"


def _leitura_total(atual):
    if not atual:
        return None
    dias = len({datetime.fromisoformat(e["inicio"]).date() for e in atual})
    total = total_minutos(atual)
    return f"Total de {fmt_h(total)} em {dias} dias, média de {fmt_h(total // dias)} por dia"


def leituras(atual, anterior):
    frases = [
        _leitura_crescimento(atual, anterior),
        _leitura_cliente(atual),
        _leitura_fragmentacao(atual),
        _leitura_total(atual),
    ]
    return [f for f in frases if f]
