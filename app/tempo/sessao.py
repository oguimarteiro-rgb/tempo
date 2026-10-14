"""Início da sessão do usuário, que sobrevive a reinícios do serviço.

O arquivo mora em XDG_RUNTIME_DIR, que o sistema apaga no logout e no boot:
cada login começa uma sessão nova, e um serviço reiniciado no meio da sessão
reaproveita o horário gravado (assim a entrada viva não parece esquecida).
"""
import os
import tempfile
from datetime import datetime
from pathlib import Path

ARQUIVO = "tempo-sessao"


def _pasta_padrao():
    return Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir())


def _ler(arq):
    try:
        v = datetime.fromisoformat(arq.read_text().strip())
    except (OSError, ValueError):
        return None
    if v.tzinfo is None:
        return None
    return v.replace(microsecond=0)


def inicio_sessao(pasta_runtime=None, agora=None):
    arq = Path(pasta_runtime or _pasta_padrao()) / ARQUIVO
    gravado = _ler(arq)
    if gravado is not None:
        return gravado
    agora = (agora or datetime.now().astimezone()).replace(microsecond=0)
    arq.write_text(agora.isoformat(timespec="seconds") + "\n")
    return agora
