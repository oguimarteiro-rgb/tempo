import os
import sys
from datetime import date
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib

from tempo import backup, banco, esquecida, servico, sessao
from tempo.caminhos import pasta_dados  # noqa: F401  (sem GTK: o resumo também usa)


def pasta_runtime():
    # TEMPO_RUNTIME_DIR existe para os testes não tocarem o arquivo da sessão real.
    return os.environ.get("TEMPO_RUNTIME_DIR") or None


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=servico.NOME, flags=Gio.ApplicationFlags.IS_SERVICE)
        self.conn = None
        self.servico = None
        self.janela = None
        self._emitir = lambda s: None

    def do_startup(self):
        Adw.Application.do_startup(self)
        pasta = pasta_dados()
        pasta.mkdir(parents=True, exist_ok=True)
        self._db = pasta / "tempo.db"
        self._pasta_backup = pasta / "backup"
        self.conn = banco.abrir(str(self._db))
        self._backup_horario()  # só depois de o banco abrir: não copia arquivo que não abre
        GLib.timeout_add_seconds(3600, self._backup_horario)
        if self.servico is not None:
            self.servico.conn = self.conn
        self.hold()
        if self.servico is not None and esquecida.detectar(self.conn, self.servico.inicio_sessao):
            GLib.idle_add(self.activate)  # abre a janela com a pergunta da entrada esquecida

    def _backup_horario(self):
        # backup.fazer é idempotente por dia: rodar de hora em hora pega a virada do dia.
        backup.fazer(self._db, self._pasta_backup, date.today())
        return GLib.SOURCE_CONTINUE

    def do_dbus_register(self, conn_dbus, caminho):
        Adw.Application.do_dbus_register(self, conn_dbus, caminho)
        self._emitir = servico.emissor(conn_dbus, servico.CAMINHO)
        self.servico = servico.Servico(self.conn, emitir=self._emitir, abrir_janela=self.abrir_janela,
                                       inicio_sessao=sessao.inicio_sessao(pasta_runtime()))
        self.servico.ao_mudar = self._mudou
        self._registro = servico.registrar(conn_dbus, servico.CAMINHO, self.servico)
        return True

    def _mudou(self):
        # Em idle: a resposta D-Bus sai antes do redesenho (erro de tela não vira erro pra barra)
        # e várias mudanças seguidas viram um redesenho só.
        if self.janela is not None and not getattr(self, "_redesenho_pendente", False):
            self._redesenho_pendente = True
            GLib.idle_add(self._redesenhar)

    def _redesenhar(self):
        self._redesenho_pendente = False
        if self.janela is not None and self.janela.stack.get_visible_child_name() != "cadastros":
            self.janela.atualizar()  # Cadastros não muda com entrada; Hoje e Gargalos mudam
        return GLib.SOURCE_REMOVE

    def abrir_janela(self):
        GLib.idle_add(self.activate)

    def do_activate(self):
        from tempo.janela.janela import Janela
        if self.janela is None:
            self.janela = Janela(self)
            self.janela.connect("close-request", self._fechou)
        self.janela.present()
        self.janela.atualizar()
        self.janela.checar_esquecida()

    def _fechou(self, *_):
        self.janela = None
        return False


def main():
    app = App()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
