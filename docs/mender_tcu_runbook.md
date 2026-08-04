# Mender TCU Runbook

## 1. Bootstrap

```bash
git clone <repo-url>
cd virtual-automotive-ota
export PROJECT_ROOT="$(pwd)"

bash bootstrap.sh --with-mender
source .venv/bin/activate
```

## 2. Preflight

```bash
bash scripts/preflight_ubuntu.sh --runtime both --tcu mender --transport both
```

For strict port checking:

```bash
bash scripts/preflight_ubuntu.sh --runtime both --tcu mender --transport both --require-free-ports
```

## 3. Install Repo Update Module And Inventory Script

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

## 4. Export Repo Root For Inventory

```bash
echo "export OTA_PROJECT_ROOT=$PROJECT_ROOT" | sudo tee /etc/profile.d/virtual-ota-mender.sh
sudo chmod 0644 /etc/profile.d/virtual-ota-mender.sh
export OTA_PROJECT_ROOT="$PROJECT_ROOT"
```

## 5. Create Custom Device With Organization Token

```bash
sudo mender-setup \
  --device-type virtual-ota-tcu \
  --server https://hosted.mender.io \
  --tenant-token 'YOUR_ORG_TOKEN' \
  --demo-polling
```

## 6. Restart Mender Services

```bash
sudo systemctl restart mender-authd mender-updated
```

## 7. Watch Mender Logs

Authentication:

```bash
journalctl -u mender-authd -f
```

Update client:

```bash
journalctl -u mender-updated -f
```

## 8. Validate Inventory

```bash
/usr/share/mender/inventory/mender-inventory-virtual-ota
```

## 9. Prepare Scenario For Mender Artifact

Default topology, DoIP, all ECUs online:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate

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

Default topology, VCAN, Cluster offline:

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

Body zone with 2 ECUs, VCAN, Cluster offline:

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

## 10. Inspect Built Artifact

Use the exact file path printed by `prepare_ota_scenario.py`.

```bash
mender-artifact read /tmp/YOUR_ARTIFACT_NAME.mender
```

## 11. Start ECU Runtime Before Deployment

Docker ECUs:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/start_demo.sh
```

Python ECUs:

- See `docs/runbook_python_ecus.md`

## 12. Start OTA Server If Needed

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_ota_server_https.sh
```

## 13. Deploy In Hosted Mender

1. Upload the generated `.mender` artifact
2. Create a deployment
3. Select the `virtual-ota-tcu` device
4. Start deployment

## 14. Check OTA Result

```bash
curl -k https://127.0.0.1:8080/status
```

```bash
cat ecus/gateway/version.json
cat ecus/bcm/version.json
cat ecus/cluster/version.json
```

## 15. Restart Mender Again If Needed

```bash
sudo systemctl restart mender-authd mender-updated
```
