# Mender TCU Runbook

This runbook is for:

- Mender-managed TCU
- Host Python TCU only
- Python ECUs or Docker ECUs

Docker TCU is not used for Mender deployments.

For direct manual ECU startup and manual non-`democtl` execution, use:

- [manual_execution_runbook.md](manual_execution_runbook.md)

## 1. Bootstrap

```bash
git clone https://github.com/HemesshRam/Virtual_Automotive_OTA_Demo.git
cd Virtual_Automotive_OTA_Demo
export PROJECT_ROOT="$(pwd)"

bash bootstrap.sh --with-mender
source .venv/bin/activate
```

If a customer prefers system Python instead of `.venv`, they must still install
the same packages from `requirements.txt` into their active Python environment
before running the commands below.

## 2. Preflight

```bash
bash scripts/preflight_ubuntu.sh --runtime both --tcu mender --transport both --auto-vcan
```

## 3. Install Mender Client

The `mender-client4` package provides `mender-setup`, `mender-auth`, and
`mender-update`. On a fresh Ubuntu install, it is often not available from the
default APT sources, so install it through Mender's supported installer first.

```bash
command -v mender-setup >/dev/null || {
  curl -fLsS https://get.mender.io -o /tmp/get-mender.sh
  sudo bash /tmp/get-mender.sh mender-client4
}
```

## 4. Install Repo Hooks

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate

sudo install -D -m 0755 \
  integrations/mender/update-modules/v3/tcu-ota-module \
  /usr/share/mender/modules/v3/tcu-ota-module

sudo install -D -m 0755 \
  integrations/mender/inventory/mender-inventory-virtual-ota \
  /usr/share/mender/inventory/mender-inventory-virtual-ota
```

## 5. Export Repo Root

Set the repo root for both the current shell and the Mender systemd services.

```bash
echo "export OTA_PROJECT_ROOT=$PROJECT_ROOT" | sudo tee /etc/profile.d/virtual-ota-mender.sh
sudo chmod 0644 /etc/profile.d/virtual-ota-mender.sh
export OTA_PROJECT_ROOT="$PROJECT_ROOT"

sudo mkdir -p /etc/systemd/system/mender-authd.service.d
sudo mkdir -p /etc/systemd/system/mender-updated.service.d

cat <<EOF | sudo tee /etc/systemd/system/mender-authd.service.d/override.conf
[Service]
Environment=OTA_PROJECT_ROOT=$PROJECT_ROOT
EOF

cat <<EOF | sudo tee /etc/systemd/system/mender-updated.service.d/override.conf
[Service]
Environment=OTA_PROJECT_ROOT=$PROJECT_ROOT
EOF
```

## 6. Register Mender Device

```bash
sudo mender-setup \
  --device-type virtual-ota-tcu \
  --hosted-mender \
  --server-url https://hosted.mender.io \
  --tenant-token 'YOUR_ORG_TOKEN' \
  --demo-polling
```

## 7. Restart Mender Services

```bash
sudo systemctl daemon-reload
sudo systemctl restart mender-authd mender-updated
```

## 8. Verify Mender Environment

```bash
sudo systemctl show mender-authd --property=Environment
sudo systemctl show mender-updated --property=Environment
```

Both should include:

```bash
OTA_PROJECT_ROOT=$PROJECT_ROOT
```

## 9. Validate Inventory

```bash
/usr/share/mender/inventory/mender-inventory-virtual-ota
```

## 10. Accept The Device

In Hosted Mender:

1. Open `Devices`
2. Accept the device if it is in pending state
3. Wait until the device is `Online`

`Accepted` is not enough on its own. We want the device online before creating a deployment.

## 11. Prepare Scenario And Build Artifact

Use the prepared scenario that matches the demo case you want to show. This example is for
VCAN, default topology, Gateway-only active, with BCM and Cluster treated as optional targets.

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport vcan \
  --topology default \
  --dependency topology-default \
  --offline none \
  --runtime python \
  --tcu-runtime python \
  --ecu-state keep-current \
  --active-ecus gateway \
  --optional-targets "BCM ECU,Cluster ECU" \
  --device-type virtual-ota-tcu \
  --artifact-name virtual-ota-vcan-gateway-only-$(date +%Y%m%d%H%M%S) \
  --build-mender auto
```

For other scenarios, change `--transport`, `--topology`, `--offline`, `--runtime`, and
`--active-ecus` to match the case you want to show.

## 12. Start ECU Runtime Only

For Mender mode, start only the ECU runtime. Do not run the TCU manually.

Docker ECUs:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/start_demo.sh
```

Python ECUs:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 -m democtl start-runtime --restart --ensure-vcan
```

Do **not** run:

```bash
python3 -m tcu.main
bash scripts/start_demo.sh --run-tcu
```

## 13. Inspect Artifact

```bash
ls -lt /tmp/virtual-ota-vcan-gateway-only-*.mender | head -n 1
mender-artifact read /tmp/virtual-ota-vcan-gateway-only-*.mender
sudo cat /var/lib/mender/device_type
```

The artifact device type and the installed device type should both be:

```bash
virtual-ota-tcu
```

## 14. Deploy In Hosted Mender

1. Upload the generated `.mender` artifact
2. Create a deployment
3. Select the `virtual-ota-tcu` device
4. Start the deployment

## 15. Watch Mender Logs

```bash
journalctl -u mender-authd -f
```

```bash
journalctl -u mender-updated -f
```

## 16. Recovery If Deployment Stays Queued

If a deployment stays `Queued to start`, refresh the client services and check the last log lines.

```bash
sudo systemctl restart mender-authd mender-updated

journalctl -u mender-authd -n 30 --no-pager
journalctl -u mender-updated -n 30 --no-pager
```

If the device was registered on a different machine or with stale auth state, decommission the
old device in Hosted Mender and keep only the current one.

## Latest Updates

- Mender uses **host Python TCU only**
- Docker TCU is **not used** for Mender deployments
- Prepared scenario state is preserved into the Mender payload
- `active_ecus` and `optional_targets` are supported
- The host path vs `/app` path mismatch in the scenario validator is fixed
- `OTA_PROJECT_ROOT` must be exported for both shell sessions and systemd services
- The recommended Mender registration path is `get.mender.io` plus `mender-setup`

