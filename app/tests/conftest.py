import pytest
from tempo import banco

@pytest.fixture
def conn():
    c = banco.abrir(":memory:")
    yield c
    c.close()
