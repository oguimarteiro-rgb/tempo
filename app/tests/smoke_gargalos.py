"""Fumaça da aba Gargalos. Rodar: timeout 90 env GTK_A11Y=none dbus-run-session -- python3 app/tests/smoke_gargalos.py [caminho.png [claro|escuro]]"""
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["TEMPO_DIR"] = tempfile.mkdtemp(prefix="tempo-smoke-")
os.environ["TEMPO_RUNTIME_DIR"] = os.environ["TEMPO_DIR"]  # não toca o tempo-sessao da sessão real

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from tempo import banco, cadastros, entradas, exportar, gargalos
from tempo.app import App
from tempo.janela.gargalos_view import OPCOES, PaginaGargalos
from tempo.janela.grafico import Barras
from tempo.janela.janela import Janela

c = banco.abrir(os.environ["TEMPO_DIR"] + "/tempo.db")
cas = cadastros.criar(c, "clientes", "Casttema", "#e01b24")
hor = cadastros.criar(c, "clientes", "Hornero", "#33d17a")
ativ = {a["nome"]: a["id"] for a in cadastros.listar(c, "atividades")}
edic, outra = ativ["Edição"], next(i for n, i in ativ.items() if n != "Edição")
hoje = date.today()
seg = hoje - timedelta(days=hoje.weekday())


def semear(dia, h, dur, cid, aid, desc=""):
    t = datetime.combine(dia, datetime.min.time()).astimezone().replace(hour=h)
    entradas.criar_manual(c, t, t + timedelta(minutes=dur), cid, aid, desc)


semear(seg, 9, 120, cas, edic, "a")
semear(seg + timedelta(days=1), 10, 90, hor, outra, "b")
semear(seg + timedelta(days=2), 14, 60, cas, edic, "c")
semear(seg - timedelta(days=5), 9, 240, hor, edic, "semana passada")   # semana passada
semear(seg - timedelta(days=4), 9, 30, cas, outra, "semana passada 2")

Adw.init()
app = App()
assert app.register(None)
jan = Janela(app)
pag = jan.paginas["gargalos"]
assert isinstance(pag, PaginaGargalos)


def rotulos():
    out, w = [], pag.leituras.get_first_child()
    while w is not None:
        out.append(w.get_label())
        w = w.get_next_sibling()
    return out


def esperado(nome):
    de, ate = gargalos.periodo(nome, hoje)
    atual = entradas.no_periodo(app.conn, de, ate)
    ant = entradas.no_periodo(app.conn, *gargalos.periodo_anterior(de, ate))
    return de, ate, atual, gargalos.leituras(atual, ant)


def confere(nome):
    de, ate, atual, frases = esperado(nome)
    assert pag.g_cliente.dados == gargalos.por_cliente(atual), (nome, pag.g_cliente.dados)
    assert pag.g_atividade.dados == gargalos.por_atividade(atual)
    assert pag.g_dia.dados == gargalos.por_dia_semana(atual)
    assert rotulos() == ([f"• {f}" for f in frases] or ["• Nada registrado neste período."]), rotulos()
    assert pag._periodo == (de, ate)
    return atual, frases


assert all(isinstance(g, Barras) for g in (pag.g_cliente, pag.g_atividade, pag.g_dia))
assert not pag.de.get_visible() and not pag.ate.get_visible()

pag.drop.set_selected(0)  # Esta semana
pag.atualizar()
atual, frases = confere("esta_semana")
assert len(atual) == 3 and frases, (atual, frases)
assert pag.g_cliente.dados[0][0] == "Casttema" and pag.g_cliente.dados[0][1] == 180 and pag.g_cliente.dados[0][2] == "#e01b24"
dados_semana = list(pag.g_cliente.dados)
assert len(pag.g_dia.dados) == 7
print("leituras (esta semana):", frases)

pag.drop.set_selected(1)  # Semana passada (o notify::selected já chama atualizar)
atual2, _ = confere("semana_passada")
assert len(atual2) == 2 and pag.g_cliente.dados != dados_semana

pag.drop.set_selected(2)  # Este mês
confere("este_mes")

pag.drop.set_selected(3)  # Personalizado
assert pag.de.get_visible() and pag.ate.get_visible()
pag.de.set_text(seg.isoformat()); pag.ate.set_text((seg + timedelta(days=6)).isoformat())
pag.atualizar()
assert pag._periodo == (seg, seg + timedelta(days=6))
assert pag.g_cliente.dados == dados_semana
pag.de.set_text("lixo"); pag.atualizar()
assert pag._periodo == (hoje, hoje)  # data inválida cai em hoje

# período vazio: lista vazia vira "Sem dados" e frase única
pag.de.set_text("2000-01-01"); pag.ate.set_text("2000-01-07"); pag.atualizar()
assert pag.g_cliente.dados == [] and pag.g_atividade.dados == []
assert rotulos() == ["• Nada registrado neste período."], rotulos()

# exportar: caminho real de _exportar com o FileDialog substituído por um falso
destino = Path(tempfile.mkdtemp(prefix="tempo-csv-")) / "saida.csv"
pag.drop.set_selected(0)
pag.atualizar()
toasts = []
jan.toast = lambda t: toasts.append(t)
nomes = []
class FakeRoot:  # a página ainda não está dentro de uma janela real neste ponto
    toast = staticmethod(lambda t: toasts.append(t))
Gtk.FileDialog.save = lambda self, pai, canc, cb: (nomes.append(self.get_initial_name()), cb(self, None))
Gtk.FileDialog.save_finish = lambda self, res: Gio.File.new_for_path(str(destino))
pag.get_root = lambda: FakeRoot
pag._exportar()
de, ate, atual, _ = esperado("esta_semana")
assert nomes == [f"tempo-{de}-{ate}.csv"], nomes
assert destino.read_text() == exportar.csv_texto(atual), destino.read_text()
assert len(destino.read_text().splitlines()) == 4  # cabeçalho + 3 entradas
assert toasts == ["Exportado para saida.csv"], toasts
# erro de escrita (pasta que não existe) vira toast, sem exceção
destino = Path(tempfile.mkdtemp(prefix="tempo-csv-")) / "nao-existe" / "saida.csv"
toasts.clear()
pag._exportar()
assert len(toasts) == 1 and toasts[0].startswith("Não foi possível exportar: "), toasts
assert not destino.exists()
print("SMOKE OK")

# captura opcional: apresenta a janela e salva PNG da aba
if len(sys.argv) > 1:
    del pag.get_root
    if len(sys.argv) > 2:  # 'claro' ou 'escuro': confere que o texto do gráfico segue o tema
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.FORCE_LIGHT if sys.argv[2] == "claro" else Adw.ColorScheme.FORCE_DARK)
    jan.stack.set_visible_child_name("gargalos")
    pag.drop.set_selected(0)
    jan.set_default_size(1000, 640)
    jan.present()
    loop = GLib.MainLoop()

    def capturar():
        pag.atualizar()
        GLib.timeout_add(500, salvar)
        return False

    def salvar():
        pt = Gtk.WidgetPaintable.new(jan)
        snap = Gtk.Snapshot()
        pt.snapshot(snap, jan.get_width(), jan.get_height())
        tex = jan.get_native().get_renderer().render_texture(snap.to_node(), None)
        tex.save_to_png(sys.argv[1])
        print("PNG salvo em", sys.argv[1])
        loop.quit()
        return False

    GLib.timeout_add(1000, capturar)
    GLib.timeout_add(8000, loop.quit)
    loop.run()
