# Manual Execution Runbook

This runbook is for direct execution without `democtl run`.

Use it when you want to run:

- Python ECUs or Docker ECUs
- Non-Mender host Python TCU
- Non-Mender Docker TCU
- Mender TCU with line-by-line scenario preparation

## 1. Bootstrap

```bash
git clone https://github.com/HemesshRam/Virtual_Automotive_OTA_Demo.git
cd Virtual_Automotive_OTA_Demo
export PROJECT_ROOT="$(pwd)"

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Reset Before Every Scenario

```bash
bash scripts/stop_demo.sh || true
bash scripts/reset_demo_state.sh
sudo ./scripts/setup_vcan_zones.sh
bash scripts/use_default_campaign.sh
```

## 3. Standard TCU Run

Use this after refreshing the active scenario:

```bash
source runtime/scenarios/active_tcu_env.sh
export OTA_ALLOW_PARTIAL_TARGET_SKIP=1
OTA_CAMPAIGN_PUBLISH_DELAY=0 python -m ota_server.campaign_scheduler
python -m tcu.main
```

Docker TCU run against the active prepared scenario:

```bash
bash scripts/start_demo.sh --run-tcu
```

## 4. Python ECUs, Default Topology, All Online, DoIP

Terminal 1:

```bash
python3 run_gateway.py
```

Terminal 2:

```bash
python3 run_bcm.py
```

Terminal 3:

```bash
python3 run_cluster.py
```

Terminal 4:

```bash
python3 -m zones.run_zone_service gateway_zone
```

Terminal 5:

```bash
python3 -m zones.run_zone_service body_zone
```

Terminal 6:

```bash
python3 -m zones.run_zone_service cluster_zone
```

Terminal 7:

```bash
bash scripts/run_ota_server_https.sh
```

Terminal 8:

```bash
python3 scripts/refresh_active_scenario.py \
  --base-campaign campaigns/campaign_v1.default.json \
  --transport doip \
  --topology-mode default \
  --dependency-mode topology_default \
  --offline-ecus "" \
  --runtime python \
  --ecu-state-preset keep_current \
  --server-url https://127.0.0.1:8080 \
  --public-base-url https://127.0.0.1:8080 \
  --status-url https://127.0.0.1:8080/status \
  --tls-verify docker/tls/demo-ca.crt \
  --source manual

source runtime/scenarios/active_tcu_env.sh
export OTA_ALLOW_PARTIAL_TARGET_SKIP=1
OTA_CAMPAIGN_PUBLISH_DELAY=0 python -m ota_server.campaign_scheduler
python -m tcu.main
```

## 5. Python ECUs, Default Topology, Gateway Only, VCAN

Terminal 1:

```bash
python3 run_gateway.py
```

Terminal 2:

```bash
python3 -m zones.run_zone_service gateway_zone
```

Terminal 3:

```bash
bash scripts/run_ota_server_https.sh
```

Terminal 4:

```bash
python3 scripts/refresh_active_scenario.py \
  --base-campaign campaigns/campaign_v1.default.json \
  --transport vcan \
  --topology-mode default \
  --dependency-mode topology_default \
  --offline-ecus "BCM ECU,Cluster ECU" \
  --runtime python \
  --ecu-state-preset keep_current \
  --server-url https://127.0.0.1:8080 \
  --public-base-url https://127.0.0.1:8080 \
  --status-url https://127.0.0.1:8080/status \
  --tls-verify docker/tls/demo-ca.crt \
  --source manual

source runtime/scenarios/active_tcu_env.sh
export OTA_ALLOW_PARTIAL_TARGET_SKIP=1
OTA_CAMPAIGN_PUBLISH_DELAY=0 python -m ota_server.campaign_scheduler
python -m tcu.main
```

## 6. Python ECUs, Body Zone With 2 ECUs, VCAN

Terminal 1:

```bash
OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json python3 run_gateway.py
```

Terminal 2:

```bash
OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json python3 run_bcm.py
```

Terminal 3:

```bash
OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json OTA_ECU_CLUSTER_CAN_CHANNEL=vcan_bcm python3 run_cluster.py
```

Terminal 4:

```bash
python3 -m zones.run_zone_service gateway_zone
```

Terminal 5:

```bash
python3 -m zones.run_zone_service body_zone
```

Terminal 6:

```bash
bash scripts/run_ota_server_https.sh
```

Terminal 7:

```bash
python3 scripts/refresh_active_scenario.py \
  --base-campaign campaigns/campaign_v1.default.json \
  --transport vcan \
  --topology-mode body_two_ecus \
  --dependency-mode topology_default \
  --offline-ecus "" \
  --runtime python \
  --ecu-state-preset keep_current \
  --server-url https://127.0.0.1:8080 \
  --public-base-url https://127.0.0.1:8080 \
  --status-url https://127.0.0.1:8080/status \
  --tls-verify docker/tls/demo-ca.crt \
  --source manual

source runtime/scenarios/active_tcu_env.sh
export OTA_ALLOW_PARTIAL_TARGET_SKIP=1
OTA_CAMPAIGN_PUBLISH_DELAY=0 python -m ota_server.campaign_scheduler
python -m tcu.main
```

## 7. Python ECUs, Dependency Override, BCM Before Gateway Before Cluster

Set the dependency order first:

```bash
bash scripts/use_bcm_gateway_cluster_campaign.sh
```

Then run the Python all-online DoIP flow from section 4, but use this refresh command in the TCU terminal:

```bash
python3 scripts/refresh_active_scenario.py \
  --base-campaign campaigns/campaign_dependency_bcm_gateway_cluster.json \
  --transport doip \
  --topology-mode default \
  --dependency-mode bcm_before_gateway \
  --offline-ecus "" \
  --runtime python \
  --ecu-state-preset keep_current \
  --server-url https://127.0.0.1:8080 \
  --public-base-url https://127.0.0.1:8080 \
  --status-url https://127.0.0.1:8080/status \
  --tls-verify docker/tls/demo-ca.crt \
  --source manual
```

## 8. Docker ECUs, Default Topology, All Online, DoIP

Terminal 1:

```bash
bash scripts/run_gateway_zone_pair.sh
```

Terminal 2:

```bash
bash scripts/run_bcm_zone_pair.sh
```

Terminal 3:

```bash
bash scripts/run_cluster_zone_pair.sh
```

Terminal 4:

```bash
bash scripts/run_ota_server_https.sh
```

Terminal 5:

```bash
python3 scripts/refresh_active_scenario.py \
  --base-campaign campaigns/campaign_v1.default.json \
  --transport doip \
  --topology-mode default \
  --dependency-mode topology_default \
  --offline-ecus "" \
  --runtime docker \
  --ecu-state-preset keep_current \
  --server-url https://127.0.0.1:8080 \
  --public-base-url https://127.0.0.1:8080 \
  --status-url https://127.0.0.1:8080/status \
  --tls-verify docker/tls/demo-ca.crt \
  --source manual

source runtime/scenarios/active_tcu_env.sh
export OTA_ALLOW_PARTIAL_TARGET_SKIP=1
OTA_CAMPAIGN_PUBLISH_DELAY=0 python -m ota_server.campaign_scheduler
python -m tcu.main
```

## 9. Manual Mender TCU, Python ECUs

Start the Python ECU and zone terminals from section 4, 5, 6, or 7 first.

Then build the artifact:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport doip \
  --topology default \
  --dependency topology-default \
  --offline none \
  --runtime python \
  --tcu-runtime python \
  --ecu-state keep-current \
  --device-type virtual-ota-tcu \
  --artifact-name virtual-ota-manual-python-$(date +%Y%m%d%H%M%S) \
  --build-mender auto
```

Watch logs:

```bash
journalctl -u mender-authd -f
```

```bash
journalctl -u mender-updated -f
```

## 10. Manual Mender TCU, Docker ECUs

Start the Docker ECU terminals from section 8 first.

Then build the artifact:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport doip \
  --topology default \
  --dependency topology-default \
  --offline none \
  --runtime docker \
  --tcu-runtime python \
  --ecu-state keep-current \
  --device-type virtual-ota-tcu \
  --artifact-name virtual-ota-manual-docker-$(date +%Y%m%d%H%M%S) \
  --build-mender auto
```

Watch logs:

```bash
journalctl -u mender-authd -f
```

```bash
journalctl -u mender-updated -f
```

## 11. Quick Checks

```bash
python3 scripts/check_zone_health.py
```

```bash
curl -k https://127.0.0.1:8080/status
```

```bash
cat ecus/gateway/version.json
cat ecus/bcm/version.json
cat ecus/cluster/version.json
```

## 12. Stop Everything

```bash
bash scripts/stop_demo.sh || true
```
