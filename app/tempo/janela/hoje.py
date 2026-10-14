from datetime import date, datetime, time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from tempo import cadastros, entradas, gargalos


def _hhmm(iso):
    return iso[11:16] if iso else "…"


class PaginaHoje(Gtk.Box):
    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12,
                         margin_start=12, margin_end=12)
        self.app = app
        topo = Gtk.Box(spacing=6)
        self.titulo = Gtk.Label(xalign=0, css_classes=["title-2"])
        topo.append(self.titulo)
        topo.append(Gtk.Box(hexpand=True))
        btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Adicionar entrada manual")
        btn.connect("clicked", lambda *_: DialogoEntrada(self.get_root(), self.app, None, self.atualizar).present(self.get_root()))
        topo.append(btn)
        self.append(topo)
        self.lista = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        scroll = Gtk.ScrolledWindow(vexpand=True, child=self.lista)
        self.append(scroll)
        self.total = Gtk.Label(xalign=1, css_classes=["dim-label"])
        self.append(self.total)

    def atualizar(self):
        hoje = date.today()
        self.titulo.set_text(hoje.strftime("%A, %d/%m").capitalize())
        while (filho := self.lista.get_first_child()) is not None:
            self.lista.remove(filho)
        lista = entradas.do_dia(self.app.conn, hoje)
        for e in lista:
            row = Adw.ActionRow(title=f"{e['cliente']} · {e['atividade']}", subtitle=e["descricao"], activatable=True)
            row.add_suffix(Gtk.Label(label=f"{_hhmm(e['inicio'])}–{_hhmm(e['fim'])}   {gargalos.fmt_h(e['minutos'])}",
                                     css_classes=["numeric"]))
            row.connect("activated", lambda _r, ent=e: DialogoEntrada(self.get_root(), self.app, ent, self.atualizar).present(self.get_root()))
            self.lista.append(row)
        self.total.set_text(f"Total do dia: {gargalos.fmt_h(gargalos.total_minutos(lista))}")


class DialogoEntrada(Adw.AlertDialog):
    def __init__(self, janela, app, entrada, depois, valores=None):
        super().__init__(heading="Editar entrada" if entrada else "Nova entrada")
        self.app, self.entrada, self.depois, self.janela = app, entrada, depois, janela
        grupo = Adw.PreferencesGroup()
        v = valores or {}
        self.desc = Adw.EntryRow(title="Descrição", text=v.get("descricao", (entrada or {}).get("descricao", "")))
        self.clientes = cadastros.listar(app.conn, "clientes")
        self.atividades = cadastros.listar(app.conn, "atividades")
        self.cli = self._combo("Cliente", self.clientes, (entrada or {}).get("cliente_id"))
        self.ati = self._combo("Atividade", self.atividades, (entrada or {}).get("atividade_id"))
        if "cli_idx" in v:
            self.cli.set_selected(v["cli_idx"])
        if "ati_idx" in v:
            self.ati.set_selected(v["ati_idx"])
        ini_txt = _hhmm((entrada or {}).get("inicio")) if entrada else ""
        fim_txt = _hhmm((entrada or {}).get("fim")) if entrada and entrada.get("fim") else ""
        self.ini = Adw.EntryRow(title="Início (HH:MM)", text=v.get("inicio", ini_txt))
        self.fim = Adw.EntryRow(title="Fim (HH:MM)", text=v.get("fim", fim_txt))
        for w in (self.desc, self.cli, self.ati, self.ini, self.fim):
            grupo.add(w)
        self.set_extra_child(grupo)
        self.add_response("cancelar", "Cancelar")
        if entrada:
            self.add_response("apagar", "Apagar")
            self.set_response_appearance("apagar", Adw.ResponseAppearance.DESTRUCTIVE)
        self.add_response("salvar", "Salvar")
        self.set_response_appearance("salvar", Adw.ResponseAppearance.SUGGESTED)
        self.set_default_response("salvar")
        self.connect("response", self._on_resp)

    def _combo(self, titulo, itens, selecionado):
        combo = Adw.ComboRow(title=titulo)
        modelo = Gtk.StringList.new([i["nome"] for i in itens])
        combo.set_model(modelo)
        for idx, i in enumerate(itens):
            if i["id"] == selecionado:
                combo.set_selected(idx)
        return combo

    def _hora(self, texto, base_iso):
        try:
            h, m = texto.strip().split(":")
            dia = datetime.fromisoformat(base_iso).date() if base_iso else date.today()
            return datetime.combine(dia, time(int(h), int(m))).astimezone()
        except ValueError:
            raise ValueError("horário inválido, use HH:MM") from None

    def _on_resp(self, _d, resp):
        try:
            if resp == "apagar":
                entradas.apagar(self.app.conn, self.entrada["id"])
            elif resp == "salvar":
                if not self.clientes or not self.atividades:
                    raise ValueError("cadastre pelo menos um cliente e uma atividade")
                cid = self.clientes[self.cli.get_selected()]["id"]
                aid = self.atividades[self.ati.get_selected()]["id"]
                base = (self.entrada or {}).get("inicio")
                ini = self._hora(self.ini.get_text(), base)
                fim_txt = self.fim.get_text().strip()
                fim = self._hora(fim_txt, base) if fim_txt else None
                if self.entrada:
                    campos = dict(descricao=self.desc.get_text(), cliente_id=cid, atividade_id=aid, inicio=ini)
                    if fim is not None:
                        if fim <= ini:
                            raise ValueError("fim precisa ser depois do início")
                        campos["fim"] = fim
                    entradas.editar(self.app.conn, self.entrada["id"], **campos)
                else:
                    if fim is None:
                        raise ValueError("entrada manual precisa de fim")
                    entradas.criar_manual(self.app.conn, ini, fim, cid, aid, self.desc.get_text())
            else:
                return
            self.app.servico.notificar()
            self.depois()
        except (ValueError, IndexError) as e:
            self.janela.toast(f"Não salvou: {e}")
            if resp == "salvar":
                # o AlertDialog fecha sozinho; reabre com o que foi digitado
                valores = dict(descricao=self.desc.get_text(), cli_idx=self.cli.get_selected(),
                               ati_idx=self.ati.get_selected(), inicio=self.ini.get_text(), fim=self.fim.get_text())
                DialogoEntrada(self.janela, self.app, self.entrada, self.depois, valores=valores).present(self.janela)
