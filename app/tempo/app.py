import os
import sys
from datetime import date
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib

from tempo import backup, banco, servico


def pasta_dados():
    return Path(os.environ.get("TEMPO_DIR") or Path.home() / ".local/share/tempo")


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
        db = pasta / "tempo.db"
        if db.exists():
            backup.fazer(db, pasta / "backup", date.today())
        self.conn = banco.abrir(str(db))
        if self.servico is not None:
            self.servico.conn = self.conn
        self.hold()

    def do_dbus_register(self, conn_dbus, caminho):
        Adw.Application.do_dbus_register(self, conn_dbus, caminho)
        self._emitir = servico.emissor(conn_dbus, servico.CAMINHO)
        self.servico = servico.Servico(self.conn, emitir=self._emitir, abrir_janela=self.abrir_janela)
        self._registro = servico.registrar(conn_dbus, servico.CAMINHO, self.servico)
        return True

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
