# Docker ECU Runbook

This runbook is for:

- Docker ECUs
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
bash scripts/preflight_ubuntu.sh --runtime docker --tcu non-mender --transport both --auto-vcan
```

## 3. Start Docker ECU Runtime

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/start_demo.sh
```

## 4. Zero-Touch TCU Run

Host Python TCU, default topology, all ECUs online:

```bash
python3 -m democtl run \
  --transport doip \
  --topology default \
  --dependency topology-default \
  --offline none \
  --runtime docker \
  --tcu-runtime python \
  --ecu-state fresh \
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
  --runtime docker \
  --tcu-runtime docker \
  --ecu-state fresh \
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
  --runtime docker \
  --tcu-runtime python \
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
  --runtime docker \
  --tcu-runtime python \
  --ecu-state keep-current \
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
  --runtime docker \
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
  --runtime docker \
  --tcu-runtime python \
  --ecu-state fresh \
  --ensure-vcan \
  --restart-runtime
```

## 5. Check Logs

```bash
ls logs/democtl
```

```bash
docker compose -f docker/docker-compose.ecus.yml logs gateway
docker compose -f docker/docker-compose.ecus.yml logs bcm
docker compose -f docker/docker-compose.ecus.yml logs cluster
```

## 6. Explicit ECU Container Commands

Default topology, all ECUs online:

Terminal 1:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_gateway_zone_pair.sh
```

Terminal 2:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_bcm_zone_pair.sh
```

Terminal 3:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_cluster_zone_pair.sh
```

Default topology, Cluster offline:

Run:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_gateway_zone_pair.sh
```

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_bcm_zone_pair.sh
```

Do not run:

```bash
bash scripts/run_cluster_zone_pair.sh
```

Body zone with 2 ECUs:

Terminal 1:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_body_multi_gateway_pair.sh
```

Terminal 2:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_body_multi_body_zone.sh
```

Terminal 3:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_body_multi_bcm_ecu.sh
```

Terminal 4:

```bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
bash scripts/run_body_multi_cluster_ecu.sh
```

## 7. Check Result

```bash
curl -k https://127.0.0.1:8080/status
```

```bash
cat ecus/gateway/version.json
cat ecus/bcm/version.json
cat ecus/cluster/version.json
```

## 8. Stop Runtime

```bash
python3 -m democtl teardown
```

## 9. Manual Fallback

Prepare only:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport doip \
  --topology default \
  --dependency topology-default \
  --offline none \
  --runtime docker \
  --tcu-runtime python \
  --ecu-state fresh
```

Start stack:

```bash
bash scripts/start_demo.sh
```

Run only TCU against the prepared scenario:

```bash
source runtime/scenarios/active_tcu_env.sh
export OTA_TRANSPORT=doip
export OTA_CLOUD_CONTROL=mqtt
python3 -m tcu.main
```

Docker TCU fallback:

```bash
python3 scripts/prepare_ota_scenario.py \
  --transport doip \
  --topology default \
  --dependency topology-default \
  --offline none \
  --runtime docker \
  --tcu-runtime docker \
  --ecu-state fresh
```

```bash
bash scripts/start_demo.sh --run-tcu
```
