#!/usr/bin/env bash
# Sobe um GNOME Shell sem janela (--devkit) num barramento próprio, com um serviço Tempo de teste
# rodando uma tarefa, e confere no log que a extensão criou o cartão sem erro.
# Pré-requisito: a extensão instalada em ~/.local/share/gnome-shell/extensions e habilitada.
# Demora uns 90 s. Rodar: bash app/tests/teste_extensao_headless.sh
set -u
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
T="$(mktemp -d /tmp/tempo-headless-XXXX)"
MARCADOR="${XDG_RUNTIME_DIR:-/run/user/$UID}/gnome-shell-disable-extensions"
# O Shell cria esse marcador ao subir e apaga ao terminar; morto no meio, ele desligaria as
# extensões do próximo login. Garantir que não sobra.
limpar() { rm -f "$MARCADOR"; }
trap limpar EXIT

timeout 120 dbus-run-session -- bash -c '
export TEMPO_DIR="'"$T"'" TEMPO_RUNTIME_DIR="'"$T"'" PYTHONPATH="'"$RAIZ"'/app" GTK_A11Y=none
python3 -m tempo.app > "'"$T"'/servico.log" 2>&1 & SP=$!
S="gdbus call --session --dest br.com.oguim.Tempo --object-path /br/com/oguim/Tempo/Servico --method br.com.oguim.Tempo.Servico"
for i in $(seq 1 10); do $S.Versao >/dev/null 2>&1 && break; sleep 1; done
$S.Iniciar 0 1 "teste headless" >/dev/null
gnome-shell --devkit > "'"$T"'/shell.log" 2>&1 & GP=$!
for i in $(seq 1 80); do grep -q "Tempo: cartão\|tempo@oguim.com: Error" "'"$T"'/shell.log" && break; sleep 1; done
sleep 3
$S.Parar >/dev/null; sleep 3
$S.Iniciar 0 2 "segunda" >/dev/null; sleep 4
kill $GP; sleep 2; kill $SP
' >/dev/null 2>&1

LOG="$T/shell.log"
cartoes=$(grep -c "Tempo: cartão" "$LOG")
erros=$(grep -E "tempo@oguim.com.*(Error|CRITICAL)|JS ERROR.*tempo@oguim" "$LOG" | wc -l)
if [ "$cartoes" -ge 2 ] && [ "$erros" -eq 0 ]; then
  echo "extensão headless ok (cartão apareceu $cartoes vezes, log em $LOG)"
else
  echo "FALHOU: cartões=$cartoes erros=$erros, veja $LOG"
  grep -nE "tempo@oguim|Tempo:" "$LOG" | head -20
  exit 1
fi
