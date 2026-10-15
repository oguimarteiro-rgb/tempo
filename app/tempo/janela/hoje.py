from datetime import date, datetime, time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango

from tempo import cadastros, entradas, gargalos
from tempo.janela.seletor import SeletorMultiplo


SEM_CLIENTE = "Sem cliente"


def _hhmm(iso):
    return iso[11:16] if iso else "…"


class CartaoTimer(Gtk.Box):
    """Topo da aba Hoje: parado pede só o nome; rodando mostra o cronômetro e Parar."""

    def __init__(self, app):
        super().__init__(css_classes=["card"])
        self.app = app
        self._tick = None
        self._inicio = None
        self._clientes, self._atividades = [], []
        self._cids, self._aids = [], []  # seleção lembrada entre redesenhos
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
        self.cli = SeletorMultiplo(SEM_CLIENTE, tooltip_text="Clientes")
        self.ati = SeletorMultiplo("Atividade", tooltip_text="Atividades")
        self.ati.connect("mudou", lambda *_: self._habilitar())
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
            partes = [entradas.rotulo(e)]
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
        senão fica o que está nos seletores. Item lembrado que foi arquivado some da marcação."""
        ultimo = entradas.recentes(self.app.conn, 1)
        marca = ultimo[0]["ultimo_id"] if ultimo else None
        if marca != self._marca:
            self._marca = marca
            if ultimo:
                self._cids, self._aids = ultimo[0]["cliente_ids"], ultimo[0]["atividade_ids"]
        elif self._atividades:
            self._cids, self._aids = self.cli.get_selecionados(), self.ati.get_selecionados()
        self._clientes = cadastros.listar(self.app.conn, "clientes")
        self._atividades = cadastros.listar(self.app.conn, "atividades")
        self.cli.set_itens(self._clientes, self._cids)
        self.ati.set_itens(self._atividades, self._aids)
        self._habilitar()

    def _habilitar(self):
        self.btn_iniciar.set_sensitive(bool(self.ati.get_selecionados()) and bool(self.nome.get_text().strip()))

    # --- ações ---
    def iniciar(self):
        if not self.nome.get_text().strip():
            return  # o nome é obrigatório; Enter vazio não faz nada
        aids = self.ati.get_selecionados()
        if not aids:
            self.get_root().toast("Marque pelo menos uma atividade antes de iniciar")
            return
        entradas.iniciar(self.app.conn, self.cli.get_selecionados(), aids, self.nome.get_text())
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
            row = Adw.ActionRow(title=entradas.rotulo(e), subtitle=e["descricao"], activatable=True)
            row.add_suffix(Gtk.Label(label=f"{_hhmm(e['inicio'])}–{_hhmm(e['fim'])}   {gargalos.fmt_h(e['minutos'])}",
                                     css_classes=["numeric"]))
            row.connect("activated", lambda _r, ent=e: DialogoEntrada(self.get_root(), self.app, ent, self.atualizar).present(self.get_root()))
            self.lista.append(row)
        self.total.set_text(f"Total do dia: {gargalos.fmt_h(gargalos.total_minutos(lista))}")


class DialogoEntrada(Adw.Dialog):
    """Editar ou lançar entrada. Fica aberto quando a validação falha, mostrando o erro dentro dele
    (um AlertDialog fecha sozinho na resposta, e reabrir outro por cima empilhava diálogos)."""

    def __init__(self, janela, app, entrada, depois, valores=None):
        super().__init__(title="Editar entrada" if entrada else "Nova entrada", content_width=440)
        self.app, self.entrada, self.depois, self.janela = app, entrada, depois, janela
        grupo = Adw.PreferencesGroup()
        v = valores or {}
        self.desc = Adw.EntryRow(title="Descrição", text=v.get("descricao", (entrada or {}).get("descricao", "")))
        self.clientes = self._itens("clientes", (entrada or {}).get("cliente_ids", []))
        self.atividades = self._itens("atividades", (entrada or {}).get("atividade_ids", []))
        self.cli = self._linha("Clientes", SEM_CLIENTE, self.clientes,
                               v.get("cliente_ids", (entrada or {}).get("cliente_ids", [])))
        # entrada nova começa com a primeira atividade marcada, como o combo antigo fazia
        padrao_ati = entrada["atividade_ids"] if entrada else [i["id"] for i in self.atividades[:1]]
        self.ati = self._linha("Atividades", "Atividade", self.atividades, v.get("atividade_ids", padrao_ati))
        ini_txt = _hhmm((entrada or {}).get("inicio")) if entrada else ""
        fim_txt = _hhmm((entrada or {}).get("fim")) if entrada and entrada.get("fim") else ""
        self.ini = Adw.EntryRow(title="Início (HH:MM)", text=v.get("inicio", ini_txt))
        self.fim = Adw.EntryRow(title="Fim (HH:MM)", text=v.get("fim", fim_txt))
        for w in (self.desc, self._linha_cli, self._linha_ati, self.ini, self.fim):
            grupo.add(w)
        if not entrada:
            grupo.set_description("Deixe Início e Fim vazios para iniciar agora.")

        corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                        margin_top=6, margin_bottom=12, margin_start=12, margin_end=12)
        corpo.append(grupo)
        self.erro = Gtk.Label(xalign=0, wrap=True, visible=False, css_classes=["error"])
        corpo.append(self.erro)
        botoes = Gtk.Box(spacing=6, halign=Gtk.Align.END)
        cancelar = Gtk.Button(label="Cancelar")
        cancelar.connect("clicked", lambda *_: self._on_resp(None, "cancelar"))
        botoes.append(cancelar)
        if entrada:
            apagar = Gtk.Button(label="Apagar", css_classes=["destructive-action"])
            apagar.connect("clicked", lambda *_: self._on_resp(None, "apagar"))
            botoes.append(apagar)
        salvar = Gtk.Button(label="Iniciar agora" if not entrada else "Salvar", css_classes=["suggested-action"])
        salvar.connect("clicked", lambda *_: self._on_resp(None, "salvar"))
        botoes.append(salvar)
        self.btn_salvar = salvar
        corpo.append(botoes)
        if not entrada:
            for w in (self.ini, self.fim):
                w.connect("changed", lambda *_: self._rotulo_salvar())

        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        view.set_content(corpo)
        self.set_child(view)
        self.set_default_widget(salvar)  # Enter nos campos aciona Salvar

    def _rotulo_salvar(self):
        vazio = not self.ini.get_text().strip() and not self.fim.get_text().strip()
        self.btn_salvar.set_label("Iniciar agora" if vazio else "Salvar")

    def _itens(self, tabela, ids_da_entrada):
        """Ativos, mais os arquivados da própria entrada (no fim), para Salvar não perder o vínculo."""
        itens = cadastros.listar(self.app.conn, tabela)
        faltam = [i for i in ids_da_entrada if all(it["id"] != i for it in itens)]
        if faltam:
            for i in cadastros.listar(self.app.conn, tabela, incluir_arquivados=True):
                if i["id"] in faltam:
                    itens.append(dict(i, nome=f"{i['nome']} (arquivado)"))
        return itens

    def _linha(self, titulo, vazio, itens, selecionados):
        seletor = SeletorMultiplo(vazio, valign=Gtk.Align.CENTER)
        seletor.set_itens(itens, selecionados)
        linha = Adw.ActionRow(title=titulo)
        linha.add_suffix(seletor)
        linha.set_activatable_widget(seletor)
        if titulo == "Clientes":
            self._linha_cli = linha
        else:
            self._linha_ati = linha
        return seletor

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
                cids = self.cli.get_selecionados()
                aids = self.ati.get_selecionados()
                base = (self.entrada or {}).get("inicio")
                if not self.entrada and not self.ini.get_text().strip() and not self.fim.get_text().strip():
                    entradas.iniciar(self.app.conn, cids, aids, self.desc.get_text())
                    self.app.servico.notificar()
                    self.depois()
                    self.close()
                    return
                ini = self._hora(self.ini.get_text(), base)
                fim_txt = self.fim.get_text().strip()
                fim = self._hora(fim_txt, base) if fim_txt else None
                if self.entrada:
                    campos = dict(descricao=self.desc.get_text(), cliente_id=cids, atividade_id=aids, inicio=ini)
                    if fim is not None:
                        if fim <= ini:
                            raise ValueError("fim precisa ser depois do início")
                        campos["fim"] = fim
                    entradas.editar(self.app.conn, self.entrada["id"], **campos)
                else:
                    if fim is None:
                        raise ValueError("entrada passada precisa de fim")
                    entradas.criar_manual(self.app.conn, ini, fim, cids, aids, self.desc.get_text())
            else:
                self.close()
                return
            self.app.servico.notificar()
            self.depois()
            self.close()
        except (ValueError, IndexError) as e:
            self.erro.set_text(f"Não salvou: {e}")
            self.erro.set_visible(True)
