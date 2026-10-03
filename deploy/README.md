# CI and GB10 deployment

`.github/workflows/ci-deploy.yml` checks pull requests and every push to `main`,
including merges. Manual runs are supported. The required check to select in branch
protection is **Replay and integration checks**.

Checks run on GitHub's Ubuntu runner with Python 3.12 and Node 22. They verify
decision self-tests, SQLite re-ingest, CSV/store parity, committed replay freshness,
JS/JSON equality, a real HTTP `/status` request, local HTML assets and JS syntax.
They use temporary state, make no model calls and send no alerts. Run locally:

```bash
python3 scripts/ci_check.py
bash -n scripts/deploy_gb10.sh
```

When the decision code, config or season changes, regenerate and commit both
timeline files with `python3 -m fieldops.decide --csv --replay`. CI checks them;
it does not push generated changes back to the branch.

## Enable deployment once

The verified SSH target is `dell@promaxgb10-887f.local` (`172.20.65.164` on
October 3; DHCP may change it). Local connection metadata is in the parent
workspace's `.env`, outside the project repository. A runner on that machine
downloads the tested artifact from GitHub. No public SSH endpoint is needed.
Deployment needs internet; the installed replay/API continues running offline.

1. The repository owner registers a **Linux ARM64 self-hosted runner** on the
   GB10 and adds the custom label **fieldops-gb10**. Use a normal login account,
   not root, and the same account that will own the API and Telegram settings.
   Follow [GitHub's registration instructions](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners).
   Run the runner from that user's logged-in terminal for the hackathon (`./run.sh`).
2. Confirm `/usr/bin/python3` is version 3.12+, `flock` exists, and
   `systemctl --user show-environment` works under that account. Keep the user's
   session logged in. For unattended reboot/logout operation, enable lingering
   for that account and install the runner service with a working user bus.
3. Coordinate stopping any manually started FieldOps API on port 8765 before
   the first deployment. The script refuses to replace an unmanaged listener.
   The existing model server and OpenShell installation stay independently managed.
4. Keep Telegram credentials in `~/.config/fieldops.env`, as `fieldops.alert`
   expects. The app does not currently read `.env.local`. Credentials and runtime
   state are excluded from the deployment artifact.
5. Set repository Actions variable **FIELDOPS_DEPLOY_ENABLED=true**, then run
   **Check and deploy FieldOps** on `main`. Future successful main pushes deploy
   automatically. Without this variable the check/artifact job runs and deploy skips.

SSH access, ARM64 architecture, Python 3.12.3 and user systemd were verified on
the GB10. The current collaborator account can push but is not a repository
administrator; runner registration requires the owner. Registration and live
deployment are still pending, including the handoff from the API already running
in `/home/dell/hackathon-stack/fieldops-ai`.

## What deployment changes

- Extracts the exact checked revision to `~/.local/share/fieldops/releases/`.
- Points `~/.local/share/fieldops/current` at it and restarts the user service
  `fieldops-api.service`. This is separate from teammates' Git checkouts.
- Keeps the SQLite store, alert log, replay clock and live feed under `shared/`.
  A new database is seeded once; subsequent deploys preserve it. Existing live
  data in another checkout must be migrated deliberately before the first deploy.
- Checks the service and `/status`. Failure restores the previous symlink and
  service file and restarts the previous release. Failed first installs stop the
  managed service. Old releases are retained for rollback.
- Skips a job if its commit has already been superseded on `main`; serializes
  deployments so two jobs cannot switch the release concurrently.

Open `~/.local/share/fieldops/current/dashboard/index.html` or `pitch/index.html`
on the GB10. This deploys the offline replay and local API. It does not install
models, configure the camera, launch the live-feed simulator or add an HTTP
dashboard server. The dashboard's `127.0.0.1` API calls refer to the machine running
the browser, so open it on the GB10 (or use an SSH tunnel for a browser on your Mac).

Inspect logs with `journalctl --user -u fieldops-api.service -n 100`; pause automatic
updates during a presentation by setting `FIELDOPS_DEPLOY_ENABLED=false` and letting
any already-running deployment finish. For manual rollback, point `current` at a
retained release and restart `fieldops-api.service`.

## Running the whole stack at boot (systemd units in `deploy/systemd/`)

CI deploys only the tools API. The rest of the GB10 stack is packaged as systemd **user** units
under one target. Lingering is on, so they start at boot without a login:

| Unit | What it runs |
|---|---|
| `fieldops-sandbox.service` | Starts the NemoClaw `fieldops` sandbox (OpenClaw + Telegram) if it is stopped, then `nemoclaw fieldops recover` |
| `fieldops-vision.service` | YOLO26 counting service in the GPU container, `127.0.0.1:8767` |
| `fieldops-api.service` | Tools API from this checkout, `127.0.0.1` and the sandbox bridge `172.18.0.1`, port 8765 |
| `fieldops.target` | Pulls in all three |

vLLM (`nemoclaw-vllm`, Docker `unless-stopped`) and the OpenShell gateway
(`nemoclaw-openshell-gateway.service`) already come back on their own.

```bash
bash deploy/install.sh                       # copy units, enable and start fieldops.target
systemctl --user status 'fieldops*'
journalctl --user -u fieldops-vision -f
```

`install.sh` copies the units rather than symlinking them, because `deploy_gb10.sh` rewrites
`fieldops-api.service` in place. It also leaves an API unit that CI installed alone. **Before the
first CI deploy**, run `systemctl --user stop fieldops-api`: the deploy refuses to start while port
8765 is in use, and from then on CI owns the API unit.
