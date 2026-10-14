from datetime import date, datetime, time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango

from tempo import cadastros, entradas, gargalos


SEM_CLIENTE = "Sem cliente"


def _hhmm(iso):
    return iso[11:16] if iso else "…"


def _nome_cliente(e):
    return e["cliente"] or SEM_CLIENTE


class CartaoTimer(Gtk.Box):
    """Topo da aba Hoje: parado pede só o nome; rodando mostra o cronômetro e Parar."""

    def __init__(self, app):
        super().__init__(css_classes=["card"])
        self.app = app
        self._tick = None
        self._inicio = None
        self._clientes, self._atividades = [], []
        self._cid, self._aid = None, None  # seleção lembrada entre redesenhos
        self._marca = object()  # id da entrada mais recente vista na última carga dos seletores
        self._rodando = False
        self.pilha = Gtk.Stack(hexpand=True, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12,
                               transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.append(self.pilha)

        parado = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        linha = Gtk.Box(spacing=6)
        self.nome = Gtk.Entry(placeholder_text="No que você está trabalhando?", hexpand=True)
        self.nome.connect("activate", lambda *_: self.iniciar())
        self.nome.connect("changed", lambda *_: self._habilitar())
        self.btn_iniciar = Gtk.Button(label="Iniciar", css_classes=["suggested-action"], sensitive=False)
        self.btn_iniciar.connect("clicked", lambda *_: self.iniciar())
        linha.append(self.nome)
        linha.append(self.btn_iniciar)
        seletores = Gtk.Box(spacing=6)
        self.cli = Gtk.DropDown(tooltip_text="Cliente")
        self.ati = Gtk.DropDown(tooltip_text="Atividade")
        seletores.append(self.cli)
        seletores.append(self.ati)
        parado.append(linha)
        parado.append(seletores)
        self.pilha.add_named(parado, "parado")

        rodando = Gtk.Box(spacing=12)
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        self.relogio = Gtk.Label(xalign=0, css_classes=["cronometro", "numeric"])
        self.legenda = Gtk.Label(xalign=0, css_classes=["dim-label"], ellipsize=Pango.EllipsizeMode.END)
        textos.append(self.relogio)
        textos.append(self.legenda)
        self.btn_parar = Gtk.Button(label="Parar", css_classes=["destructive-action"], valign=Gtk.Align.CENTER)
        self.btn_parar.connect("clicked", lambda *_: self.parar())
        rodando.append(textos)
        rodando.append(self.btn_parar)
        self.pilha.add_named(rodando, "rodando")
        # O destroy da janela faz unrealize, e é aí que o timer de 1 s morre.
        self.connect("unrealize", lambda *_: self._parar_tick())

    # --- estado ---
    def atualizar(self):
        e = entradas.atual(self.app.conn)
        if e:
            self._inicio = e["inicio"]
            partes = [_nome_cliente(e), e["atividade"]]
            if e["descricao"]:
                partes.append(e["descricao"])
            self.legenda.set_text(" · ".join(partes))
            self._bater()
            if self._tick is None:
                self._tick = GLib.timeout_add_seconds(1, self._bater)
            self.pilha.set_visible_child_name("rodando")
            self._rodando = True
        else:
            self._parar_tick()
            self._carregar_opcoes()
            self.pilha.set_visible_child_name("parado")
            if self._rodando and self.get_mapped():
                self.nome.grab_focus()  # só ao parar: num redesenho parado→parado roubaria o texto digitado
            self._rodando = False

    def _bater(self):
        if self._inicio is None:
            self._tick = None
            return GLib.SOURCE_REMOVE
        self.relogio.set_text(entradas.cronometro(self._inicio))
        return GLib.SOURCE_CONTINUE

    def _parar_tick(self):
        if self._tick is not None:
            GLib.source_remove(self._tick)
            self._tick = None
        self._inicio = None

    def _carregar_opcoes(self):
        """Seleção: se rodou tarefa nova desde a última carga (por aqui, pela barra ou pelo diálogo), segue ela;
        senão fica o que está nos seletores. Item lembrado que foi arquivado cai no primeiro da lista."""
        ultimo = entradas.recentes(self.app.conn, 1)
        marca = ultimo[0]["ultimo_id"] if ultimo else None
        if marca != self._marca:
            self._marca = marca
            if ultimo:
                self._cid, self._aid = ultimo[0]["cliente_id"], ultimo[0]["atividade_id"]
        elif self._clientes:
            self._cid = self._clientes[self.cli.get_selected()]["id"]
            self._aid = self._atividades[self.ati.get_selected()]["id"] if self._atividades else None
        self._clientes = [{"id": None, "nome": SEM_CLIENTE}] + cadastros.listar(self.app.conn, "clientes")
        self._atividades = cadastros.listar(self.app.conn, "atividades")
        for combo, itens, sel in ((self.cli, self._clientes, self._cid), (self.ati, self._atividades, self._aid)):
            combo.set_model(Gtk.StringList.new([i["nome"] for i in itens]))
            for idx, i in enumerate(itens):
                if i["id"] == sel:
                    combo.set_selected(idx)
        self._habilitar()

    def _habilitar(self):
        self.btn_iniciar.set_sensitive(bool(self._atividades) and bool(self.nome.get_text().strip()))

    # --- ações ---
    def iniciar(self):
        if not self.nome.get_text().strip():
            return  # o nome é obrigatório; Enter vazio não faz nada
        if not self._atividades:
            self.get_root().toast("Cadastre pelo menos uma atividade antes de iniciar")
            return
        cid = self._clientes[self.cli.get_selected()]["id"]
        aid = self._atividades[self.ati.get_selected()]["id"]
        entradas.iniciar(self.app.conn, cid, aid, self.nome.get_text())
        self.nome.set_text("")
        self.app.servico.notificar()  # avisa a barra do GNOME e redesenha a janela

    def parar(self):
        entradas.parar(self.app.conn)
        self.app.servico.notificar()


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
        self.cartao = CartaoTimer(app)
        self.append(self.cartao)
        self.lista = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        scroll = Gtk.ScrolledWindow(vexpand=True, child=self.lista)
        self.append(scroll)
        self.total = Gtk.Label(xalign=1, css_classes=["dim-label"])
        self.append(self.total)

    def atualizar(self):
        hoje = date.today()
        self.titulo.set_text(hoje.strftime("%A, %d/%m").capitalize())
        self.cartao.atualizar()
        while (filho := self.lista.get_first_child()) is not None:
            self.lista.remove(filho)
        lista = entradas.do_dia(self.app.conn, hoje)
        for e in lista:
            row = Adw.ActionRow(title=f"{_nome_cliente(e)} · {e['atividade']}", subtitle=e["descricao"], activatable=True)
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
        self.clientes = self._itens("clientes", (entrada or {}).get("cliente_id"))
        self.atividades = self._itens("atividades", (entrada or {}).get("atividade_id"))
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

    def _itens(self, tabela, id_da_entrada):
        """Ativos, mais o arquivado da própria entrada (no fim), para Salvar não trocar o vínculo."""
        itens = cadastros.listar(self.app.conn, tabela)
        if tabela == "clientes":
            itens.insert(0, {"id": None, "nome": SEM_CLIENTE})
        if id_da_entrada is not None and all(i["id"] != id_da_entrada for i in itens):
            for i in cadastros.listar(self.app.conn, tabela, incluir_arquivados=True):
                if i["id"] == id_da_entrada:
                    itens.append(dict(i, nome=f"{i['nome']} (arquivado)"))
        return itens

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
                if not self.atividades:
                    raise ValueError("cadastre pelo menos uma atividade")
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
