# Python ECU Runbook

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

Default topology, Cluster offline:

```bash
python3 -m democtl run \
  --transport vcan \
  --topology default \
  --dependency topology-default \
  --offline cluster \
  --runtime python \
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
  --ecu-state fresh \
  --ensure-vcan \
  --restart-runtime
```

## 4. Check Logs

```bash
ls logs/democtl
```

## 5. Check Result

```bash
curl -k https://127.0.0.1:8080/status
```

```bash
cat ecus/gateway/version.json
cat ecus/bcm/version.json
cat ecus/cluster/version.json
```

## 6. Stop Runtime

```bash
python3 -m democtl teardown
```

## 7. Manual Fallback

Prepare only:

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
