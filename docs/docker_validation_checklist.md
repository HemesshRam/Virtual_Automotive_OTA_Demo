# Docker Validation Checklist


## Purpose

This checklist verifies the current ECU-container execution model:

- ECU containers run separately
- host VCAN interfaces back the CAN side
- DoIP runs through the gateway container
- TCU and OTA server can remain on the host

## 1. Host VCAN Preflight

Create zonal VCAN interfaces on the host:

```bash
sudo ./scripts/setup_vcan_zones.sh
```

Verify:

```bash
ip link show | grep vcan
```

Expected:

- `vcan_gate`
- `vcan_bcm`
- `vcan_clus`

## 2. Start ECU Containers

```bash
export LOCAL_UID=$(id -u)
export LOCAL_GID=$(id -g)
docker compose -f docker-compose.ecus.yml up --build
```

Expected log lines:

- `[VCAN PREFLIGHT] Interfaces ready: vcan_gate vcan_bcm vcan_clus`
- `Gateway ECU Ready...`
- `BCM ECU Ready...`
- `Cluster ECU Ready...`

If VCAN is missing, containers should fail fast with:

```text
[VCAN PREFLIGHT] Missing interfaces: ...
[VCAN PREFLIGHT] Run: sudo ./scripts/setup_vcan_zones.sh
```

## 3. Host Services

Run OTA server:

```bash
python -m ota_server.app
```

Run TCU:

```bash
python -m tcu.main
```

## 4. DoIP Validation

Choose:

- `2` for `DoIP`
- `1` or `2` for the cloud control plane

Expected behavior:

- DoIP vehicle identification succeeds
- DoIP routing activation succeeds
- TCU discovers ECU versions through DoIP inventory reads
- flashing completes
- post-install validation confirms version `2.0.0`

## 5. VCAN Validation

Choose:

- `1` for `VCAN`
- `1` or `2` for the cloud control plane

Expected behavior:

- CAN discovery succeeds on zonal VCAN channels
- flashing completes for all ECUs
- post-install validation confirms version `2.0.0`

## 6. Final ECU State Check

```bash
cat ecus/gateway/version.json
cat ecus/gateway/slot_state.json
cat ecus/bcm/version.json
cat ecus/bcm/slot_state.json
cat ecus/cluster/version.json
cat ecus/cluster/slot_state.json
```

Expected:

- `current_version: 2.0.0`
- `confirmed_version: 2.0.0`
- `pending_version: ""`
- `pending_commit: false`

## 7. Known Residual Gaps

Still not fully production-grade:

- full ISO-TP timing/addressing matrix
- full UDS service/NRC coverage
- full container-native CAN namespace isolation
- cryptographic PKI instead of demo HMAC-based metadata trust
