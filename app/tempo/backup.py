import shutil
from pathlib import Path


def fazer(db_path, pasta, hoje, guardar=7):
    db_path, pasta = Path(db_path), Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"tempo-{hoje.isoformat()}.db"
    if destino.exists():
        return None
    shutil.copy2(db_path, destino)
    antigos = sorted(pasta.glob("tempo-*.db"))
    for p in antigos[:-guardar]:
        p.unlink()
    return destino
