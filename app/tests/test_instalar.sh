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
  .local/share/gnome-shell/extensions/tempo@oguim.com/schemas/gschemas.compiled ; do
  [ -e "$FAKE/$f" ] || { echo "FALTOU $f"; exit 1; }
done
grep -q "Exec=$FAKE/.local/bin/tempo --gapplication-service" "$FAKE/.local/share/dbus-1/services/br.com.oguim.Tempo.service"
[ -x "$FAKE/.local/bin/tempo" ]
# idempotente
HOME="$FAKE" TEMPO_SEM_GNOME=1 "$RAIZ/instalar.sh" >/dev/null
echo "instalar.sh ok"
