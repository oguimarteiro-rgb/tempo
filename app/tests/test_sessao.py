from datetime import datetime, timedelta, timezone

from tempo import sessao

TZ = timezone(timedelta(hours=-3))
AGORA = datetime(2026, 10, 14, 8, 30, 15, 123456, tzinfo=TZ)


def test_cria_quando_nao_existe_sem_microssegundos(tmp_path):
    v = sessao.inicio_sessao(tmp_path, agora=AGORA)
    assert v == AGORA.replace(microsecond=0)
    assert v.microsecond == 0 and v.tzinfo is not None
    assert (tmp_path / "tempo-sessao").read_text().strip() == "2026-10-14T08:30:15-03:00"


def test_padrao_sem_microssegundos_e_com_fuso(tmp_path):
    v = sessao.inicio_sessao(tmp_path)
    assert v.microsecond == 0 and v.tzinfo is not None


def test_reaproveita_quando_existe(tmp_path):
    (tmp_path / "tempo-sessao").write_text("2026-10-14T07:00:00-03:00\n")
    v = sessao.inicio_sessao(tmp_path, agora=AGORA)
    assert v == datetime(2026, 10, 14, 7, 0, tzinfo=TZ)
    assert (tmp_path / "tempo-sessao").read_text().strip() == "2026-10-14T07:00:00-03:00"


def test_reinicio_do_servico_mantem_a_sessao(tmp_path):
    primeira = sessao.inicio_sessao(tmp_path, agora=AGORA)
    depois = sessao.inicio_sessao(tmp_path, agora=AGORA + timedelta(hours=3))
    assert depois == primeira


def test_ignora_conteudo_invalido_e_regrava(tmp_path):
    (tmp_path / "tempo-sessao").write_text("lixo")
    v = sessao.inicio_sessao(tmp_path, agora=AGORA)
    assert v == AGORA.replace(microsecond=0)
    assert (tmp_path / "tempo-sessao").read_text().strip() == "2026-10-14T08:30:15-03:00"


def test_ignora_valor_sem_fuso_e_regrava(tmp_path):
    (tmp_path / "tempo-sessao").write_text("2026-10-14T07:00:00")
    v = sessao.inicio_sessao(tmp_path, agora=AGORA)
    assert v == AGORA.replace(microsecond=0)


def test_pasta_padrao_e_xdg_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    sessao.inicio_sessao(agora=AGORA)
    assert (tmp_path / "tempo-sessao").exists()
