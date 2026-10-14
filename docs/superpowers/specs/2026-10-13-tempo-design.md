# Tempo: rastreador de tempo nativo do GNOME

Data: 2026-10-13. Autor: oguim com Claude. Estado: aprovado em conversa, aguardando revisão do spec.

## Objetivo

Um app de PC, fora do navegador, que mede quanto tempo o oguim gasta em cada
tarefa (estilo Toggl Track, timer manual) e mostra onde o tempo vaza. Vive num
repositório público no GitHub para reinstalar em qualquer PC formatado com um
comando.

Não é: rastreio automático de janelas (ActivityWatch), ferramenta de equipe,
ferramenta de faturamento.

## Decisões tomadas

| Pergunta | Decisão |
| --- | --- |
| Captura | Manual: play, descreve, stop. |
| Pra que serve o relatório | Achar gargalos. Cada entrada leva cliente/projeto e tipo de atividade. |
| Onde mora o popup | Indicador na barra de cima do GNOME (extensão do Shell). |
| Relatório | Janela nativa GTK4 + libadwaita, não navegador. |
| Engenharia reversa (REA) | Descartada. O Toggl Linux já era aberto e o comportamento é público. |
| Música de foco | Fase 2, controlando playlists do player via MPRIS. |

## Arquitetura

Duas peças, um banco:

```
GNOME Shell                       sessão do usuário
┌──────────────────┐   D-Bus     ┌────────────────────────────┐
│ extensao/        │ ──────────▶ │ app/ (Python)              │
│ indicador + menu │ ◀────────── │ serviço D-Bus + banco +    │
│ (JavaScript)     │  sinais     │ janela GTK4/libadwaita     │
└──────────────────┘             └──────────┬─────────────────┘
                                            ▼
                               ~/.local/share/tempo/tempo.db (SQLite)
```

- A extensão não tem lógica de negócio. Cada clique vira uma chamada D-Bus
  (`Iniciar`, `Parar`, `Trocar`, `EntradaAtual`, `Recentes`). Ela assina o
  sinal `EntradaMudou` pra atualizar o texto da barra.
- O serviço D-Bus (`br.com.oguim.Tempo`) é o único que escreve no banco. A
  janela GTK é o mesmo processo Python; o serviço sobe com a sessão e a janela
  abre sob demanda.
- Se o serviço não estiver rodando quando a extensão chamar, o D-Bus ativa ele
  sozinho (arquivo `.service` de ativação).

## Seção 1: dados

Banco SQLite em `~/.local/share/tempo/tempo.db`. Três tabelas.

**clientes**: id, nome, cor (hex), arquivado (bool). Exemplos: Viretto,
Casttema, Hornero, NP Hub, oguim.criativo, Pessoal.

**atividades**: id, nome, cor, arquivado. Lista inicial: Edição, Captação,
Reunião, Roteiro, Administrativo, Estudo, Deslocamento.

**entradas**: id, inicio (ISO 8601 com fuso), fim (nulo enquanto roda),
cliente_id, atividade_id, descricao (texto livre, opcional).

Regras:
- No máximo **uma** entrada com `fim` nulo. Garantido por índice único parcial
  e pela camada de serviço.
- Iniciar com uma entrada rodando encerra a atual no mesmo instante em que a
  nova começa. Sem buraco, sem sobreposição.
- **Entrada esquecida**: ao abrir (serviço ou janela), se existe entrada aberta
  iniciada em sessão anterior, perguntar: encerrar no horário de início,
  encerrar agora, ou descartar. Entrada passando de 12h gera aviso no
  indicador.
- Exportação CSV de qualquer período (inicio, fim, duracao_min, cliente,
  atividade, descricao).
- Cópia diária automática do banco em `~/.local/share/tempo/backup/`, guarda 7.

## Seção 2: indicador na barra

Estados:
- Parado: ícone de relógio, sem texto.
- Rodando: `▶ 00:42 · Casttema`, atualizado a cada segundo, pontinho na cor do
  cliente.
- Serviço fora: ícone cinza, item "Reconectar".

Menu ao clicar:
1. Botão grande Iniciar / Parar.
2. Campo de descrição (opcional).
3. Seletores Cliente e Atividade, pré-preenchidos com os últimos usados.
4. Recentes: 5 últimas combinações cliente · atividade, um clique inicia.
5. Abrir relatório.

Atalho global padrão **Super+T** abre o menu. Configurável nas preferências da
extensão.

## Seção 3: janela do app

GTK4 + libadwaita, três abas na barra de título.

**Hoje**: lista das entradas do dia (horário, duração, cliente, atividade,
descrição). Clique edita qualquer campo ou apaga. Botão de entrada manual.
Total do dia no rodapé.

**Gargalos**: seletor de período (esta semana, semana passada, este mês,
personalizado). Três gráficos de barras desenhados em GTK (Cairo/Gtk.Snapshot),
cores seguem o tema claro/escuro: por cliente, por atividade, por dia da
semana. Abaixo, bloco de **leituras automáticas** em texto, por exemplo:
- "Administrativo subiu 40% em relação à semana passada."
- "Hornero: 6h20 em Edição no período."
- "Terça foi o dia mais fragmentado: 14 trocas de tarefa."
Botão Exportar CSV do período.

**Cadastros**: clientes e atividades, com adicionar, renomear, trocar cor,
arquivar. Arquivado some do menu da barra e fica no histórico.

### Leituras automáticas (regras iniciais)

Calculadas no período escolhido contra o período anterior de mesmo tamanho:
1. Atividade que mais cresceu em proporção (limiar 25%).
2. Cliente com mais horas e sua atividade dominante.
3. Dia com mais trocas de tarefa (contagem de entradas).
4. Horas totais e média por dia útil.
Cada regra é uma função pura testável que recebe entradas e devolve texto ou
nada.

## Seção 4: repositório e instalação

Repo público `oguimarteiro-rgb/tempo`, licença MIT.

```
tempo/
  app/            Python: servico.py, banco.py, gargalos.py, janela/, exportar.py
  extensao/       JavaScript: metadata.json, extension.js, prefs.js
  instalar.sh     deixa tudo funcionando num PC novo
  tests/          pytest do app Python
  docs/superpowers/specs/   este arquivo
```

`instalar.sh`, nesta ordem:
1. Dependências via dnf (gtk4, libadwaita, python3-gobject). Única parte com
   sudo: imprime o comando pra rodar no Terminal e continua depois de
   confirmado (`rpm -q`).
2. Copia o app pra `~/.local/share/tempo` e cria `.desktop` + ícone no menu.
3. Instala a extensão em `~/.local/share/gnome-shell/extensions/` e ativa com
   `gnome-extensions enable`.
4. Registra ativação D-Bus (`~/.local/share/dbus-1/services/`) e autostart.
5. Verifica chamando o serviço e imprime "Tempo instalado, versão X".

Reinstalação em PC formatado: clonar, `./instalar.sh`, copiar `tempo.db` do
backup.

## Seção 5: erros e testes

Erros:
- Serviço caiu: indicador cinza, "Reconectar". Entrada em andamento continua
  válida porque o início já está no banco.
- Timer esquecido: pergunta da seção 1 e aviso de 12h.
- GNOME atualizou e desativou a extensão: a janela detecta e orienta a rodar
  `./instalar.sh` de novo.
- Banco corrompido: restaurar do backup diário.

Testes:
- App Python com pytest, TDD por fatia. Núcleo (banco, regra de uma-rodando,
  gargalos, exportação) testado sem interface, SQLite em memória. Serviço D-Bus
  testado por chamada real num barramento de sessão de teste.
- Extensão: roteiro manual de 10 passos (iniciar, trocar, parar, reconectar,
  atalho) executado e registrado com captura de tela antes de declarar pronto.
- `instalar.sh` testado com `HOME` falso, sem tocar o sistema.

## Fase 2 (fora deste spec): música de foco

Item "Tocar foco" no menu da barra. Ao iniciar uma entrada, manda o player
configurado (VLC, Spotify) tocar uma playlist via MPRIS (`playerctl`); ao
parar, pausa. Alternativa: pasta local de áudios livres tocada em loop pelo
próprio app. Nunca usar faixas do Brain.fm.

## Fontes consultadas

- Toggl Desktop (arquivado): https://github.com/toggl-open-source/toggldesktop
- Time Tracker for GNOME: https://alternativeto.net/software/time-tracker-for-gnome/about
- ActivityWatch: https://github.com/ActivityWatch
- Super Productivity: https://alternativeto.net/software/toggl/?p=17
