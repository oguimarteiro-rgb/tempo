#!/usr/bin/env bash
# Sobe um GNOME Shell sem janela (--devkit) num barramento e num dconf próprios, com um serviço
# Tempo de teste rodando uma tarefa, e confere no log que a extensão criou o cartão sem erro.
# Pré-requisito: a extensão instalada em ~/.local/share/gnome-shell/extensions (./instalar.sh).
# Demora de 30 s a 3 min (o Shell headless às vezes demora pra subir). Rodar: bash app/tests/teste_extensao_headless.sh
set -u
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
T="$(mktemp -d /tmp/tempo-headless-XXXX)"
MARCADOR="${XDG_RUNTIME_DIR:-/run/user/$UID}/gnome-shell-disable-extensions"
# O Shell cria esse marcador ao subir e apaga ao terminar; morto no meio, ele desligaria as
# extensões do próximo login. Garantir que não sobra, e matar o que ficou órfão.
limpar() {
  rm -f "$MARCADOR"
  [ -f "$T/pids" ] && xargs -r kill < "$T/pids" 2>/dev/null
  true
}
trap limpar EXIT

export RAIZ T
# XDG_CONFIG_HOME isolado: o dconf do barramento de teste não escreve no dconf real.
XDG_CONFIG_HOME="$T/config" TEMPO_DIR="$T" TEMPO_RUNTIME_DIR="$T" PYTHONPATH="$RAIZ/app" GTK_A11Y=none \
timeout 220 dbus-run-session -- bash -c '
python3 -m tempo.app > "$T/servico.log" 2>&1 & echo $! >> "$T/pids"
S="gdbus call --session --dest br.com.oguim.Tempo --object-path /br/com/oguim/Tempo/Servico --method br.com.oguim.Tempo.Servico"
for i in $(seq 1 10); do $S.Versao >/dev/null 2>&1 && break; sleep 1; done
$S.Iniciar 0 1 "teste headless" >/dev/null
gsettings set org.gnome.shell enabled-extensions "[\"tempo@oguim.com\"]"
gsettings set org.gnome.shell disable-user-extensions false
echo "$(date +%T) shell sobe" >> "$T/passos.log"
gnome-shell --devkit > "$T/shell.log" 2>&1 & echo $! >> "$T/pids"
for i in $(seq 1 60); do grep -qE "Tempo: |JS ERROR|tempo@oguim.com: Error" "$T/shell.log" && break; sleep 1; done
echo "$(date +%T) cartão 1 visto" >> "$T/passos.log"
sleep 3
$S.Parar >/dev/null; echo "$(date +%T) parou" >> "$T/passos.log"; sleep 3
$S.Iniciar 0 2 "segunda" >/dev/null; echo "$(date +%T) iniciou 2" >> "$T/passos.log"; sleep 4
xargs -r kill < "$T/pids"; sleep 2; : > "$T/pids"
' >/dev/null 2>&1

LOG="$T/shell.log"
cartoes=$(grep -c "Tempo: cartão" "$LOG")
erros=$(grep -cE "JS ERROR|JS WARNING|tempo@oguim\.com/.*\.js:[0-9]+|tempo@oguim.*(Error|CRITICAL)" "$LOG")
if [ "$cartoes" -ge 2 ] && [ "$erros" -eq 0 ]; then
  echo "extensão headless ok (cartão apareceu $cartoes vezes, log em $LOG)"
else
  echo "FALHOU: cartões=$cartoes erros=$erros, veja $LOG"
  grep -nE "JS ERROR|tempo@oguim|Tempo:" "$LOG" | head -20
  exit 1
fi
