import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Pango from 'gi://Pango';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const NOME = 'br.com.oguim.Tempo';
const SEM_CLIENTE = 'Sem cliente';
const CAMINHO = '/br/com/oguim/Tempo/Servico';
const IFACE = `<node><interface name="br.com.oguim.Tempo.Servico">
  <method name="Iniciar"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="i" direction="out"/></method>
  <method name="IniciarVarios"><arg type="ai" direction="in"/><arg type="ai" direction="in"/><arg type="s" direction="in"/><arg type="i" direction="out"/></method>
  <method name="Parar"><arg type="b" direction="out"/></method>
  <method name="EntradaAtual"><arg type="s" direction="out"/></method>
  <method name="Recentes"><arg type="s" direction="out"/></method>
  <method name="Clientes"><arg type="s" direction="out"/></method>
  <method name="Atividades"><arg type="s" direction="out"/></method>
  <method name="AbrirJanela"/>
  <method name="Versao"><arg type="s" direction="out"/></method>
  <signal name="EntradaMudou"><arg type="s"/></signal>
</interface></node>`;
const Proxy = Gio.DBusProxy.makeProxyWrapper(IFACE);

const LIMITE_AVISO_SEG = 12 * 3600;
const MARGEM_CARTAO = 24;

// Segundos decorridos desde o instante ISO 8601 informado (0 se invalido).
function segundosDesde(iso) {
    const ini = GLib.DateTime.new_from_iso8601(iso, null);
    if (!ini) return 0;
    return Math.max(0, GLib.DateTime.new_now_local().difference(ini) / 1e6);
}

function fmtDuracao(seg) {
    const h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60), s = Math.floor(seg % 60);
    return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
                 : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function fmtRelogio(seg) {
    const h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60), s = Math.floor(seg % 60);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// Item de submenu que marca/desmarca sem fechar o menu (o activate padrão fecharia a árvore inteira).
const ItemMarcavel = GObject.registerClass({
    Signals: {'marcou': {}},
}, class ItemMarcavel extends PopupMenu.PopupMenuItem {
    activate(_event) {
        this.emit('marcou');
    }
});

// Cartao flutuante com o cronometro: fica por cima de tudo, arrasta com o mouse e lembra a posicao.
const Cartao = GObject.registerClass(
class Cartao extends St.BoxLayout {
    _init(settings, acoes) {
        super._init({style_class: 'tempo-cartao', vertical: true, reactive: true, visible: false});
        this._settings = settings;
        this._acoes = acoes;
        this._arrasto = null;
        this._mostrado = false;  // estado proprio: addTopChrome pode deixar o ator visivel por conta propria

        const topo = new St.BoxLayout({x_expand: true});
        this._legenda = new St.Label({style_class: 'tempo-cartao-legenda', x_expand: true, y_align: Clutter.ActorAlign.CENTER});
        this._legenda.clutter_text.ellipsize = Pango.EllipsizeMode.END;
        const fechar = new St.Button({style_class: 'tempo-cartao-fechar', can_focus: true,
            child: new St.Icon({icon_name: 'window-close-symbolic', icon_size: 14})});
        fechar.connect('clicked', () => this._acoes.fechar());
        topo.add_child(this._legenda);
        topo.add_child(fechar);

        const base = new St.BoxLayout({x_expand: true});
        this._relogio = new St.Label({style_class: 'tempo-cartao-relogio', x_expand: true, y_align: Clutter.ActorAlign.CENTER, text: '00:00:00'});
        const parar = new St.Button({style_class: 'tempo-cartao-parar', label: 'Parar', can_focus: true, y_align: Clutter.ActorAlign.CENTER});
        parar.connect('clicked', () => this._acoes.parar());
        base.add_child(this._relogio);
        base.add_child(parar);

        this.add_child(topo);
        this.add_child(base);

        this.connect('button-press-event', (_a, ev) => this._pressionou(ev));
        this.connect('motion-event', (_a, ev) => this._moveu(ev));
        this.connect('button-release-event', () => this._soltou());
        // trackFullscreen: some quando ha janela em tela cheia no monitor (video no VLC, playback do Resolve).
        Main.layoutManager.addTopChrome(this, {trackFullscreen: true});
        this.hide();
        // O LayoutManager faz actor.visible = !fullscreen ao abrir o overview, trocar de monitor etc.
        // Sem tarefa (ou depois do X) ele mostraria o cartao vazio: desfaz na hora.
        this.connect('notify::visible', () => { if (this.visible && !this._mostrado) this.hide(); });
        this._monitoresId = Main.layoutManager.connect('monitors-changed', () => { if (this._mostrado) this._posicionar(); });
        this.connect('notify::width', () => { if (this._mostrado && !this._arrasto) this._mover(this.x, this.y); });
    }

    mostrar(entrada) {
        const partes = [
            entrada.clientes?.map(c => c.nome).join(' + ') || SEM_CLIENTE,
            entrada.atividades?.map(a => a.nome).join(' + ') || entrada.atividade || '',
        ];
        if (entrada.descricao) partes.push(entrada.descricao);
        this._legenda.text = partes.join(' · ');
        if (!this._mostrado) {
            this._mostrado = true;
            this.show();
            this._posicionar();
        }
    }

    esconder() {
        this._mostrado = false;
        this.hide();
    }

    atualizar(seg) {
        this._relogio.text = fmtRelogio(seg);
        if (seg >= LIMITE_AVISO_SEG) this._relogio.add_style_class_name('aviso');
        else this._relogio.remove_style_class_name('aviso');
    }

    // Area util do monitor principal (sem a barra de cima nem docks que reservam espaco).
    _monitor() {
        const lm = Main.layoutManager;
        if (lm.primaryIndex >= 0) {
            try { return lm.getWorkAreaForMonitor(lm.primaryIndex); } catch (_e) { /* cai no monitor inteiro */ }
        }
        return lm.primaryMonitor ?? {x: 0, y: 0, width: 1920, height: 1080};
    }

    _posicionar() {
        const m = this._monitor();
        const [, w] = this.get_preferred_width(-1);
        const [, h] = this.get_preferred_height(w);
        let x = this._settings.get_int('cartao-x');
        let y = this._settings.get_int('cartao-y');
        if (x < 0 || y < 0) {
            x = m.x + m.width - w - MARGEM_CARTAO;
            y = m.y + m.height - h - MARGEM_CARTAO * 4;  // folga pra dock que nao reserva espaco
        }
        this._mover(x, y, w, h);
        console.log(`Tempo: cartão em ${this.x},${this.y} (${w}x${h})`);
    }

    // Mantem o cartao inteiro dentro do monitor principal.
    _mover(x, y, w = this.width, h = this.height) {
        const m = this._monitor();
        x = Math.max(m.x, Math.min(x, m.x + m.width - w));
        y = Math.max(m.y, Math.min(y, m.y + m.height - h));
        this.set_position(Math.round(x), Math.round(y));
    }

    _sobreBotao(ator) {
        for (let a = ator; a && a !== this; a = a.get_parent())
            if (a instanceof St.Button) return true;
        return false;
    }

    _pressionou(ev) {
        if (ev.get_button() !== 1 || this._sobreBotao(ev.get_source())) return Clutter.EVENT_PROPAGATE;
        const [x, y] = ev.get_coords();
        this._arrasto = {dx: x - this.x, dy: y - this.y, moveu: false};
        return Clutter.EVENT_STOP;
    }

    _moveu(ev) {
        if (!this._arrasto) return Clutter.EVENT_PROPAGATE;
        if (!(ev.get_state() & Clutter.ModifierType.BUTTON1_MASK)) return this._soltou();  // release engolido por outro grab
        const [x, y] = ev.get_coords();
        this._mover(x - this._arrasto.dx, y - this._arrasto.dy);
        this._arrasto.moveu = true;
        return Clutter.EVENT_STOP;
    }

    _soltou() {
        if (!this._arrasto) return Clutter.EVENT_PROPAGATE;
        if (this._arrasto.moveu) {
            this._settings.set_int('cartao-x', this.x);
            this._settings.set_int('cartao-y', this.y);
        }
        this._arrasto = null;
        return Clutter.EVENT_STOP;
    }

    destroy() {
        if (this._monitoresId) { Main.layoutManager.disconnect(this._monitoresId); this._monitoresId = 0; }
        Main.layoutManager.removeChrome(this);
        super.destroy();
    }
});

const Indicador = GObject.registerClass(
class Indicador extends PanelMenu.Button {
    _init(settings) {
        super._init(0.5, 'Tempo');
        this._settings = settings;
        this._caixa = new St.BoxLayout({style_class: 'panel-status-menu-box'});
        this._ponto = new St.Label({text: '●', y_align: Clutter.ActorAlign.CENTER, visible: false});
        this._icone = new St.Icon({icon_name: 'alarm-symbolic', style_class: 'system-status-icon'});
        this._rotulo = new St.Label({text: '', y_align: Clutter.ActorAlign.CENTER});
        this._caixa.add_child(this._ponto);
        this._caixa.add_child(this._icone);
        this._caixa.add_child(this._rotulo);
        this.add_child(this._caixa);

        this._destruido = false;
        this._entrada = null;
        this._clientes = [];
        this._atividades = [];
        this._recentesLista = null;
        this._clientesSel = [];
        this._atividadesSel = [];
        // Clientes vazios é uma escolha válida (sem cliente): o padrão dos recentes entra só uma vez,
        // antes de o oguim mexer ou de chegar uma entrada. Depois disso, vazio fica vazio.
        this._clientesDecididos = false;
        // Itens dos submenus por tipo (id -> item), pra manter o check igual à seleção.
        this._itensMenu = {cliente: new Map(), atividade: new Map()};
        this._tick = 0;
        this._proxy = null;
        this._sinalId = 0;
        this._iniciado = false;
        this._geracao = 0;
        this._cartao = new Cartao(settings, {
            parar: () => this._proxy?.PararRemote((_r, e) => { if (e && !this._destruido) this._recarregar(); }),
            fechar: () => this._cartaoVisivel(false),
        });

        this._montarMenu();
        this._conectar();
        this.menu.connect('open-state-changed', (_m, aberto) => { if (aberto) this._recarregar(); });
        // No desligamento do Shell os atores morrem por baixo, sem passar por destroy(): parar o tick aqui.
        this.connect('destroy', () => { this._destruido = true; this._pararTick(); });
    }

    // Cria o proxy D-Bus. O sinal e conectado mesmo se o servico ainda nao estiver de pe.
    _conectar() {
        this._desconectarSinal();
        this._iniciado = false;
        const geracao = ++this._geracao;
        this._proxy = new Proxy(Gio.DBus.session, NOME, CAMINHO, (_p, erro) => {
            if (this._destruido || geracao !== this._geracao || !this._proxy) return;
            this._conectarSinal();
            if (erro) { console.log(`Tempo: serviço indisponível (${erro.message})`); this._semServico(); return; }
            this._iniciado = true;
            this._recarregar();
        });
    }

    _conectarSinal() {
        if (!this._proxy || this._sinalId) return;
        this._sinalId = this._proxy.connectSignal('EntradaMudou', (_p, _s, [json]) => {
            if (this._destruido) return;
            this._icone.opacity = 255;
            this._reconectar.visible = false;
            this._aplicar(json);
        });
    }

    _desconectarSinal() {
        if (this._proxy && this._sinalId) this._proxy.disconnectSignal(this._sinalId);
        this._sinalId = 0;
    }

    _montarMenu() {
        this._btn = new PopupMenu.PopupMenuItem('Iniciar');
        this._btn.connect('activate', () => this._iniciarOuParar());
        this.menu.addMenuItem(this._btn);

        this._trocar = new PopupMenu.PopupMenuItem('Trocar para');
        this._trocar.connect('activate', () => this._trocarTarefa());
        this._trocar.visible = false;
        this.menu.addMenuItem(this._trocar);

        const campo = new PopupMenu.PopupBaseMenuItem({reactive: false, can_focus: false});
        this._desc = new St.Entry({hint_text: 'Descrição (opcional)', x_expand: true, can_focus: true});
        campo.add_child(this._desc);
        this.menu.addMenuItem(campo);

        this._subCli = new PopupMenu.PopupSubMenuMenuItem('Cliente');
        this._subAti = new PopupMenu.PopupSubMenuMenuItem('Atividade');
        this.menu.addMenuItem(this._subCli);
        this.menu.addMenuItem(this._subAti);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem('Recentes'));
        this._recentes = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._recentes);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._mostrarCartao = new PopupMenu.PopupSwitchMenuItem('Cartão flutuante',
            this._settings.get_boolean('cartao-flutuante'));
        this._mostrarCartao.connect('toggled', (_i, ligado) => this._cartaoVisivel(ligado));
        this.menu.addMenuItem(this._mostrarCartao);
        const abrir = new PopupMenu.PopupMenuItem('Abrir relatório');
        abrir.connect('activate', () => this._proxy?.AbrirJanelaRemote(() => {}));
        this.menu.addMenuItem(abrir);
        this._reconectar = new PopupMenu.PopupMenuItem('Reconectar ao serviço');
        this._reconectar.connect('activate', () => this._recarregar());
        this._reconectar.visible = false;
        this.menu.addMenuItem(this._reconectar);
    }

    _semServico() {
        if (this._destruido) return;
        this._entrada = null;
        this._btn.label.text = 'Iniciar';
        this._trocar.visible = false;
        this._icone.visible = true;
        this._icone.opacity = 120;
        this._rotulo.text = '';
        this._ponto.visible = false;
        this._reconectar.visible = true;
        this._pararTick();
        this._atualizarCartao();
    }

    // O cartão é opcional e vem desligado: a barra já mostra o tempo. O X e o interruptor
    // do menu gravam a mesma chave, que sobrevive a bloqueio de tela e reinício do serviço.
    _cartaoVisivel(sim) {
        this._settings.set_boolean('cartao-flutuante', sim);
        this._atualizarCartao();
    }

    _atualizarCartao() {
        if (this._destruido) return;
        const ligado = this._settings.get_boolean('cartao-flutuante');
        if (this._mostrarCartao.state !== ligado) this._mostrarCartao.setToggleState(ligado);
        if (!this._entrada) {
            this._cartao.esconder();
            return;
        }
        if (ligado) {
            this._cartao.mostrar(this._entrada);
            this._cartao.atualizar(segundosDesde(this._entrada.inicio));
        } else {
            this._cartao.esconder();
        }
    }

    _recarregar() {
        if (this._destruido) return;
        // Proxy que nunca iniciou (servico estava fora): recria, o que ja recarrega tudo.
        if (!this._proxy || !this._iniciado) { this._conectar(); return; }
        this._proxy.EntradaAtualRemote((r, e) => {
            if (this._destruido) return;
            if (e) { console.log(`Tempo: EntradaAtual falhou (${e.message})`); this._semServico(); return; }
            this._icone.opacity = 255;
            this._reconectar.visible = false;
            this._aplicar(r[0]);
        });
        this._proxy.ClientesRemote((r, e) => {
            if (this._destruido || e) return;
            // Sem cliente agora é "nenhum cliente marcado", não um item da lista.
            this._clientes = JSON.parse(r[0]);
            this._preencher(this._subCli, this._clientes, 'cliente');
        });
        this._proxy.AtividadesRemote((r, e) => {
            if (this._destruido || e) return;
            this._atividades = JSON.parse(r[0]);
            this._preencher(this._subAti, this._atividades, 'atividade');
        });
        this._proxy.RecentesRemote((r, e) => {
            if (this._destruido) return;
            if (e) { if (this._recentesLista === null) this._recentesLista = []; return; }
            this._preencherRecentes(JSON.parse(r[0]));
        });
    }

    // Rótulo curto da seleção: '(nenhuma)', 'Pessoal' ou 'Pessoal +1'. Sem cliente marcado: 'Sem cliente'.
    _rotuloSel(tipo) {
        const itens = tipo === 'cliente' ? this._clientes : this._atividades;
        const ids = tipo === 'cliente' ? this._clientesSel : this._atividadesSel;
        const nomes = itens.filter(i => ids.includes(i.id)).map(i => i.nome);
        if (nomes.length === 0) return tipo === 'cliente' ? SEM_CLIENTE : '(nenhuma)';
        return nomes.length === 1 ? nomes[0] : `${nomes[0]} +${nomes.length - 1}`;
    }

    _rotuloSub(sub, tipo) {
        sub.label.text = `${tipo === 'cliente' ? 'Cliente' : 'Atividade'}: ${this._rotuloSel(tipo)}`;
        const ids = tipo === 'cliente' ? this._clientesSel : this._atividadesSel;
        for (const [id, item] of this._itensMenu[tipo])
            item.setOrnament(ids.includes(id) ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
        this._atualizarTrocar();
    }

    _atualizarTrocar() {
        this._trocar.visible = this._entrada != null;
        this._trocar.label.text = `Trocar para ${this._rotuloSel('cliente')} · ${this._rotuloSel('atividade')}`;
    }

    // Padrão quando nada está marcado: a última combinação usada (recentes), senão a primeira atividade.
    _padrao(tipo) {
        const r = this._recentesLista?.[0];
        if (r) return tipo === 'cliente' ? [...(r.cliente_ids ?? [])] : [...(r.atividade_ids ?? [])];
        if (tipo === 'atividade' && this._atividades[0]) return [this._atividades[0].id];
        return [];
    }

    _preencher(sub, itens, tipo) {
        if (this._destruido) return;
        sub.menu.removeAll();
        this._itensMenu[tipo].clear();
        const validos = new Set(itens.map(i => i.id));
        let sel = (tipo === 'cliente' ? this._clientesSel : this._atividadesSel).filter(id => validos.has(id));
        const podePadrao = tipo === 'atividade' || !this._clientesDecididos;
        if (sel.length === 0 && podePadrao && this._recentesLista !== null) sel = this._padrao(tipo).filter(id => validos.has(id));
        if (tipo === 'cliente') {
            this._clientesSel = sel;
            if (this._recentesLista !== null) this._clientesDecididos = true;
        } else {
            this._atividadesSel = sel;
        }
        for (const it of itens) {
            const item = new ItemMarcavel(it.nome);
            this._itensMenu[tipo].set(it.id, item);
            item.connect('marcou', () => {
                const atual = tipo === 'cliente' ? this._clientesSel : this._atividadesSel;
                // marca/desmarca; a ordem dos marcados segue a ordem da lista (o primeiro é o principal)
                const novo = atual.includes(it.id) ? atual.filter(id => id !== it.id) : [...atual, it.id];
                const ordenado = itens.map(i => i.id).filter(id => novo.includes(id));
                if (tipo === 'cliente') {
                    this._clientesSel = ordenado;
                    this._clientesDecididos = true;
                } else {
                    this._atividadesSel = ordenado;
                }
                this._rotuloSub(sub, tipo);
            });
            sub.menu.addMenuItem(item);
        }
        this._rotuloSub(sub, tipo);
    }

    _preencherRecentes(lista) {
        if (this._destruido) return;
        this._recentesLista = lista;
        this._recentes.removeAll();
        for (const r of lista) {
            const item = new PopupMenu.PopupMenuItem(`${r.cliente || SEM_CLIENTE} · ${r.atividade}`);
            item.connect('activate', () => this._proxy?.IniciarVariosRemote(r.cliente_ids ?? [], r.atividade_ids ?? [], '', () => {}));
            this._recentes.addMenuItem(item);
        }
        if (this._atividadesSel.length === 0 && lista.length > 0) {
            // Não repõe clientes que o oguim já desmarcou de propósito.
            if (!this._clientesDecididos) this._clientesSel = [...(lista[0].cliente_ids ?? [])];
            this._atividadesSel = [...(lista[0].atividade_ids ?? [])];
        }
        this._clientesDecididos = true;
        // Último recurso: a primeira atividade da lista já carregada.
        if (this._atividadesSel.length === 0 && this._atividades[0]) this._atividadesSel = [this._atividades[0].id];
        this._rotuloSub(this._subCli, 'cliente');
        this._rotuloSub(this._subAti, 'atividade');
    }

    _iniciarOuParar() {
        if (!this._proxy) return;
        if (this._entrada) {
            this._proxy.PararRemote(() => {});
        } else {
            this._trocarTarefa();
        }
    }

    // Inicia a combinação marcada (com timer rodando, o serviço fecha a anterior sem intervalo).
    _trocarTarefa() {
        if (!this._proxy) return;
        if (this._atividadesSel.length === 0) {
            Main.notify('Tempo', 'Marque pelo menos uma atividade antes de iniciar.');
            return;
        }
        this._proxy.IniciarVariosRemote(this._clientesSel, this._atividadesSel, this._desc.get_text(), (_r, e) => {
            if (!this._destruido && !e) this._desc.set_text('');
        });
    }

    _aplicar(json) {
        if (this._destruido) return;
        this._entrada = json && json !== 'null' ? JSON.parse(json) : null;
        if (this._entrada) {
            this._clientesSel = [...(this._entrada.cliente_ids ?? [])];
            this._atividadesSel = [...(this._entrada.atividade_ids ?? [])];
            this._clientesDecididos = true;
            this._btn.label.text = 'Parar';
            this._ponto.visible = true;
            this._ponto.style = `color: ${this._entrada.cor}; margin-right: 4px;`;
            this._icone.visible = false;
            this._atualizarRotulo();
            this._iniciarTick();
        } else {
            this._btn.label.text = 'Iniciar';
            this._ponto.visible = false;
            this._icone.visible = true;
            this._rotulo.text = '';
            this._pararTick();
        }
        this._atualizarCartao();
        this._rotuloSub(this._subCli, 'cliente');
        this._rotuloSub(this._subAti, 'atividade');
        this._proxy?.RecentesRemote((r, e) => {
            if (this._destruido || e) return;
            this._preencherRecentes(JSON.parse(r[0]));
        });
    }

    _atualizarRotulo() {
        if (this._destruido || !this._entrada) return;
        const seg = segundosDesde(this._entrada.inicio);
        const aviso = seg >= LIMITE_AVISO_SEG ? ' ⚠' : '';
        // Sem cliente, mostra a atividade: curta e sempre presente (a descricao e livre e esticaria a barra).
        // Com vários, o primeiro marcado e quantos mais: 'Pessoal +1'.
        const nomes = (this._entrada.clientes?.length ? this._entrada.clientes : this._entrada.atividades ?? []).map(i => i.nome);
        const quem = nomes.length > 1 ? `${nomes[0]} +${nomes.length - 1}` : (nomes[0] ?? (this._entrada.cliente || this._entrada.atividade || ''));
        this._rotulo.text = `▶ ${fmtDuracao(seg)} · ${quem}${aviso}`;
        if (this._cartao._mostrado) this._cartao.atualizar(seg);
    }

    _iniciarTick() {
        this._pararTick();
        this._tick = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => { this._atualizarRotulo(); return GLib.SOURCE_CONTINUE; });
    }

    _pararTick() {
        if (this._tick) { GLib.source_remove(this._tick); this._tick = 0; }
    }

    destroy() {
        this._destruido = true;
        this._pararTick();
        this._desconectarSinal();
        this._proxy = null;
        this._cartao?.destroy();
        this._cartao = null;
        super.destroy();
    }
});

export default class TempoExtension extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._indicador = new Indicador(this._settings);
        Main.panel.addToStatusArea('tempo', this._indicador, 1, 'right');
        Main.wm.addKeybinding('atalho-menu', this._settings, Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW, () => this._indicador.menu.toggle());
    }

    disable() {
        Main.wm.removeKeybinding('atalho-menu');
        this._indicador?.destroy();
        this._indicador = null;
        this._settings = null;
    }
}
