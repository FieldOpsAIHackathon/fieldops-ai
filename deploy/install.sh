#!/usr/bin/env bash
# Install FieldOps as systemd user services that start at boot (lingering keeps them up without a login).
# Units are copied, not symlinked: scripts/deploy_gb10.sh (CI) rewrites fieldops-api.service in place and
# owns it once deployment is enabled; this script never overwrites an API unit that CI installed.
#   bash deploy/install.sh            install + enable + start
#   systemctl --user status 'fieldops*'
#   journalctl --user -u fieldops-api -f
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p ~/.config/systemd/user
for unit in "$here"/systemd/*; do
  dest=~/.config/systemd/user/"$(basename "$unit")"
  if [[ "$(basename "$unit")" == fieldops-api.service && -f ~/.local/share/fieldops/current/REVISION ]]; then
    echo "keeping CI-deployed $(basename "$unit")"; continue
  fi
  rm -f "$dest" && cp "$unit" "$dest"
done
loginctl show-user "$USER" -p Linger | grep -q yes || sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable fieldops.target
systemctl --user start fieldops.target
systemctl --user --no-pager status 'fieldops*' | grep -E "●|Active:"
