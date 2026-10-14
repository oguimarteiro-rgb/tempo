import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

from tempo import gargalos

ALTURA_BARRA = 22
ESPACO = 8
LARGURA_ROTULO = 110
LARGURA_VALOR = 56


class Barras(Gtk.Box):
    def __init__(self, titulo):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.append(Gtk.Label(label=titulo, xalign=0, css_classes=["heading"]))
        self.area = Gtk.DrawingArea(hexpand=True)
        self.area.set_draw_func(self._desenhar)
        self.append(self.area)
        self.dados = []

    def set_dados(self, dados):
        self.dados = list(dados)
        self.area.set_content_height(max(1, len(self.dados)) * (ALTURA_BARRA + ESPACO))
        self.area.queue_draw()

    def _desenhar(self, area, cr, w, h):
        cor_texto = area.get_color()
        cr.set_source_rgba(cor_texto.red, cor_texto.green, cor_texto.blue, cor_texto.alpha)
        cr.set_font_size(13)
        if not self.dados:
            cr.move_to(0, 16)
            cr.show_text("Sem dados")
            return
        maximo = max(v for _, v, _ in self.dados) or 1
        largura_util = max(10, w - LARGURA_ROTULO - LARGURA_VALOR)
        for i, (nome, valor, cor) in enumerate(self.dados):
            y = i * (ALTURA_BARRA + ESPACO)
            cr.set_source_rgba(cor_texto.red, cor_texto.green, cor_texto.blue, cor_texto.alpha)
            cr.move_to(0, y + 16)
            cr.show_text(nome[:16])
            rgba = Gdk.RGBA()
            rgba.parse(cor)
            cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, 0.9)
            cr.rectangle(LARGURA_ROTULO, y + 3, largura_util * valor / maximo, ALTURA_BARRA - 6)
            cr.fill()
            cr.set_source_rgba(cor_texto.red, cor_texto.green, cor_texto.blue, cor_texto.alpha)
            cr.move_to(LARGURA_ROTULO + largura_util + 6, y + 16)
            cr.show_text(gargalos.fmt_h(valor))
