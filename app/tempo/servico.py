import json
from datetime import datetime

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from tempo import VERSAO, cadastros, entradas, esquecida

INTERFACE = "br.com.oguim.Tempo.Servico"
CAMINHO = "/br/com/oguim/Tempo/Servico"
NOME = "br.com.oguim.Tempo"

XML = f"""<node>
<interface name="{INTERFACE}">
  <method name="Iniciar">
    <arg type="i" name="cliente_id" direction="in"/>
    <arg type="i" name="atividade_id" direction="in"/>
    <arg type="s" name="descricao" direction="in"/>
    <arg type="i" name="id" direction="out"/>
  </method>
  <method name="Parar"><arg type="b" name="parou" direction="out"/></method>
  <method name="EntradaAtual"><arg type="s" name="json" direction="out"/></method>
  <method name="Recentes"><arg type="s" name="json" direction="out"/></method>
  <method name="Clientes"><arg type="s" name="json" direction="out"/></method>
  <method name="Atividades"><arg type="s" name="json" direction="out"/></method>
  <method name="Esquecida"><arg type="s" name="json" direction="out"/></method>
  <method name="ResolverEsquecida"><arg type="s" name="modo" direction="in"/></method>
  <method name="AbrirJanela"/>
  <method name="Versao"><arg type="s" name="versao" direction="out"/></method>
  <signal name="EntradaMudou"><arg type="s" name="json"/></signal>
</interface>
</node>"""

ASSINATURAS = {
    "Iniciar": "(i)", "Parar": "(b)", "EntradaAtual": "(s)", "Recentes": "(s)", "Clientes": "(s)",
    "Atividades": "(s)", "Esquecida": "(s)", "ResolverEsquecida": "()", "AbrirJanela": "()", "Versao": "(s)",
}


class Servico:
    def __init__(self, conn, emitir, abrir_janela, inicio_sessao=None):
        self.conn = conn
        self.emitir = emitir
        self.abrir_janela = abrir_janela
        self.inicio_sessao = inicio_sessao or datetime.now().astimezone().replace(microsecond=0)

    def notificar(self):
        self.emitir(json.dumps(entradas.atual(self.conn)))

    def chamar(self, nome, args):
        if nome == "Iniciar":
            cid, aid, desc = args
            eid = entradas.iniciar(self.conn, cid, aid, desc)
            self.notificar()
            return (eid,)
        if nome == "Parar":
            parou = entradas.parar(self.conn)
            self.notificar()
            return (parou,)
        if nome == "EntradaAtual":
            return (json.dumps(entradas.atual(self.conn)),)
        if nome == "Recentes":
            return (json.dumps(entradas.recentes(self.conn)),)
        if nome == "Clientes":
            return (json.dumps(cadastros.listar(self.conn, "clientes")),)
        if nome == "Atividades":
            return (json.dumps(cadastros.listar(self.conn, "atividades")),)
        if nome == "Esquecida":
            return (json.dumps(esquecida.detectar(self.conn, self.inicio_sessao)),)
        if nome == "ResolverEsquecida":
            esquecida.resolver(self.conn, args[0])
            self.notificar()
            return ()
        if nome == "AbrirJanela":
            self.abrir_janela()
            return ()
        if nome == "Versao":
            return (VERSAO,)
        raise ValueError(f"método desconhecido: {nome}")


def registrar(conn_dbus, caminho, servico):
    info = Gio.DBusNodeInfo.new_for_xml(XML)

    def on_call(conn, sender, path, iface, method, params, inv):
        try:
            res = servico.chamar(method, params.unpack())
            inv.return_value(GLib.Variant(ASSINATURAS[method], res))
        except Exception as e:  # erro vira erro D-Bus legível, não derruba o serviço
            inv.return_dbus_error("br.com.oguim.Tempo.Erro", str(e))

    return conn_dbus.register_object(caminho, info.interfaces[0], on_call, None, None)


def emissor(conn_dbus, caminho):
    def emitir(json_str):
        conn_dbus.emit_signal(None, caminho, INTERFACE, "EntradaMudou", GLib.Variant("(s)", (json_str,)))
    return emitir
