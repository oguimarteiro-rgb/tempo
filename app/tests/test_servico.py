import json, os, subprocess, sys, time
from datetime import datetime, timedelta, timezone
import pytest
from tempo import servico, cadastros, entradas

TZ = timezone(timedelta(hours=-3))
T0 = datetime(2026, 10, 13, 10, 0, tzinfo=TZ)
AQUI = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(AQUI)


@pytest.fixture
def sv(conn):
    sinais = []
    s = servico.Servico(conn, emitir=sinais.append, abrir_janela=lambda: sinais.append("janela"),
                        inicio_sessao=T0 + timedelta(hours=5))
    s.sinais = sinais
    return s


def test_iniciar_parar_emitem_sinal(conn, sv):
    c = cadastros.criar(conn, "clientes", "Casttema")
    a = cadastros.listar(conn, "atividades")[0]["id"]
    (eid,) = sv.chamar("Iniciar", (c, a, "reel"))
    assert json.loads(sv.chamar("EntradaAtual", ())[0])["id"] == eid
    assert json.loads(sv.sinais[-1])["id"] == eid
    assert sv.chamar("Parar", ()) == (True,)
    assert sv.chamar("EntradaAtual", ()) == ("null",)
    assert sv.sinais[-1] == "null"


def test_listas_em_json(conn, sv):
    cadastros.criar(conn, "clientes", "Viretto")
    assert [c["nome"] for c in json.loads(sv.chamar("Clientes", ())[0])] == ["Viretto"]
    assert len(json.loads(sv.chamar("Atividades", ())[0])) == 7
    assert sv.chamar("Recentes", ()) == ("[]",)


def test_esquecida(conn, sv):
    c = cadastros.criar(conn, "clientes", "Casttema")
    a = cadastros.listar(conn, "atividades")[0]["id"]
    entradas.iniciar(conn, c, a, agora=T0)
    assert json.loads(sv.chamar("Esquecida", ())[0])["cliente"] == "Casttema"
    sv.chamar("ResolverEsquecida", ("descartar",))
    assert sv.chamar("Esquecida", ()) == ("null",)
    assert sv.chamar("EntradaAtual", ()) == ("null",)


def test_abrir_janela_e_versao(sv):
    sv.chamar("AbrirJanela", ())
    assert sv.sinais[-1] == "janela"
    assert sv.chamar("Versao", ()) == ("0.1.0",)


def test_metodo_desconhecido(sv):
    with pytest.raises(ValueError):
        sv.chamar("Explodir", ())


@pytest.mark.skipif(not os.path.exists("/usr/bin/dbus-run-session"), reason="sem dbus-run-session")
def test_processo_real_responde_no_dbus(tmp_path):
    script = f"""
import gi, subprocess, sys, time, os
from gi.repository import Gio, GLib
env = dict(os.environ, TEMPO_DIR={str(tmp_path)!r}, PYTHONPATH={APP_DIR!r})
p = subprocess.Popen([sys.executable, "-m", "tempo.app"], env=env)
try:
    for _ in range(50):
        time.sleep(0.1)
        try:
            px = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SESSION, Gio.DBusProxyFlags.DO_NOT_AUTO_START, None,
                 "br.com.oguim.Tempo", "/br/com/oguim/Tempo/Servico", "br.com.oguim.Tempo.Servico", None)
            r = px.call_sync("Versao", None, 0, 2000, None)
            print("VERSAO", r.unpack()[0]); break
        except GLib.Error:
            continue
    else:
        print("FALHOU")
finally:
    p.terminate(); p.wait(5)
"""
    out = subprocess.run(["dbus-run-session", "--", sys.executable, "-c", script],
                         capture_output=True, text=True, timeout=60)
    assert "VERSAO 0.1.0" in out.stdout, out.stdout + out.stderr
    assert (tmp_path / "tempo.db").exists()
