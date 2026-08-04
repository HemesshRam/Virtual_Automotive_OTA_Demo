# Python ECU Runbook

## 1. Bootstrap

```bash
git clone <repo-url>
cd virtual-automotive-ota
export PROJECT_ROOT="$(pwd)"

bash bootstrap.sh
source .venv/bin/activate
```

## 2. Preflight

```bash
bash scripts/preflight_ubuntu.sh --runtime python --tcu non-mender --transport both
```

For strict port checking:

```bash
bash scripts/preflight_ubuntu.sh --runtime python --tcu non-mender --transport both --require-free-ports
```

## 3. Reset

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate

bash scripts/stop_demo.sh || true
bash scripts/reset_demo_state.sh
sudo ./scripts/setup_vcan_zones.sh
```

## 4. Prepare Scenario

Default topology, DoIP, all ECUs online:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport doip \
  --topology default \
  --dependency topology-default \
  --offline none \
  --runtime python \
  --ecu-state fresh
```

Default topology, VCAN, Cluster offline:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport vcan \
  --topology default \
  --dependency topology-default \
  --offline cluster \
  --runtime python \
  --ecu-state keep-current
```

Body zone with 2 ECUs, VCAN, Cluster offline:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport vcan \
  --topology body-two \
  --dependency topology-default \
  --offline cluster \
  --runtime python \
  --ecu-state keep-current
```

BCM before Gateway before Cluster:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport doip \
  --topology default \
  --dependency bcm-gateway-cluster \
  --offline none \
  --runtime python \
  --ecu-state fresh
```

Cluster depends on Gateway:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport doip \
  --topology default \
  --dependency cluster-gateway \
  --offline none \
  --runtime python \
  --ecu-state fresh
```

## 5. Start Python ECU + Zone Processes

### 5.1 Default Topology

Terminal 1:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 -m zones.run_zone_service gateway_zone
```

Terminal 2:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 -m zones.run_zone_service body_zone
```

Terminal 3:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 -m zones.run_zone_service cluster_zone
```

Terminal 4:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 run_gateway.py
```

Terminal 5:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 run_bcm.py
```

Terminal 6:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python3 run_cluster.py
```

### 5.2 Body Zone With 2 ECUs

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

## 6. Start OTA Server

Terminal 7:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_ota_server_https.sh
```

## 7. Optional ECU Fault Injection

Cluster offline:

```bash
python3 scripts/ecu_fault_control.py cluster heartbeat offline
```

BCM offline:

```bash
python3 scripts/ecu_fault_control.py bcm heartbeat offline
```

Gateway offline:

```bash
python3 scripts/ecu_fault_control.py gateway heartbeat offline
```

Bring ECU heartbeat back online:

```bash
python3 scripts/ecu_fault_control.py cluster heartbeat online
python3 scripts/ecu_fault_control.py bcm heartbeat online
python3 scripts/ecu_fault_control.py gateway heartbeat online
```

## 8. Check Zone Health

Default topology:

```bash
python3 scripts/check_zone_health.py
```

Body zone with 2 ECUs:

```bash
OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json python3 scripts/check_zone_health.py
```

## 9. Run Non-Mender TCU

Publish the job:

```bash
OTA_CAMPAIGN_PUBLISH_DELAY=0 python3 -m ota_server.campaign_scheduler
```

Run the TCU:

```bash
source runtime/scenarios/active_tcu_env.sh
python3 -m tcu.main
```

## 10. Check Result

```bash
curl -k https://127.0.0.1:8080/status
```

```bash
cat ecus/gateway/version.json
cat ecus/bcm/version.json
cat ecus/cluster/version.json
```
