"""Resumo do dia em texto puro, pra mandar no Telegram às 18h. Zero IA: só o banco e contas."""
import sys
from collections import Counter
from datetime import date, timedelta

from tempo import banco, entradas, gargalos

DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _lista(grupos):
    return " · ".join(f"{nome} {gargalos.fmt_h(mins)}" for nome, mins, _cor in grupos)


def _fragmentado(dia):
    """Atividade com mais blocos no dia, se teve pelo menos 2."""
    blocos = Counter(e["atividade"] or "Sem atividade" for e in dia)
    if not blocos:
        return None
    nome, n = blocos.most_common(1)[0]
    if n < 2:
        return None
    mins = sum(e["minutos"] for e in dia if (e["atividade"] or "Sem atividade") == nome)
    return f"Mais fragmentado: {nome}, {n} blocos ({gargalos.fmt_h(mins)})"


def _semana(conn, hoje):
    de, ate = gargalos.periodo("esta_semana", hoje)
    atual = entradas.no_periodo(conn, de, ate)
    anterior = entradas.no_periodo(conn, *gargalos.periodo_anterior(de, ate))
    total = gargalos.total_minutos(atual)
    if total == 0:
        return None
    partes = [f"Semana: {gargalos.fmt_h(total)}"]
    por_cliente = gargalos.por_cliente(atual)
    if por_cliente:
        nome, mins, _ = por_cliente[0]
        partes.append(f"{nome} levou mais tempo ({gargalos.fmt_h(mins)})")
    delta = total - gargalos.total_minutos(anterior)
    if delta == 0:
        partes.append("igual à semana passada")
    else:
        partes.append(f"{'+' if delta > 0 else '-'}{gargalos.fmt_h(abs(delta))} que a semana passada")
    return ", ".join(partes)


def texto(conn, hoje=None, agora=None):
    """Texto do resumo, ou None quando não há o que mandar (fim de semana, dia sem registro)."""
    hoje = hoje or date.today()
    if hoje.weekday() >= 5:
        return None
    dia = entradas.do_dia(conn, hoje, agora)
    if not dia:
        return None
    linhas = [
        f"Tempo de hoje ({DIAS[hoje.weekday()]} {hoje:%d/%m}): {gargalos.fmt_h(gargalos.total_minutos(dia))}",
        _lista(gargalos.por_cliente(dia)),
        _lista(gargalos.por_atividade(dia)),
    ]
    frag = _fragmentado(dia)
    if frag:
        linhas.append(frag)
    if hoje.weekday() == 4:
        semana = _semana(conn, hoje)
        if semana:
            linhas.append(semana)
    aberta = next((e for e in dia if e["fim"] is None), None)
    if aberta:
        linhas.append(f"Ainda rodando: {aberta['cliente'] or 'Sem cliente'} · {aberta['atividade']} "
                      f"desde {aberta['inicio'][11:16]} (não esquece de parar)")
    return "\n".join(linhas)


def main():
    from tempo.app import pasta_dados
    conn = banco.abrir(str(pasta_dados() / "tempo.db"))
    t = texto(conn)
    if t:
        print(t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
