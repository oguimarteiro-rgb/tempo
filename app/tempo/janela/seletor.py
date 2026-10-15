import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GObject, Gtk


class SeletorMultiplo(Gtk.MenuButton):
    """Botão que abre uma lista de caixas de marcação. Rótulo: 'Pessoal', 'Pessoal +1' ou o texto vazio."""

    __gsignals__ = {"mudou": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, vazio, **kw):
        super().__init__(**kw)
        self._vazio = vazio
        self._itens = []
        self._caixas = {}
        self._quieto = False
        self._lista = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=6, margin_bottom=6,
                              margin_start=6, margin_end=6)
        rolagem = Gtk.ScrolledWindow(child=self._lista, propagate_natural_height=True, propagate_natural_width=True,
                                     max_content_height=320, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.set_popover(Gtk.Popover(child=rolagem))
        self._rotular()

    def set_itens(self, itens, selecionados=()):
        """itens: [{"id", "nome"}] na ordem de exibição (a ordem dos marcados segue essa lista)."""
        while (f := self._lista.get_first_child()) is not None:
            self._lista.remove(f)
        self._itens, self._caixas = list(itens), {}
        self._quieto = True
        for it in self._itens:
            caixa = Gtk.CheckButton(label=it["nome"], active=it["id"] in selecionados)
            caixa.connect("toggled", lambda *_: self._mudou())
            self._caixas[it["id"]] = caixa
            self._lista.append(caixa)
        self._quieto = False
        self._rotular()

    def get_selecionados(self):
        return [it["id"] for it in self._itens if self._caixas[it["id"]].get_active()]

    def set_selecionados(self, ids):
        self._quieto = True
        for it in self._itens:
            self._caixas[it["id"]].set_active(it["id"] in ids)
        self._quieto = False
        self._mudou()

    def _mudou(self):
        if self._quieto:
            return
        self._rotular()
        self.emit("mudou")

    def _rotular(self):
        nomes = [it["nome"] for it in self._itens if self._caixas.get(it["id"]) and self._caixas[it["id"]].get_active()]
        if not nomes:
            self.set_label(self._vazio)
        elif len(nomes) == 1:
            self.set_label(nomes[0])
        else:
            self.set_label(f"{nomes[0]} +{len(nomes) - 1}")
