"""Fumaça da aba Cadastros. Rodar: timeout 90 env GTK_A11Y=none dbus-run-session -- python3 app/tests/smoke_cadastros.py [caminho.png]"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["TEMPO_DIR"] = tempfile.mkdtemp(prefix="tempo-smoke-")

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gdk, Gtk

from tempo import banco, cadastros
from tempo.app import App
from tempo.janela.cadastros_view import PaginaCadastros
from tempo.janela.janela import Janela

c = banco.abrir(os.environ["TEMPO_DIR"] + "/tempo.db")
cadastros.criar(c, "clientes", "Casttema", "#e01b24")
hid = cadastros.criar(c, "clientes", "Hornero", "#26a269")
vid = cadastros.criar(c, "clientes", "Antigo", "#9141ac")
cadastros.arquivar(c, "clientes", vid, True)
c.close()

Adw.init()
app = App()
assert app.register(None)
c = app.conn
chamadas = []
app.servico.notificar = lambda: chamadas.append(1)

jan = Janela(app)
pag = jan.paginas["cadastros"]
assert isinstance(pag, PaginaCadastros)
toasts = []
jan.toast = lambda texto: toasts.append(texto)


def linhas(tabela):
    return list(pag.grupos[tabela][1])


def por_titulo(tabela, titulo):
    return next(r for r in linhas(tabela) if r.get_title() == titulo)


def descendentes(w, tipo, out=None):
    out = [] if out is None else out
    f = w.get_first_child()
    while f is not None:
        if isinstance(f, tipo):
            out.append(f)
        descendentes(f, tipo, out)
        f = f.get_next_sibling()
    return out


pag.atualizar()
assert len(linhas("clientes")) == 3, len(linhas("clientes"))
assert len(linhas("atividades")) == 7, len(linhas("atividades"))
assert por_titulo("clientes", "Antigo").has_css_class("dim-label")
assert not por_titulo("clientes", "Casttema").has_css_class("dim-label")
assert all(isinstance(r, Adw.ActionRow) for t in pag.grupos for r in linhas(t))

# diálogo: captura o AlertDialog sem apresentar e dispara o handler de resposta
apresentados = []
Adw.AlertDialog.present = lambda self, pai=None: apresentados.append(self)


def dialogo(tabela, item, texto, resp="salvar"):
    apresentados.clear()
    pag._dialogo_nome(tabela, item)
    d = apresentados[0]
    entry = descendentes(d.get_extra_child(), Adw.EntryRow)[0]
    entry.set_text(texto)
    d.emit("response", resp)
    return d


n = len(chamadas)
dialogo("clientes", None, "  Viretto ")
assert any(i["nome"] == "Viretto" for i in cadastros.listar(c, "clientes")), "cliente não criado"
assert len(linhas("clientes")) == 4
assert len(chamadas) == n + 1 and not toasts

dialogo("clientes", None, "Viretto")  # duplicado
assert len(toasts) == 1 and toasts[0].startswith("Não salvou: "), toasts
assert len(linhas("clientes")) == 4
dialogo("clientes", None, "   ")  # vazio
assert toasts[-1] == "Não salvou: nome vazio", toasts
dialogo("clientes", None, "Cancelado", resp="cancelar")
assert not any(i["nome"] == "Cancelado" for i in cadastros.listar(c, "clientes"))

# renomear
item = next(i for i in cadastros.listar(c, "clientes") if i["nome"] == "Hornero")
dialogo("clientes", item, "Hornero Cerâmica")
assert por_titulo("clientes", "Hornero Cerâmica")
assert not any(r.get_title() == "Hornero" for r in linhas("clientes"))
assert any(i["nome"] == "Hornero Cerâmica" for i in cadastros.listar(c, "clientes"))

# cor: muda no botão da linha e persiste o hex
row = por_titulo("clientes", "Casttema")
btn = descendentes(row, Gtk.ColorDialogButton)[0]
rgba = Gdk.RGBA()
rgba.parse("#33d17a")
n = len(chamadas)
btn.set_rgba(rgba)
cid = next(i["id"] for i in cadastros.listar(c, "clientes") if i["nome"] == "Casttema")
cor = next(i["cor"] for i in cadastros.listar(c, "clientes") if i["id"] == cid)
assert cor == "#33d17a", cor
assert len(chamadas) == n + 1

# arquivar pelo switch: persiste e a linha fica cinza
row = por_titulo("clientes", "Casttema")
sw = descendentes(row, Gtk.Switch)[0]
assert sw.get_active()
n = len(chamadas)
sw.set_active(False)
assert next(i for i in cadastros.listar(c, "clientes", incluir_arquivados=True) if i["id"] == cid)["arquivado"]
assert por_titulo("clientes", "Casttema").has_css_class("dim-label")
assert len(chamadas) == n + 1
# e volta a ativo
sw = descendentes(por_titulo("clientes", "Casttema"), Gtk.Switch)[0]
assert not sw.get_active()
sw.set_active(True)
assert not por_titulo("clientes", "Casttema").has_css_class("dim-label")
assert not next(i for i in cadastros.listar(c, "clientes", incluir_arquivados=True) if i["id"] == cid)["arquivado"]

# atividades: arquivadas somem da listagem padrão do combo (Hoje), mas seguem na aba
aid = cadastros.listar(c, "atividades")[0]["id"]
pag._arquivar("atividades", aid, True)
assert len(linhas("atividades")) == 7
assert len(cadastros.listar(c, "atividades")) == 6
print("SMOKE OK")

# captura opcional
if len(sys.argv) > 1:
    pag._arquivar("clientes", vid, True)
    jan.stack.set_visible_child_name("cadastros")
    jan.set_default_size(900, 700)
    jan.present()
    loop = GLib.MainLoop()

    def salvar():
        pag.atualizar()
        GLib.timeout_add(500, tirar)
        return False

    def tirar():
        pt = Gtk.WidgetPaintable.new(jan)
        snap = Gtk.Snapshot()
        pt.snapshot(snap, jan.get_width(), jan.get_height())
        tex = jan.get_native().get_renderer().render_texture(snap.to_node(), None)
        tex.save_to_png(sys.argv[1])
        print("PNG salvo em", sys.argv[1])
        loop.quit()
        return False

    GLib.timeout_add(1000, salvar)
    GLib.timeout_add(8000, loop.quit)
    loop.run()
