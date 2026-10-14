from datetime import date

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from tempo import entradas, exportar, gargalos
from tempo.janela.grafico import Barras

OPCOES = [("esta_semana", "Esta semana"), ("semana_passada", "Semana passada"),
          ("este_mes", "Este mês"), ("personalizado", "Personalizado")]


class PaginaGargalos(Gtk.Box):
    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12,
                         margin_start=12, margin_end=12)
        self.app = app
        topo = Gtk.Box(spacing=6)
        self.drop = Gtk.DropDown.new_from_strings([t for _, t in OPCOES])
        self.drop.connect("notify::selected", lambda *_: self.atualizar())
        self.de = Gtk.Entry(placeholder_text="AAAA-MM-DD", width_chars=11, visible=False)
        self.ate = Gtk.Entry(placeholder_text="AAAA-MM-DD", width_chars=11, visible=False)
        for e in (self.de, self.ate):
            e.connect("activate", lambda *_: self.atualizar())
        btn = Gtk.Button(label="Exportar CSV")
        btn.connect("clicked", self._exportar)
        for w in (self.drop, self.de, self.ate):
            topo.append(w)
        topo.append(Gtk.Box(hexpand=True))
        topo.append(btn)
        self.append(topo)

        graficos = Gtk.Box(spacing=18, homogeneous=True)
        self.g_cliente, self.g_atividade, self.g_dia = Barras("Por cliente"), Barras("Por atividade"), Barras("Por dia da semana")
        for g in (self.g_cliente, self.g_atividade, self.g_dia):
            graficos.append(g)
        self.append(graficos)

        self.leituras = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.append(Gtk.Label(label="Leituras", xalign=0, css_classes=["heading"]))
        self.append(self.leituras)
        self.append(Gtk.Box(vexpand=True))
        self._periodo = (date.today(), date.today())

    def _periodo_escolhido(self):
        nome = OPCOES[self.drop.get_selected()][0]
        personalizado = nome == "personalizado"
        self.de.set_visible(personalizado)
        self.ate.set_visible(personalizado)
        hoje = date.today()
        if personalizado:
            try:
                return gargalos.periodo(nome, hoje, date.fromisoformat(self.de.get_text()), date.fromisoformat(self.ate.get_text()))
            except ValueError:
                return hoje, hoje
        return gargalos.periodo(nome, hoje)

    def atualizar(self):
        de, ate = self._periodo_escolhido()
        self._periodo = (de, ate)
        atual = entradas.no_periodo(self.app.conn, de, ate)
        anterior = entradas.no_periodo(self.app.conn, *gargalos.periodo_anterior(de, ate))
        self.g_cliente.set_dados(gargalos.por_cliente(atual))
        self.g_atividade.set_dados(gargalos.por_atividade(atual))
        self.g_dia.set_dados(gargalos.por_dia_semana(atual))
        while (f := self.leituras.get_first_child()) is not None:
            self.leituras.remove(f)
        frases = gargalos.leituras(atual, anterior) or ["Nada registrado neste período."]
        for frase in frases:
            self.leituras.append(Gtk.Label(label=f"• {frase}", xalign=0, wrap=True))

    def _exportar(self, *_):
        de, ate = self._periodo
        dialogo = Gtk.FileDialog(initial_name=f"tempo-{de}-{ate}.csv")

        def pronto(d, res):
            try:
                arq = d.save_finish(res)
            except GLib.Error:
                return
            texto = exportar.csv_texto(entradas.no_periodo(self.app.conn, de, ate))
            try:
                arq.replace_contents(texto.encode(), None, False, Gio.FileCreateFlags.REPLACE_DESTINATION, None)
            except GLib.Error as e:
                self.get_root().toast(f"Não foi possível exportar: {e.message}")
                return
            self.get_root().toast(f"Exportado para {arq.get_basename()}")
        dialogo.save(self.get_root(), None, pronto)
