import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from tempo import cadastros


class PaginaCadastros(Gtk.Box):
    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=18, margin_top=12, margin_bottom=12,
                         margin_start=12, margin_end=12)
        self.app = app
        self.grupos = {}
        scroll = Gtk.ScrolledWindow(vexpand=True)
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        scroll.set_child(caixa)
        for tabela, titulo in (("clientes", "Clientes"), ("atividades", "Atividades")):
            grupo = Adw.PreferencesGroup(title=titulo)
            btn = Gtk.Button(icon_name="list-add-symbolic", css_classes=["flat"], tooltip_text=f"Novo em {titulo}")
            btn.connect("clicked", lambda _b, t=tabela: self._dialogo_nome(t, None))
            grupo.set_header_suffix(btn)
            caixa.append(grupo)
            self.grupos[tabela] = (grupo, [])
        self.append(scroll)

    def atualizar(self):
        for tabela, (grupo, linhas) in self.grupos.items():
            for l in linhas:
                grupo.remove(l)
            linhas.clear()
            for item in cadastros.listar(self.app.conn, tabela, incluir_arquivados=True):
                row = Adw.ActionRow(title=item["nome"], activatable=True)
                if item["arquivado"]:
                    row.add_css_class("dim-label")
                cor = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False), valign=Gtk.Align.CENTER)
                rgba = Gdk.RGBA()
                rgba.parse(item["cor"])
                cor.set_rgba(rgba)
                cor.connect("notify::rgba", lambda b, _p, t=tabela, i=item["id"]: self._trocar_cor(t, i, b.get_rgba()))
                row.add_prefix(cor)
                sw = Gtk.Switch(active=not item["arquivado"], valign=Gtk.Align.CENTER, tooltip_text="Ativo")
                sw.connect("state-set", lambda _s, ativo, t=tabela, i=item["id"]: self._arquivar(t, i, not ativo))
                row.add_suffix(sw)
                row.connect("activated", lambda _r, t=tabela, it=item: self._dialogo_nome(t, it))
                grupo.add(row)
                linhas.append(row)

    def _hex(self, rgba):
        return "#%02x%02x%02x" % (round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255))

    def _trocar_cor(self, tabela, id, rgba):
        cadastros.trocar_cor(self.app.conn, tabela, id, self._hex(rgba))
        self.app.servico.notificar()

    def _arquivar(self, tabela, id, arquivado):
        cadastros.arquivar(self.app.conn, tabela, id, arquivado)
        self.app.servico.notificar()
        self.atualizar()
        return False

    def _dialogo_nome(self, tabela, item):
        d = Adw.AlertDialog(heading="Renomear" if item else "Novo")
        entry = Adw.EntryRow(title="Nome", text=item["nome"] if item else "")
        grupo = Adw.PreferencesGroup()
        grupo.add(entry)
        d.set_extra_child(grupo)
        d.add_response("cancelar", "Cancelar")
        d.add_response("salvar", "Salvar")
        d.set_response_appearance("salvar", Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response("salvar")

        def on_resp(_d, resp):
            if resp != "salvar":
                return
            nome = entry.get_text().strip()
            try:
                if not nome:
                    raise ValueError("nome vazio")
                if item:
                    cadastros.renomear(self.app.conn, tabela, item["id"], nome)
                else:
                    cadastros.criar(self.app.conn, tabela, nome)
                self.app.servico.notificar()
                self.atualizar()
            except ValueError as e:
                self.get_root().toast(f"Não salvou: {e}")
        d.connect("response", on_resp)
        d.present(self.get_root())
