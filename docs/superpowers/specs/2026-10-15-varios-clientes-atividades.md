# Tempo: vários clientes e várias atividades por entrada

Data: 2026-10-15. Autor: oguim com Claude. Estado: aprovado em conversa ("vamos seguir").

## Problema

O oguim trabalha com frequência em duas coisas ao mesmo tempo (vibecoding + edição +
roteiro; projeto pessoal + NP Hub). Hoje uma entrada tem um cliente e uma atividade, e o
que ele faz é escrever a combinação no nome ("Projetos pessoais e NP Hub"). O nome vira
texto solto e a métrica se perde: a hora conta só pro cliente escolhido.

## Decisões

| Pergunta | Decisão |
| --- | --- |
| O que pode ser múltiplo | Cliente **e** atividade. Zero ou mais clientes, uma ou mais atividades. |
| Principal | O primeiro da lista, na ordem em que os itens aparecem no cadastro (alfabética). |
| Contagem nos gargalos | **Tempo inteiro pra cada.** 1 h em "Pessoal + NP Hub" conta 1 h pra Pessoal e 1 h pra NP Hub. O total do dia continua 1 h. |
| Visibilidade do modo múltiplo | Linha "Combinado: Pessoal + NP Hub 1h" nas leituras dos Gargalos e no resumo do Telegram. |
| Entradas antigas | Continuam valendo: um cliente, uma atividade. Sem migração manual. |
| Rótulo curto (barra, legendas) | "Pessoal + NP Hub · Reunião + Edição". Na barra do GNOME: "Pessoal +1". |
| Dividir o tempo por igual | Descartado: esconde quanto cada cliente ocupou de verdade. |

## Modelo de dados

Duas tabelas de vínculo, com ordem:

```
entrada_clientes(entrada_id, cliente_id, ordem)      chave (entrada_id, cliente_id)
entrada_atividades(entrada_id, atividade_id, ordem)  chave (entrada_id, atividade_id)
```

As colunas `entradas.cliente_id` e `entradas.atividade_id` continuam existindo e guardam
o **principal** (o primeiro da lista). Toda escrita passa por `tempo.entradas`, que grava
as duas coisas juntas. Ao abrir o banco, as linhas antigas sem vínculo ganham o vínculo
a partir das colunas (`insert or ignore`), então banco antigo funciona sem passo manual.

Dicionário de entrada (`entradas._dict`) ganha:

```
clientes:      [{"id", "nome", "cor"}, ...]   na ordem
atividades:    [{"id", "nome", "cor"}, ...]   na ordem
cliente_ids:   [ids]
atividade_ids: [ids]
```

E mantém `cliente`, `atividade`, `cliente_id`, `atividade_id`, `cor`, `cor_atividade`
apontando pro principal (nada que já lê esses campos quebra).

## Interfaces

- `entradas.iniciar(conn, clientes, atividades, descricao, agora)`, `criar_manual(...)` e
  `editar(..., cliente_id=, atividade_id=)` aceitam **int, None ou lista** nos campos de
  cliente/atividade. Lista vazia de atividades é erro (`ValueError("escolha pelo menos uma atividade")`).
- `entradas.rotulo_clientes(e)` → "Sem cliente" | "Pessoal" | "Pessoal + NP Hub".
  `entradas.rotulo_atividades(e)` → "Reunião" | "Reunião + Edição".
  `entradas.rotulo(e)` → `f"{clientes} · {atividades}"`.
- `entradas.recentes(conn, n)` agrupa por **combinação** (mesmos clientes e mesmas
  atividades, na mesma ordem) e devolve `cliente_ids`, `atividade_ids` além dos campos atuais.
- `gargalos.por_cliente` / `por_atividade`: cada item da lista recebe os minutos inteiros.
  `gargalos.combinados(entradas)` → `[(rotulo, minutos, cor)]` só das entradas com mais de
  um cliente ou mais de uma atividade. `leituras()` ganha "Combinado: ..." (até 3 itens).
- `resumo.texto`: linha "Combinado: Pessoal + NP Hub 1h" depois da linha por atividade,
  quando houver; "Ainda rodando" usa `rotulo(e)`.
- `exportar.csv_texto`: colunas cliente/atividade com nomes unidos por " + ".
- D-Bus: novo método `IniciarVarios(ai cliente_ids, ai atividade_ids, s descricao) → i`.
  `Iniciar(i, i, s)` continua existindo. JSON de `EntradaAtual`/`EntradaMudou`/`Recentes`
  carrega as listas.
- App GTK: widget `SeletorMultiplo` (botão com popover de caixas de marcação; rótulo
  "Pessoal +1"), usado no cartão da aba Hoje e no diálogo de entrada. Linhas da lista e
  legenda usam `rotulo(e)`.
- Extensão: submenus Cliente e Atividade viram listas de marcação (ornamento de check);
  rótulo do submenu "Cliente: Pessoal +1"; Iniciar, Trocar e Recentes chamam
  `IniciarVarios`; barra mostra "▶ 00:42 · Pessoal +1".

## Fora do escopo

Celular, Telegram como controle remoto, pomodoro, lembrete antes de 12 h.
