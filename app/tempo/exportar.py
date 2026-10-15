import csv
import io

CABECALHO = ["inicio", "fim", "duracao_min", "cliente", "atividade", "descricao"]


def csv_texto(entradas):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CABECALHO)
    for e in entradas:
        w.writerow([e["inicio"], e["fim"] or "", e["minutos"],
                    " + ".join(c["nome"] for c in e["clientes"]),
                    " + ".join(a["nome"] for a in e["atividades"]), e["descricao"]])
    return buf.getvalue()
