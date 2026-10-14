import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';
import Clutter from 'gi://Clutter';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const NOME = 'br.com.oguim.Tempo';
const SEM_CLIENTE = 'Sem cliente';
const CAMINHO = '/br/com/oguim/Tempo/Servico';
const IFACE = `<node><interface name="br.com.oguim.Tempo.Servico">
  <method name="Iniciar"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="i" direction="out"/></method>
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

const Indicador = GObject.registerClass(
class Indicador extends PanelMenu.Button {
    _init() {
        super._init(0.5, 'Tempo');
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
        this._clienteSel = null;
        this._atividadeSel = null;
        this._tick = 0;
        this._proxy = null;
        this._sinalId = 0;
        this._iniciado = false;
        this._geracao = 0;

        this._montarMenu();
        this._conectar();
        this.menu.connect('open-state-changed', (_m, aberto) => { if (aberto) this._recarregar(); });
    }

    // Cria o proxy D-Bus. O sinal e conectado mesmo se o servico ainda nao estiver de pe.
    _conectar() {
        this._desconectarSinal();
        this._iniciado = false;
        const geracao = ++this._geracao;
        this._proxy = new Proxy(Gio.DBus.session, NOME, CAMINHO, (_p, erro) => {
            if (this._destruido || geracao !== this._geracao || !this._proxy) return;
            this._conectarSinal();
            if (erro) { this._semServico(); return; }
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
    }

    _recarregar() {
        if (this._destruido) return;
        // Proxy que nunca iniciou (servico estava fora): recria, o que ja recarrega tudo.
        if (!this._proxy || !this._iniciado) { this._conectar(); return; }
        this._proxy.EntradaAtualRemote((r, e) => {
            if (this._destruido) return;
            if (e) { this._semServico(); return; }
            this._icone.opacity = 255;
            this._reconectar.visible = false;
            this._aplicar(r[0]);
        });
        this._proxy.ClientesRemote((r, e) => {
            if (this._destruido || e) return;
            // id 0 = sem cliente, o mesmo valor que o servico entende no Iniciar
            this._clientes = [{id: 0, nome: SEM_CLIENTE}, ...JSON.parse(r[0])];
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

    // Nome do item selecionado (ou null se ainda nao ha lista ou selecao).
    _nomeSel(tipo) {
        const itens = tipo === 'cliente' ? this._clientes : this._atividades;
        const id = tipo === 'cliente' ? this._clienteSel : this._atividadeSel;
        return itens.find(i => i.id === id)?.nome ?? null;
    }

    _rotuloSub(sub, tipo) {
        const nome = this._nomeSel(tipo);
        sub.label.text = `${tipo === 'cliente' ? 'Cliente' : 'Atividade'}: ${nome ?? '(nenhum)'}`;
        this._atualizarTrocar();
    }

    _atualizarTrocar() {
        this._trocar.visible = this._entrada != null;
        this._trocar.label.text = `Trocar para ${this._nomeSel('cliente') ?? '(nenhum)'} · ${this._nomeSel('atividade') ?? '(nenhum)'}`;
    }

    // Padrao quando nao ha selecao: o ultimo usado (recentes), senao o primeiro da lista.
    _padrao(itens, tipo) {
        if (this._recentesLista === null) return null;
        const r = this._recentesLista[0];
        const id = r ? (tipo === 'cliente' ? (r.cliente_id ?? 0) : r.atividade_id) : null;
        return itens.find(i => i.id === id) ?? itens[0] ?? null;
    }

    _preencher(sub, itens, tipo) {
        if (this._destruido) return;
        sub.menu.removeAll();
        const selId = tipo === 'cliente' ? this._clienteSel : this._atividadeSel;
        const sel = itens.find(i => i.id === selId) ?? this._padrao(itens, tipo);
        if (tipo === 'cliente') this._clienteSel = sel?.id ?? null; else this._atividadeSel = sel?.id ?? null;
        this._rotuloSub(sub, tipo);
        for (const it of itens) {
            const item = new PopupMenu.PopupMenuItem(it.nome);
            item.connect('activate', () => {
                if (tipo === 'cliente') this._clienteSel = it.id; else this._atividadeSel = it.id;
                this._rotuloSub(sub, tipo);
            });
            sub.menu.addMenuItem(item);
        }
    }

    _preencherRecentes(lista) {
        if (this._destruido) return;
        this._recentesLista = lista;
        this._recentes.removeAll();
        for (const r of lista) {
            const item = new PopupMenu.PopupMenuItem(`${r.cliente || SEM_CLIENTE} · ${r.atividade}`);
            item.connect('activate', () => this._proxy?.IniciarRemote(r.cliente_id ?? 0, r.atividade_id, '', () => {}));
            this._recentes.addMenuItem(item);
        }
        if ((this._clienteSel == null || this._atividadeSel == null) && lista.length > 0) {
            this._clienteSel = lista[0].cliente_id ?? 0;
            this._atividadeSel = lista[0].atividade_id;
        }
        // Ultimo recurso: primeiro item de cada lista ja carregada.
        if (this._clienteSel == null) this._clienteSel = this._clientes[0]?.id ?? null;
        if (this._atividadeSel == null) this._atividadeSel = this._atividades[0]?.id ?? null;
        this._rotuloSub(this._subCli, 'cliente');
        this._rotuloSub(this._subAti, 'atividade');
    }

    _iniciarOuParar() {
        if (!this._proxy) return;
        if (this._entrada) {
            this._proxy.PararRemote(() => {});
        } else if (this._atividadeSel != null) {
            this._proxy.IniciarRemote(this._clienteSel ?? 0, this._atividadeSel, this._desc.get_text(), (_r, e) => {
                if (!this._destruido && !e) this._desc.set_text('');
            });
        } else {
            Main.notify('Tempo', 'Cadastre pelo menos uma atividade no relatório antes de iniciar.');
        }
    }

    // Com um timer rodando, inicia a tarefa escolhida nos seletores (o servico fecha a anterior sem intervalo).
    _trocarTarefa() {
        if (!this._proxy || this._atividadeSel == null) return;
        this._proxy.IniciarRemote(this._clienteSel ?? 0, this._atividadeSel, this._desc.get_text(), (_r, e) => {
            if (!this._destruido && !e) this._desc.set_text('');
        });
    }

    _aplicar(json) {
        if (this._destruido) return;
        this._entrada = json && json !== 'null' ? JSON.parse(json) : null;
        if (this._entrada) {
            this._clienteSel = this._entrada.cliente_id ?? 0;
            this._atividadeSel = this._entrada.atividade_id;
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
        this._rotuloSub(this._subCli, 'cliente');
        this._rotuloSub(this._subAti, 'atividade');
        this._proxy?.RecentesRemote((r, e) => {
            if (this._destruido || e) return;
            this._preencherRecentes(JSON.parse(r[0]));
        });
    }

    _atualizarRotulo() {
        if (!this._entrada) return;
        const seg = segundosDesde(this._entrada.inicio);
        const aviso = seg >= LIMITE_AVISO_SEG ? ' ⚠' : '';
        // Sem cliente, mostra a atividade: curta e sempre presente (a descricao e livre e esticaria a barra)
        this._rotulo.text = `▶ ${fmtDuracao(seg)} · ${this._entrada.cliente || this._entrada.atividade}${aviso}`;
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
        super.destroy();
    }
});

export default class TempoExtension extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._indicador = new Indicador();
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
