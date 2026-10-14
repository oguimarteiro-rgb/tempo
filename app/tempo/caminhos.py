import os
from pathlib import Path


def pasta_dados():
    return Path(os.environ.get("TEMPO_DIR") or Path.home() / ".local/share/tempo")
