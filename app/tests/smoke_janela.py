"""Fumaça da janela (sem apresentar). Rodar: dbus-run-session -- python3 app/tests/smoke_janela.py"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["TEMPO_DIR"] = tempfile.mkdtemp(prefix="tempo-smoke-")
os.environ["TEMPO_RUNTIME_DIR"] = os.environ["TEMPO_DIR"]  # não toca o tempo-sessao da sessão real

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from tempo import banco, cadastros, entradas, servico
from tempo.app import App
from tempo.janela.hoje import DialogoEntrada, PaginaHoje
from tempo.janela.janela import Janela

c = banco.abrir(os.environ["TEMPO_DIR"] + "/tempo.db")
cid = cadastros.criar(c, "clientes", "Casttema", "#e01b24")
aid = next(a["id"] for a in cadastros.listar(c, "atividades") if a["nome"] == "Edição")
t = datetime.now().astimezone().replace(hour=9, minute=0, second=0, microsecond=0)
entradas.criar_manual(c, t, t + timedelta(hours=2), cid, aid, "reel 07")

Adw.init()
app = App()
assert app.register(None)  # emite startup (abre o banco de TEMPO_DIR) e registra o serviço no barramento
c = app.conn
avisos = []
app.servico.emitir = lambda s: avisos.append(s)

jan = Janela(app)
app.janela = jan  # como do_activate faz: o serviço redesenha a janela ao mudar a entrada


def bombear():
    """Roda o que ficou agendado em idle (o redesenho pedido pelo serviço)."""
    ctx = GLib.MainContext.default()
    while ctx.pending():
        ctx.iteration(False)
pag = jan.paginas["hoje"]
assert isinstance(pag, PaginaHoje)
assert set(jan.paginas) == {"hoje", "gargalos", "cadastros"}
jan.atualizar()


def linhas():
    out, w = [], pag.lista.get_first_child()
    while w is not None:
        out.append(w)
        w = w.get_next_sibling()
    return out


def sufixo(row):
    # o Label de sufixo é o único Gtk.Label descendente com "–"
    achados = []
    def varrer(w):
        f = w.get_first_child()
        while f is not None:
            if isinstance(f, Gtk.Label) and "–" in f.get_text():
                achados.append(f.get_text())
            varrer(f)
            f = f.get_next_sibling()
    varrer(row)
    return achados[0]


rs = linhas()
assert len(rs) == 1 and isinstance(rs[0], Adw.ActionRow), rs
assert rs[0].get_title() == "Casttema · Edição", rs[0].get_title()
assert rs[0].get_subtitle() == "reel 07"
s = sufixo(rs[0])
assert "09:00–11:00" in s and "2h" in s, s
assert pag.total.get_text() == "Total do dia: 2h", pag.total.get_text()

ent = entradas.do_dia(c, t.date())[0]
d = DialogoEntrada(jan, app, ent, jan.atualizar)
assert d.ini.get_text() == "09:00" and d.fim.get_text() == "11:00"
assert d.clientes[d.cli.get_selected()]["id"] == cid
d.fim.set_text("12:00")
d._on_resp(None, "salvar")
assert entradas.do_dia(c, t.date())[0]["minutos"] == 180
assert pag.total.get_text() == "Total do dia: 3h", pag.total.get_text()
assert avisos, "notificar() não emitiu sinal"

# validação: fim antes do início vira toast, sem alterar
d2 = DialogoEntrada(jan, app, entradas.do_dia(c, t.date())[0], jan.atualizar)
d2.fim.set_text("08:00")
d2._on_resp(None, "salvar")
assert entradas.do_dia(c, t.date())[0]["minutos"] == 180

# falha de validação: toast em pt-BR e novo diálogo com o digitado preservado
toasts, apresentados = [], []
jan.toast = lambda texto: toasts.append(texto)
DialogoEntrada.present = lambda self, pai=None: apresentados.append(self)
for fim_ruim, trecho in (("08:00", "fim precisa ser depois do início"), ("25:99", "horário inválido, use HH:MM")):
    toasts.clear(); apresentados.clear()
    d5 = DialogoEntrada(jan, app, entradas.do_dia(c, t.date())[0], jan.atualizar)
    d5.desc.set_text("texto digitado"); d5.ini.set_text("09:30"); d5.fim.set_text(fim_ruim)
    d5._on_resp(None, "salvar")
    assert toasts == [f"Não salvou: {trecho}"], toasts
    assert len(apresentados) == 1 and apresentados[0] is not d5
    n = apresentados[0]
    assert (n.desc.get_text(), n.ini.get_text(), n.fim.get_text()) == ("texto digitado", "09:30", fim_ruim)
    assert n.entrada is d5.entrada
    assert entradas.do_dia(c, t.date())[0]["minutos"] == 180
# cancelar não reabre
apresentados.clear(); d5._on_resp(None, "cancelar"); assert not apresentados
# texto malformado sem dois pontos
toasts.clear(); d5.fim.set_text("abc"); d5._on_resp(None, "salvar")
assert toasts == ["Não salvou: horário inválido, use HH:MM"], toasts

# entrada manual
d3 = DialogoEntrada(jan, app, None, jan.atualizar)
d3.ini.set_text("13:00"); d3.fim.set_text("14:30"); d3.desc.set_text("manual")
d3._on_resp(None, "salvar")
assert len(linhas()) == 2 and pag.total.get_text() == "Total do dia: 4h30", pag.total.get_text()

# apagar
d4 = DialogoEntrada(jan, app, entradas.do_dia(c, t.date())[1], jan.atualizar)
d4._on_resp(None, "apagar")
assert len(linhas()) == 1

# cliente arquivado da própria entrada: aparece no combo e Salvar mantém o vínculo
cid2 = cadastros.criar(c, "clientes", "Antigo", "#33d17a")
eid_arq = entradas.criar_manual(c, t.replace(hour=15), t.replace(hour=16), cid2, aid, "arquivada")
cadastros.arquivar(c, "clientes", cid2)
ent_arq = entradas.por_id(c, eid_arq)
d6 = DialogoEntrada(jan, app, ent_arq, jan.atualizar)
nomes = [d6.cli.get_model().get_string(i) for i in range(d6.cli.get_model().get_n_items())]
assert nomes[-1] == "Antigo (arquivado)", nomes
assert d6.clientes[d6.cli.get_selected()]["id"] == cid2
d6.desc.set_text("só a descrição")
d6._on_resp(None, "salvar")
depois = entradas.por_id(c, eid_arq)
assert depois["descricao"] == "só a descrição" and depois["cliente_id"] == cid2, depois
# diálogo de entrada nova não oferece o arquivado
d7 = DialogoEntrada(jan, app, None, jan.atualizar)
assert all(i["id"] != cid2 for i in d7.clientes)
entradas.apagar(c, eid_arq)

# --- cartão do cronômetro na aba Hoje ---
from tempo.janela.hoje import CartaoTimer, SEM_CLIENTE
cart = pag.cartao
assert isinstance(cart, CartaoTimer)
jan.atualizar()
assert cart.pilha.get_visible_child_name() == "parado"
# pré-seleção vem da última entrada (Casttema · Edição)
assert cart._clientes[cart.cli.get_selected()]["id"] == cid
assert cart._atividades[cart.ati.get_selected()]["id"] == aid
assert cart._clientes[0]["nome"] == SEM_CLIENTE
# iniciar só com o nome: hora de início é agora, cronômetro aparece, barra é avisada
avisos.clear()
cart.nome.set_text("")
cart.iniciar(); bombear()
assert entradas.atual(c) is None and not cart.btn_iniciar.get_sensitive()  # nome vazio não inicia
cart.nome.set_text("   ")
cart.iniciar(); bombear()
assert entradas.atual(c) is None
cart.nome.set_text("roteiro do reel")
assert cart.btn_iniciar.get_sensitive()
cart.iniciar(); bombear()
assert cart.pilha.get_visible_child_name() == "rodando"
e_ab = entradas.atual(c)
assert e_ab["descricao"] == "roteiro do reel" and e_ab["cliente_id"] == cid and e_ab["atividade_id"] == aid
assert abs((datetime.now().astimezone() - entradas.parse(e_ab["inicio"])).total_seconds()) < 5
assert cart.relogio.get_text().startswith("00:00:0"), cart.relogio.get_text()
assert cart.legenda.get_text() == "Casttema · Edição · roteiro do reel", cart.legenda.get_text()
assert cart.nome.get_text() == "" and cart._tick is not None
assert avisos and json.loads(avisos[-1])["id"] == e_ab["id"]
# parar: volta pro estado parado, entrada fechada entra na lista do dia
cart.parar(); bombear()
assert cart.pilha.get_visible_child_name() == "parado" and cart._tick is None
assert entradas.atual(c) is None
assert any(r.get_subtitle() == "roteiro do reel" for r in linhas())
# iniciar sem cliente: lista mostra "Sem cliente"
cart.cli.set_selected(0)
cart.nome.set_text("reunião")
cart.iniciar(); bombear()
assert entradas.atual(c)["cliente_id"] is None
assert cart.legenda.get_text() == "Sem cliente · Edição · reunião", cart.legenda.get_text()
# a barra do GNOME parou pelo serviço: a janela redesenha sozinha
app.servico.chamar("Parar", ()); bombear()
assert cart.pilha.get_visible_child_name() == "parado"
assert any(r.get_title() == "Sem cliente · Edição" for r in linhas())
# iniciar pela barra (cliente 0 = sem cliente) também aparece na janela
app.servico.chamar("Iniciar", (0, aid, "pela barra")); bombear()
assert cart.pilha.get_visible_child_name() == "rodando" and cart.legenda.get_text() == "Sem cliente · Edição · pela barra"
cart.parar(); bombear()
# regressão: a barra roda outro cliente · atividade; ao parar, os seletores da janela seguem essa tarefa
cid_h = cadastros.criar(c, "clientes", "Hornero", "#33d17a")
aid_c = next(a["id"] for a in cadastros.listar(c, "atividades") if a["nome"] != "Edição")
cart.cli.set_selected(cart._clientes.index(next(i for i in cart._clientes if i["id"] == cid)))
app.servico.chamar("Iniciar", (cid_h, aid_c, "pela barra 2")); bombear()
app.servico.chamar("Parar", ()); bombear()
assert cart._clientes[cart.cli.get_selected()]["id"] == cid_h, cart._clientes[cart.cli.get_selected()]
assert cart._atividades[cart.ati.get_selected()]["id"] == aid_c
# parado → parado: o que o oguim escolheu nos seletores fica
cart.cli.set_selected(0); jan.atualizar()
assert cart._clientes[cart.cli.get_selected()]["id"] is None
# a barra inicia com a aba Hoje escondida; ao voltar pra Hoje o cartão está rodando
jan.stack.set_visible_child_name("gargalos")
app.servico.chamar("Iniciar", (cid_h, aid_c, "escondida")); bombear()
jan.stack.set_visible_child_name("hoje")
assert cart.pilha.get_visible_child_name() == "rodando" and cart.legenda.get_text() == "Hornero · " + next(a["nome"] for a in cart._atividades if a["id"] == aid_c) + " · escondida"
cart.parar(); bombear()
# barra inicia e para com a Hoje escondida: ao voltar, os seletores seguem a tarefa nova
cart.cli.set_selected(0); cart.nome.set_text("digitando")
jan.stack.set_visible_child_name("gargalos")
app.servico.chamar("Iniciar", (cid_h, aid_c, "escondida 2")); bombear()
app.servico.chamar("Parar", ()); bombear()
jan.stack.set_visible_child_name("hoje")
assert cart._clientes[cart.cli.get_selected()]["id"] == cid_h
assert cart.nome.get_text() == "digitando"  # redesenho não mexe no que foi digitado
cart.nome.set_text("")
# aba Cadastros visível: mudança de entrada não reconstrói a lista
jan.stack.set_visible_child_name("cadastros")
app.servico.chamar("Iniciar", (cid_h, aid_c, "x")); bombear()
app.servico.chamar("Parar", ()); bombear()
jan.stack.set_visible_child_name("hoje")
# editar entrada sem cliente: diálogo abre em "Sem cliente" e salvar mantém
ent_sc = next(e for e in entradas.do_dia(c, t.date()) if e["descricao"] == "reunião")
d8 = DialogoEntrada(jan, app, ent_sc, jan.atualizar)
assert d8.clientes[d8.cli.get_selected()]["id"] is None
d8._on_resp(None, "salvar")
assert entradas.por_id(c, ent_sc["id"])["cliente_id"] is None
for e in entradas.do_dia(c, t.date()):
    if e["descricao"] in ("roteiro do reel", "reunião", "pela barra", "pela barra 2", "escondida", "escondida 2", "x"):
        entradas.apagar(c, e["id"])
cadastros.arquivar(c, "clientes", cid_h)
jan.atualizar()

# esquecida: sem entrada aberta, não abre diálogo
jan.checar_esquecida()

# esquecida: a resposta age só na entrada que foi perguntada (passa o id)
import tempo.janela.janela as mod_janela
from datetime import timedelta as _td
chamadas = []
real_resolver = mod_janela.esquecida.resolver
mod_janela.esquecida.resolver = lambda conn, modo, agora=None, id=None: chamadas.append((modo, id))
alertas = []
Adw.AlertDialog.present = lambda self, pai=None: alertas.append(self)
velha = entradas.iniciar(c, cid, aid, "velha", agora=app.servico.inicio_sessao - _td(hours=3))
jan.checar_esquecida()
assert len(alertas) == 1
alertas[0].emit("response", "descartar")
assert chamadas == [("descartar", velha)], chamadas
mod_janela.esquecida.resolver = real_resolver
entradas.apagar(c, velha)
print("SMOKE OK")
