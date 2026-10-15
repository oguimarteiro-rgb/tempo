import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from tempo import entradas, esquecida
from tempo.janela.cadastros_view import PaginaCadastros
from tempo.janela.gargalos_view import PaginaGargalos
from tempo.janela.hoje import PaginaHoje


CSS = ".cronometro { font-size: 2.6em; font-weight: 300; }"


def _instalar_css():
    tela = Gdk.Display.get_default()
    if tela is None or getattr(_instalar_css, "feito", False):
        return
    prov = Gtk.CssProvider()
    prov.load_from_string(CSS)
    Gtk.StyleContext.add_provider_for_display(tela, prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _instalar_css.feito = True


class Janela(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Tempo", default_width=760, default_height=560)
        self.app = app
        _instalar_css()
        self.stack = Adw.ViewStack()
        self.paginas = {}
        self._adicionar("hoje", "Hoje", "x-office-calendar-symbolic", PaginaHoje(app))
        self._adicionar("gargalos", "Gargalos", "view-list-bullet-symbolic", PaginaGargalos(app))
        self._adicionar("cadastros", "Cadastros", "x-office-address-book-symbolic", PaginaCadastros(app))

        switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header = Adw.HeaderBar(title_widget=switcher)
        self.toasts = Adw.ToastOverlay()
        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(self.stack)
        self.toasts.set_child(view)
        self.set_content(self.toasts)
        self.stack.connect("notify::visible-child", lambda *a: self.atualizar())

    def _adicionar(self, nome, titulo, icone, widget):
        page = self.stack.add_titled(widget, nome, titulo)
        page.set_icon_name(icone)
        self.paginas[nome] = widget

    def atualizar(self):
        w = self.stack.get_visible_child()
        if hasattr(w, "atualizar"):
            w.atualizar()

    def toast(self, texto):
        self.toasts.add_toast(Adw.Toast(title=texto))

    def checar_esquecida(self):
        e = esquecida.detectar(self.app.conn, self.app.servico.inicio_sessao)
        if not e:
            return
        d = Adw.AlertDialog(
            heading="Entrada ficou aberta",
            body=f"'{entradas.rotulo(e)}' está rodando desde {e['inicio'][11:16]} de {e['inicio'][8:10]}/{e['inicio'][5:7]}. O que fazer?",
        )
        d.add_response("inicio", "Encerrar no início")
        d.add_response("agora", "Encerrar agora")
        d.add_response("descartar", "Descartar")
        d.set_response_appearance("descartar", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_default_response("agora")

        def on_resp(_d, resp):
            if resp in esquecida.MODOS:
                esquecida.resolver(self.app.conn, resp, id=e["id"])
                self.app.servico.notificar()
                self.atualizar()
        d.connect("response", on_resp)
        d.present(self)
