# Tempo

Rastreador de tempo nativo do GNOME, com timer manual no estilo Toggl Track.
Um indicador na barra de cima inicia e para o cronômetro, e uma janela GTK4 com
libadwaita mostra para onde o tempo está vazando (gráficos e leituras automáticas).
Roda local, sem conta e sem nuvem: os dados ficam num arquivo SQLite no seu PC.

![Tempo](docs/tela.png)

> A captura `docs/tela.png` será adicionada depois que o [roteiro manual](docs/roteiro-manual.md) for executado.

## Instalação

```bash
git clone https://github.com/oguimarteiro-rgb/tempo.git ~/tempo && ~/tempo/instalar.sh
```

Depois, **saia da sessão e entre de novo** (logout/login). No Wayland, o GNOME
Shell só carrega uma extensão nova ao iniciar a sessão.

O instalador nunca pede sudo. Se faltar GTK4, libadwaita ou python3-gobject, ele
imprime o comando `dnf` para você rodar no Terminal de verdade e depois continua.

## Uso

- O indicador fica na barra de cima: ícone de relógio parado, ou `▶ 00:42 · Cliente` rodando.
- **Super+T** abre o menu do indicador.
- No menu: **Iniciar / Parar**, **Trocar para …** (aparece enquanto roda), campo de
  descrição, seletores **Cliente** e **Atividade**, os 5 **Recentes** (um clique inicia)
  e **Abrir relatório**.
- A janela do relatório tem três abas:
  - **Hoje**: entradas do dia, edição, apagar, entrada manual e total.
  - **Gargalos**: 3 gráficos de barras (cliente, atividade, dia da semana), leituras
    automáticas em texto e **Exportar CSV** do período.
  - **Cadastros**: clientes e atividades (adicionar, renomear, cor, arquivar).
- O atalho é editável nas preferências da extensão, no formato `<Super>t`
  (precisa de pelo menos uma tecla modificadora).

## Dados e backup

- Banco: `~/.local/share/tempo/tempo.db`
- Backup diário automático: `~/.local/share/tempo/backup/` (guarda os 7 últimos)

## PC novo

1. Instale como acima (clone + `instalar.sh`).
2. Antes de usar, copie o seu `tempo.db` (do backup) para `~/.local/share/tempo/`.
3. Saia e entre na sessão.

## Desenvolvimento

```bash
cd app && python3 -m pytest -q          # 48 testes
app/tests/test_instalar.sh              # instalador com HOME falso
timeout 90 env GTK_A11Y=none dbus-run-session -- python3 app/tests/smoke_janela.py
# idem para smoke_gargalos.py e smoke_cadastros.py
```

Estrutura: `app/tempo/` (serviço D-Bus, banco, janela), `extensao/` (indicador do
GNOME Shell), `instalar.sh`, `docs/`.

## Limites conhecidos

- A extensão só aparece depois de sair e entrar na sessão.
- `shell-version` cobre o GNOME 48 a 51. Um GNOME mais novo pede ajuste do
  `metadata.json` e nova instalação.
- Reinstalar não reinicia um serviço que já está rodando. Para testar uma versão
  nova, saia e entre na sessão ou rode `pkill -f tempo.app`.
- Entradas que atravessam a meia-noite não podem ser editadas pela aba Hoje.
- A janela ainda não detecta que a extensão foi desativada (por exemplo, após
  atualizar o GNOME). Nesse caso, rode `~/tempo/instalar.sh` de novo.

## Fase 2 (planejada, não construída)

- Música de foco via MPRIS (`playerctl`) ao iniciar o timer.
- Cartão flutuante do timer no canto inferior direito da tela, arrastável e fechável.
- Identidade visual do @oguim.criativo.

## Licença

[MIT](LICENSE).
