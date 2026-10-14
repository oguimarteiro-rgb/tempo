#!/usr/bin/bash
# Instala o Tempo para o usuário atual. Idempotente. Não usa sudo: imprime o dnf se faltar pacote.
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/tempo"
BIN="$HOME/.local/bin/tempo"
EXT_UUID="tempo@oguim.com"
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"

echo "== Tempo: instalação em $HOME"

if [ -z "${TEMPO_SEM_GNOME:-}" ]; then
  faltando=()
  for p in gtk4 libadwaita python3-gobject; do rpm -q "$p" >/dev/null 2>&1 || faltando+=("$p"); done
  if [ ${#faltando[@]} -gt 0 ]; then
    echo "Faltam pacotes do sistema. Rode no Terminal e depois execute este script de novo:"
    echo "  sudo dnf install ${faltando[*]}"
    exit 1
  fi
fi

echo "-- app"
mkdir -p "$DEST/app" "$HOME/.local/bin"
rm -rf "$DEST/app/tempo"
cp -r "$RAIZ/app/tempo" "$DEST/app/tempo"
cat > "$BIN" <<EOF
#!/usr/bin/bash
export PYTHONPATH="$DEST/app\${PYTHONPATH:+:\$PYTHONPATH}"
# O app já nasce como serviço (IS_SERVICE); o GLib não reconhece --gapplication-service nesse caso.
args=()
for a in "\$@"; do [ "\$a" = "--gapplication-service" ] || args+=("\$a"); done
exec python3 -m tempo.app "\${args[@]}"
EOF
chmod +x "$BIN"

echo "-- ícone e menu"
mkdir -p "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/scalable/apps" \
         "$HOME/.local/share/dbus-1/services" "$HOME/.config/autostart"
cp "$RAIZ/dados/br.com.oguim.Tempo.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/"
sed "s|^Exec=tempo|Exec=$BIN|" "$RAIZ/dados/br.com.oguim.Tempo.desktop" > "$HOME/.local/share/applications/br.com.oguim.Tempo.desktop"
sed "s|@BIN@|$BIN|" "$RAIZ/dados/br.com.oguim.Tempo.service" > "$HOME/.local/share/dbus-1/services/br.com.oguim.Tempo.service"
{ sed "s|^Exec=tempo|Exec=$BIN --gapplication-service|; /^DBusActivatable/d" "$RAIZ/dados/br.com.oguim.Tempo.desktop"; echo "X-GNOME-Autostart-enabled=true"; } \
  > "$HOME/.config/autostart/br.com.oguim.Tempo.desktop"

echo "-- extensão"
mkdir -p "$EXT_DIR"
cp -r "$RAIZ/extensao/." "$EXT_DIR/"
glib-compile-schemas "$EXT_DIR/schemas/"

if [ -z "${TEMPO_SEM_GNOME:-}" ]; then
  gnome-extensions enable "$EXT_UUID" 2>/dev/null || echo "   (ative a extensão após relogar: gnome-extensions enable $EXT_UUID)"
  update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
  gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
  echo "-- verificação"
  if versao=$(timeout 10 gdbus call --session -d br.com.oguim.Tempo -o /br/com/oguim/Tempo/Servico -m br.com.oguim.Tempo.Servico.Versao 2>/dev/null); then
    echo "Tempo instalado, versão ${versao//[\(\)\',]/}"
  else
    echo "Serviço não respondeu. Faça logout e login para o GNOME carregar a extensão, depois rode: $BIN --gapplication-service &"
  fi
  echo "No Wayland a extensão só aparece depois de sair e entrar de novo na sessão."
else
  echo "Tempo instalado (modo teste, sem GNOME)."
fi
