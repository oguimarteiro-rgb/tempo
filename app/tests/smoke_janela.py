"""Fumaça da janela (sem apresentar). Rodar: dbus-run-session -- python3 app/tests/smoke_janela.py"""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["TEMPO_DIR"] = tempfile.mkdtemp(prefix="tempo-smoke-")

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from tempo import banco, cadastros, entradas, servico
from tempo.app import App
from tempo.janela.hoje import DialogoEntrada, PaginaHoje
from tempo.janela.janela import Janela

c = banco.abrir(os.environ["TEMPO_DIR"] + "/tempo.db")
cid = cadastros.criar(c, "clientes", "Casttema", "#e01b24")
aid = next(a["id"] for a in cadastros.listar(c, "atividades") if a["nome"] == "Edição")
t = datetime.now().astimezone().replace(hour=9, minute=0, second=0, microsecond=0)
entradas.criar_manual(c, t, t + timedelta(hours=2), cid, aid, "reel 07")

Adw.init()
app = App()
assert app.register(None)  # emite startup (abre o banco de TEMPO_DIR) e registra o serviço no barramento
c = app.conn
avisos = []
app.servico.emitir = lambda s: avisos.append(s)

jan = Janela(app)
pag = jan.paginas["hoje"]
assert isinstance(pag, PaginaHoje)
assert set(jan.paginas) == {"hoje", "gargalos", "cadastros"}
jan.atualizar()


def linhas():
    out, w = [], pag.lista.get_first_child()
    while w is not None:
        out.append(w)
        w = w.get_next_sibling()
    return out


def sufixo(row):
    # o Label de sufixo é o único Gtk.Label descendente com "–"
    achados = []
    def varrer(w):
        f = w.get_first_child()
        while f is not None:
            if isinstance(f, Gtk.Label) and "–" in f.get_text():
                achados.append(f.get_text())
            varrer(f)
            f = f.get_next_sibling()
    varrer(row)
    return achados[0]


rs = linhas()
assert len(rs) == 1 and isinstance(rs[0], Adw.ActionRow), rs
assert rs[0].get_title() == "Casttema · Edição", rs[0].get_title()
assert rs[0].get_subtitle() == "reel 07"
s = sufixo(rs[0])
assert "09:00–11:00" in s and "2h" in s, s
assert pag.total.get_text() == "Total do dia: 2h", pag.total.get_text()

ent = entradas.do_dia(c, t.date())[0]
d = DialogoEntrada(jan, app, ent, jan.atualizar)
assert d.ini.get_text() == "09:00" and d.fim.get_text() == "11:00"
assert d.clientes[d.cli.get_selected()]["id"] == cid
d.fim.set_text("12:00")
d._on_resp(None, "salvar")
assert entradas.do_dia(c, t.date())[0]["minutos"] == 180
assert pag.total.get_text() == "Total do dia: 3h", pag.total.get_text()
assert avisos, "notificar() não emitiu sinal"

# validação: fim antes do início vira toast, sem alterar
d2 = DialogoEntrada(jan, app, entradas.do_dia(c, t.date())[0], jan.atualizar)
d2.fim.set_text("08:00")
d2._on_resp(None, "salvar")
assert entradas.do_dia(c, t.date())[0]["minutos"] == 180

# entrada manual
d3 = DialogoEntrada(jan, app, None, jan.atualizar)
d3.ini.set_text("13:00"); d3.fim.set_text("14:30"); d3.desc.set_text("manual")
d3._on_resp(None, "salvar")
assert len(linhas()) == 2 and pag.total.get_text() == "Total do dia: 4h30", pag.total.get_text()

# apagar
d4 = DialogoEntrada(jan, app, entradas.do_dia(c, t.date())[1], jan.atualizar)
d4._on_resp(None, "apagar")
assert len(linhas()) == 1

# esquecida: sem entrada aberta, não abre diálogo
jan.checar_esquecida()
print("SMOKE OK")
