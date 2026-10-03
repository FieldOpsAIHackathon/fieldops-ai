#!/usr/bin/env bash
# Install a CI artifact into an isolated release directory on the GB10.
set -Eeuo pipefail

archive=${1:?Usage: deploy_gb10.sh ARCHIVE COMMIT_SHA}
revision=${2:?Usage: deploy_gb10.sh ARCHIVE COMMIT_SHA}
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo "Expected a full commit SHA" >&2; exit 1; }
root=${FIELDOPS_DEPLOY_ROOT:-"$HOME/.local/share/fieldops"}
unit_dir=${FIELDOPS_UNIT_DIR:-"$HOME/.config/systemd/user"}
python=${FIELDOPS_PYTHON:-/usr/bin/python3}
health_url=${FIELDOPS_HEALTH_URL:-http://127.0.0.1:8765/status}
service=fieldops-api.service
"$python" -c 'import sys; assert sys.version_info >= (3, 12), "Python 3.12+ required"'
systemctl --user show-environment > /dev/null
mkdir -p "$root/releases" "$root/shared" "$unit_dir"
exec 9>"$root/deploy.lock"
flock -n 9 || { echo "Another deployment is active" >&2; exit 1; }
[[ ! -e "$root/current" || -L "$root/current" ]] || { echo "current must be a symlink" >&2; exit 1; }
old=$(readlink "$root/current" || true)

# Never stop an API started by a teammate outside this managed service.
if [[ -z "$old" ]]; then
  "$python" - <<'PY'
import socket
with socket.socket() as probe:
    if probe.connect_ex(("127.0.0.1", 8765)) == 0:
        raise SystemExit("Port 8765 is occupied. Coordinate stopping the existing API before first deployment.")
PY
fi

release=$(mktemp -d "$root/releases/$revision.XXXXXX")
"$python" - "$archive" "$release" <<'PY'
import sys, tarfile
with tarfile.open(sys.argv[1], "r:gz") as archive:
    archive.extractall(sys.argv[2], filter="data")
PY
for file in fieldops/api.py dashboard/index.html dashboard/data/timeline.json deploy/fieldops-api.service; do
  [[ -f "$release/$file" ]] || { echo "Artifact missing $file" >&2; exit 1; }
done

# Data survives code deployments. Initialize only a new store, never overwrite it.
if [[ ! -e "$root/shared/fieldops.db" ]]; then
  (cd "$release" && "$python" -m fieldops.store --db "$root/shared/fieldops.db" --load data/season.csv)
fi
for file in fieldops.db alerts.jsonl replay_state.json; do
  [[ ! -e "$release/data/$file" ]] || { echo "Artifact contains runtime file $file" >&2; exit 1; }
  ln -s "$root/shared/$file" "$release/data/$file"
done
[[ ! -e "$release/dashboard/data/live.json" ]] || { echo "Artifact contains live feed" >&2; exit 1; }
ln -s "$root/shared/live.json" "$release/dashboard/data/live.json"
printf '%s\n' "$revision" > "$release/REVISION"

old_unit="$release/previous-api.service"
if [[ -f "$unit_dir/$service" ]]; then cp "$unit_dir/$service" "$old_unit"; fi
switch_current() {
  "$python" - "$root" "$1" <<'PY'
import os, sys
from pathlib import Path
root, target = Path(sys.argv[1]), sys.argv[2]
pending = root / f".current-{os.getpid()}"
pending.symlink_to(target)
os.replace(pending, root / "current")
PY
}
rollback() {
  local status=$?
  trap - ERR INT TERM
  set +e
  echo "Deployment failed; restoring previous release" >&2
  if [[ -f "$old_unit" ]]; then cp "$old_unit" "$unit_dir/$service"; else rm -f "$unit_dir/$service"; fi
  if [[ -n "$old" ]]; then
    switch_current "$old"
    systemctl --user daemon-reload
    systemctl --user restart "$service"
  else
    systemctl --user stop "$service"
    rm -f "$root/current"
    systemctl --user daemon-reload
  fi
  exit "$status"
}
trap rollback ERR
trap 'false' INT TERM

"$python" - "$release/deploy/fieldops-api.service" "$unit_dir/$service" "$root" "$python" <<'PY'
import sys
from pathlib import Path
def quote(value):
    return '"' + str(Path(value).resolve()).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
working_dir = str(Path(sys.argv[3]).resolve() / 'current').replace('%', '%%')
text = Path(sys.argv[1]).read_text().replace('@ROOT@', working_dir).replace('@PYTHON@', quote(sys.argv[4]))
Path(sys.argv[2]).write_text(text)
PY
switch_current "$release"
systemctl --user daemon-reload
systemctl --user restart "$service"
"$python" - "$health_url" <<'PY'
import json, subprocess, sys, time, urllib.request
for attempt in range(20):
    active = subprocess.run(["systemctl", "--user", "is-active", "--quiet", "fieldops-api.service"]).returncode == 0
    try:
        with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
            status = json.load(response)
        if active and status.get("blocks") and status.get("as_of"):
            print("API health check passed")
            break
    except (OSError, ValueError):
        pass
    time.sleep(1)
else:
    raise SystemExit("API health check failed")
PY
systemctl --user enable "$service"
trap - ERR INT TERM
echo "Deployed $revision to $release"
echo "Open $root/current/dashboard/index.html on the GB10"
