import sqlite3

SCHEMA = """
create table if not exists clientes(
  id integer primary key,
  nome text not null unique,
  cor text not null default '#3584e4',
  arquivado integer not null default 0
);
create table if not exists atividades(
  id integer primary key,
  nome text not null unique,
  cor text not null default '#3584e4',
  arquivado integer not null default 0
);
create table if not exists entradas(
  id integer primary key,
  inicio text not null,
  fim text,
  cliente_id integer references clientes(id),
  atividade_id integer references atividades(id),
  descricao text not null default ''
);
create unique index if not exists uma_aberta on entradas((fim is null)) where fim is null;
create index if not exists entradas_inicio on entradas(inicio);
"""

ATIVIDADES_PADRAO = [
    ("Edição", "#3584e4"), ("Captação", "#2ec27e"), ("Reunião", "#e66100"),
    ("Roteiro", "#9141ac"), ("Administrativo", "#c01c28"), ("Estudo", "#f5c211"),
    ("Deslocamento", "#5e5c64"),
]


def abrir(caminho=":memory:"):
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    conn.executescript(SCHEMA)
    if conn.execute("select count(*) from atividades").fetchone()[0] == 0:
        conn.executemany("insert into atividades(nome, cor) values(?, ?)", ATIVIDADES_PADRAO)
        conn.commit()
    return conn
