#!/usr/bin/bash
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
FAKE="$(mktemp -d)"
trap 'rm -rf "$FAKE"' EXIT
HOME="$FAKE" TEMPO_SEM_GNOME=1 "$RAIZ/instalar.sh" >/dev/null
for f in \
  .local/share/tempo/app/tempo/app.py \
  .local/bin/tempo \
  .local/share/applications/br.com.oguim.Tempo.desktop \
  .local/share/icons/hicolor/scalable/apps/br.com.oguim.Tempo.svg \
  .local/share/dbus-1/services/br.com.oguim.Tempo.service \
  .config/autostart/br.com.oguim.Tempo.desktop \
  .local/share/gnome-shell/extensions/tempo@oguim.com/extension.js \
  .local/share/gnome-shell/extensions/tempo@oguim.com/schemas/gschemas.compiled \
  .config/systemd/user/tempo-resumo.service \
  .config/systemd/user/tempo-resumo.timer \
  .config/tempo/resumo.env ; do
  [ -e "$FAKE/$f" ] || { echo "FALTOU $f"; exit 1; }
done
grep -q "Exec=$FAKE/.local/bin/tempo --gapplication-service" "$FAKE/.local/share/dbus-1/services/br.com.oguim.Tempo.service"
[ -x "$FAKE/.local/bin/tempo" ]

falha() { echo "FALHOU: $*"; exit 1; }

# lançador: python do sistema fixo, sem argumento abre a janela pelo D-Bus
L="$FAKE/.local/bin/tempo"
bash -n "$L" || falha "lançador com erro de sintaxe"
grep -q "/usr/bin/python3 -m tempo.app" "$L" || falha "lançador sem /usr/bin/python3"
grep -q "gapplication launch br.com.oguim.Tempo" "$L" || falha "lançador sem gapplication launch"
grep -q -- '--gapplication-service' "$L" || falha "lançador sem o filtro de --gapplication-service"
grep -q "PYTHONPATH=\"$FAKE/.local/share/tempo/app" "$L" || falha "lançador sem PYTHONPATH"
# executa o filtro de verdade com /usr/bin/python3 e gapplication trocados por stubs que ecoam
mkdir -p "$FAKE/stub"
printf '#!/usr/bin/bash\necho "py:$*"\n' > "$FAKE/stub/python3"
printf '#!/usr/bin/bash\necho "gapp:$*"\n' > "$FAKE/stub/gapplication"
chmod +x "$FAKE/stub/python3" "$FAKE/stub/gapplication"
sed -e "s|/usr/bin/python3|$FAKE/stub/python3|" -e "s|/usr/bin/gapplication|$FAKE/stub/gapplication|" "$L" > "$FAKE/stub/tempo"
chmod +x "$FAKE/stub/tempo"
[ "$("$FAKE/stub/tempo")" = "gapp:launch br.com.oguim.Tempo" ] || falha "sem argumento não chamou gapplication launch"
[ "$("$FAKE/stub/tempo" --gapplication-service)" = "py:-m tempo.app" ] || falha "filtro com o argumento sozinho"
[ "$("$FAKE/stub/tempo" -x --gapplication-service -y)" = "py:-m tempo.app -x -y" ] || falha "filtro no meio"
[ "$("$FAKE/stub/tempo" --outro)" = "py:-m tempo.app --outro" ] || falha "outros argumentos não passaram adiante"
[ "$("$FAKE/stub/tempo" resumo)" = "py:-m tempo.resumo" ] || falha "tempo resumo não chamou o módulo"
grep -q "ExecStart=$FAKE/.local/bin/tempo resumo-telegram" "$FAKE/.config/systemd/user/tempo-resumo.service" || falha "service sem ExecStart certo"
grep -q "OnCalendar=Mon..Fri 18:00" "$FAKE/.config/systemd/user/tempo-resumo.timer" || falha "timer sem horário"
# resumo-telegram: manda o texto pro comando configurado; sem texto não manda; sem comando sai limpo
printf '#!/usr/bin/bash\necho "enviado:$1"\n' > "$FAKE/stub/enviar"; chmod +x "$FAKE/stub/enviar"
printf 'ENVIAR_CMD="%s"\n' "$FAKE/stub/enviar" > "$FAKE/.config/tempo/resumo.env"
printf '#!/usr/bin/bash\n[ "$2" = tempo.resumo ] && echo "Tempo de hoje: 1h"\n' > "$FAKE/stub/python3"
[ "$(HOME="$FAKE" "$FAKE/stub/tempo" resumo-telegram)" = "enviado:Tempo de hoje: 1h" ] || falha "resumo-telegram não enviou o texto"
printf '#!/usr/bin/bash\n:\n' > "$FAKE/stub/python3"
[ -z "$(HOME="$FAKE" "$FAKE/stub/tempo" resumo-telegram)" ] || falha "resumo vazio mandou algo"
rm "$FAKE/.config/tempo/resumo.env"
HOME="$FAKE" "$FAKE/stub/tempo" resumo-telegram | grep -q "sem comando de envio" || falha "sem resumo.env não avisou"

# autostart: liga o serviço no login, sem DBusActivatable
A="$FAKE/.config/autostart/br.com.oguim.Tempo.desktop"
grep -qx "X-GNOME-Autostart-enabled=true" "$A" || falha "autostart sem X-GNOME-Autostart-enabled"
! grep -q "DBusActivatable" "$A" || falha "autostart com DBusActivatable"
[ "$(grep '^Exec=' "$A")" = "Exec=$FAKE/.local/bin/tempo --gapplication-service" ] || falha "Exec do autostart"
# menu de aplicativos: exatamente uma linha Exec, sem argumento
D="$FAKE/.local/share/applications/br.com.oguim.Tempo.desktop"
[ "$(grep -c '^Exec=' "$D")" = 1 ] || falha "desktop com mais de um Exec"
[ "$(grep '^Exec=' "$D")" = "Exec=$FAKE/.local/bin/tempo" ] || falha "Exec do desktop"

# extensão sem órfãos: arquivo que não existe mais na fonte some na reinstalação
touch "$FAKE/.local/share/gnome-shell/extensions/tempo@oguim.com/orfao.js"
# idempotente
HOME="$FAKE" TEMPO_SEM_GNOME=1 "$RAIZ/instalar.sh" >/dev/null
[ ! -e "$FAKE/.local/share/gnome-shell/extensions/tempo@oguim.com/orfao.js" ] || falha "órfão ficou na extensão"
[ -e "$FAKE/.local/share/gnome-shell/extensions/tempo@oguim.com/schemas/gschemas.compiled" ] || falha "schema sumiu"
echo "instalar.sh ok"
