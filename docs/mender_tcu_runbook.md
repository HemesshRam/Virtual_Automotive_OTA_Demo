# Mender TCU Runbook

This runbook assumes the recommended virtualenv flow created by `bootstrap.sh`.
If a customer prefers system Python instead of `.venv`, they must still install
the same packages from `requirements.txt` into their active Python environment
before running the commands below.

## 1. Bootstrap

```bash
git clone https://github.com/HemesshRam/Virtual_Automotive_OTA_Demo.git
cd Virtual_Automotive_OTA_Demo
export PROJECT_ROOT="$(pwd)"

bash bootstrap.sh --with-mender
source .venv/bin/activate
```

## 2. Preflight

```bash
bash scripts/preflight_ubuntu.sh --runtime both --tcu mender --transport both --auto-vcan
```

## 3. Install Mender Repo Scripts

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

## 4. Export Repo Root For Mender

```bash
echo "export OTA_PROJECT_ROOT=$PROJECT_ROOT" | sudo tee /etc/profile.d/virtual-ota-mender.sh
sudo chmod 0644 /etc/profile.d/virtual-ota-mender.sh
export OTA_PROJECT_ROOT="$PROJECT_ROOT"
```

## 5. Register Mender Device

The `mender-client4` package provides `mender-setup`, `mender-auth`, and
`mender-update`. On a fresh Ubuntu install, it is usually not available from
the default APT sources, so install it through Mender's supported installer
first.

```bash
command -v mender-setup >/dev/null || {
  curl -fLsS https://get.mender.io -o /tmp/get-mender.sh
  sudo bash /tmp/get-mender.sh mender-client4
}

sudo mender-setup \
  --device-type virtual-ota-tcu \
  --hosted-mender \
  --server-url https://hosted.mender.io \
  --tenant-token 'YOUR_ORG_TOKEN' \
  --demo-polling
```

## 6. Restart Mender Services

```bash
sudo systemctl restart mender-authd mender-updated
```

## 7. Validate Inventory

```bash
/usr/share/mender/inventory/mender-inventory-virtual-ota
```

## 8. Start ECU Runtime

Docker ECUs:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/start_demo.sh
```

Python ECUs:

```bash
python3 -m democtl start-runtime --restart --ensure-vcan
```

## 9. Build Mender Artifact

Default topology, DoIP, Docker ECUs:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport doip \
  --topology default \
  --dependency topology-default \
  --offline none \
  --runtime docker \
  --ecu-state fresh \
  --device-type virtual-ota-tcu \
  --artifact-name virtual-ota-doip-default-$(date +%Y%m%d%H%M%S) \
  --build-mender auto
```

Default topology, VCAN, Cluster offline, Python ECUs:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport vcan \
  --topology default \
  --dependency topology-default \
  --offline cluster \
  --runtime python \
  --ecu-state keep-current \
  --device-type virtual-ota-tcu \
  --artifact-name virtual-ota-vcan-default-cluster-offline-$(date +%Y%m%d%H%M%S) \
  --build-mender auto
```

Body zone with 2 ECUs, VCAN, Cluster offline, Python ECUs:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport vcan \
  --topology body-two \
  --dependency topology-default \
  --offline cluster \
  --runtime python \
  --ecu-state keep-current \
  --device-type virtual-ota-tcu \
  --artifact-name virtual-ota-vcan-body-two-cluster-offline-$(date +%Y%m%d%H%M%S) \
  --build-mender auto
```

## 10. Inspect Artifact

```bash
mender-artifact read /tmp/YOUR_ARTIFACT_NAME.mender
```

## 11. Watch Mender Logs

```bash
journalctl -u mender-authd -f
```

```bash
journalctl -u mender-updated -f
```

## 12. Deploy In Hosted Mender

1. Upload the generated `.mender` artifact
2. Create deployment
3. Select the `virtual-ota-tcu` device
4. Start deployment

## 13. Check Result

```bash
curl -k https://127.0.0.1:8080/status
```

```bash
cat ecus/gateway/version.json
cat ecus/bcm/version.json
cat ecus/cluster/version.json
```

## 14. Restart Mender If Needed

```bash
sudo systemctl restart mender-authd mender-updated
```
