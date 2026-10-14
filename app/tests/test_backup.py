from datetime import date, timedelta
from tempo import backup

def test_cria_e_nao_duplica(tmp_path):
    db = tmp_path / "tempo.db"; db.write_bytes(b"x")
    pasta = tmp_path / "backup"
    p = backup.fazer(db, pasta, date(2026, 10, 13))
    assert p == pasta / "tempo-2026-10-13.db" and p.read_bytes() == b"x"
    assert backup.fazer(db, pasta, date(2026, 10, 13)) is None

def test_guarda_sete(tmp_path):
    db = tmp_path / "tempo.db"; db.write_bytes(b"x")
    pasta = tmp_path / "backup"
    for i in range(10):
        backup.fazer(db, pasta, date(2026, 10, 1) + timedelta(days=i))
    nomes = sorted(p.name for p in pasta.iterdir())
    assert len(nomes) == 7 and nomes[0] == "tempo-2026-10-04.db"
