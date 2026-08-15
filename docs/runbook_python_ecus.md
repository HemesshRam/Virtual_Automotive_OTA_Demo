# Python ECU Runbook

This runbook is for:

- Python ECUs
- Non-Mender TCU
- Host Python TCU or Docker TCU

For direct manual execution without `democtl run`, use:

- [manual_execution_runbook.md](manual_execution_runbook.md)

## 1. Bootstrap

```bash
git clone https://github.com/HemesshRam/Virtual_Automotive_OTA_Demo.git
cd Virtual_Automotive_OTA_Demo
export PROJECT_ROOT="$(pwd)"

bash bootstrap.sh
source .venv/bin/activate
```

## 2. Preflight

```bash
bash scripts/preflight_ubuntu.sh --runtime python --tcu non-mender --transport both --auto-vcan
```

## 3. Zero-Touch Run

Host Python TCU, default topology, Cluster offline:

```bash
python3 -m democtl run \
  --transport vcan \
  --topology default \
  --dependency topology-default \
  --offline cluster \
  --runtime python \
  --tcu-runtime python \
  --ecu-state keep-current \
  --ensure-vcan \
  --restart-runtime
```

Docker TCU, default topology, all ECUs online:

```bash
python3 -m democtl run \
  --transport doip \
  --topology default \
  --dependency topology-default \
  --offline none \
  --runtime python \
  --tcu-runtime docker \
  --ecu-state fresh \
  --ensure-vcan \
  --restart-runtime
```

Default topology, Cluster offline:

```bash
python3 -m democtl run \
  --transport vcan \
  --topology default \
  --dependency topology-default \
  --offline cluster \
  --runtime python \
  --tcu-runtime python \
  --ecu-state keep-current \
  --ensure-vcan \
  --restart-runtime
```

Default topology, all ECUs online:

```bash
python3 -m democtl run \
  --transport doip \
  --topology default \
  --dependency topology-default \
  --offline none \
  --runtime python \
  --tcu-runtime python \
  --ecu-state fresh \
  --ensure-vcan \
  --restart-runtime
```

Body zone with 2 ECUs, Cluster offline:

```bash
python3 -m democtl run \
  --transport vcan \
  --topology body-two \
  --dependency topology-default \
  --offline cluster \
  --runtime python \
  --tcu-runtime python \
  --ecu-state keep-current \
  --ensure-vcan \
  --restart-runtime
```

BCM before Gateway before Cluster:

```bash
python3 -m democtl run \
  --transport doip \
  --topology default \
  --dependency bcm-gateway-cluster \
  --offline none \
  --runtime python \
  --tcu-runtime python \
  --ecu-state fresh \
  --ensure-vcan \
  --restart-runtime
```

Cluster depends on Gateway:

```bash
python3 -m democtl run \
  --transport doip \
  --topology default \
  --dependency cluster-gateway \
  --offline none \
  --runtime python \
  --tcu-runtime python \
  --ecu-state fresh \
  --ensure-vcan \
  --restart-runtime
```

## 4. Check Logs

```bash
ls logs/democtl
```

## 5. Explicit ECU And Zone Commands

Default topology, all ECUs online:

Terminal 1:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 run_gateway.py
```

Terminal 2:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 run_bcm.py
```

Terminal 3:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 run_cluster.py
```

Terminal 4:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 -m zones.run_zone_service gateway_zone
```

Terminal 5:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 -m zones.run_zone_service body_zone
```

Terminal 6:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 -m zones.run_zone_service cluster_zone
```

Terminal 7:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_ota_server_https.sh
```

Default topology, Cluster offline:

Run the same commands as above, but do not start:

```bash
python3 run_cluster.py
```

Body zone with 2 ECUs:

Terminal 1:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
PYTHONPATH="$PROJECT_ROOT" python3 -m zones.run_zone_service gateway_zone
```

Terminal 2:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
PYTHONPATH="$PROJECT_ROOT" python3 -m zones.run_zone_service body_zone
```

Terminal 3:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json python3 run_gateway.py
```

Terminal 4:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json python3 run_bcm.py
```

Terminal 5:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json OTA_ECU_CLUSTER_CAN_CHANNEL=vcan_bcm python3 run_cluster.py
```

Terminal 6:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_ota_server_https.sh
```

## 6. Check Result

```bash
curl -k https://127.0.0.1:8080/status
```

```bash
cat ecus/gateway/version.json
cat ecus/bcm/version.json
cat ecus/cluster/version.json
```

## 7. Stop Runtime

```bash
python3 -m democtl teardown
```

## 8. Manual Fallback

Prepare only:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport doip \
  --topology default \
  --dependency topology-default \
  --offline none \
  --runtime python \
  --tcu-runtime python \
  --ecu-state fresh
```

Run host Python TCU:

```bash
source runtime/scenarios/active_tcu_env.sh
python3 -m tcu.main
```

Run Docker TCU:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport doip \
  --topology default \
  --dependency topology-default \
  --offline none \
  --runtime python \
  --tcu-runtime docker \
  --ecu-state fresh
```

```bash
bash scripts/start_demo.sh --run-tcu
```

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport vcan \
  --topology default \
  --dependency topology-default \
  --offline cluster \
  --runtime python \
  --ecu-state keep-current
```

Run only TCU against the prepared scenario:

```bash
source runtime/scenarios/active_tcu_env.sh
export OTA_TRANSPORT=vcan
export OTA_CLOUD_CONTROL=mqtt
python3 -m tcu.main
```
