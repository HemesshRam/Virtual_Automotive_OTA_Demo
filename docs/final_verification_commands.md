# Final Verification Commands


This file lists the commands to verify the implemented OTA framework features in
the repository.

The recommended workflow is to use the virtualenv created by `bootstrap.sh`.
If a customer prefers system Python instead, they must install the same
`requirements.txt` packages into that active interpreter before running the
commands below.

## 1. Quick Static Verification

Run:

```bash
bash scripts/check_features.sh quick
```

This checks:

- campaign JSON parsing
- dynamic vehicle topology loading and validation
- Uptane-style trust verification
- Docker compose file validity
- VCAN presence if available

If VCAN is not configured, quick mode prints the setup command:

```bash
sudo ./scripts/setup_vcan_zones.sh
```

## 2. Full Software Verification

Run:

```bash
bash scripts/check_features.sh full
```

This checks:

- campaign JSON parsing
- topology uniqueness, dependency references, and dependency cycles
- Uptane-style trust verification
- Docker compose validity
- VCAN zonal interfaces
- production-style simulation profile
- focused unit/integration test suite
- final ECU slot/version/flash state files

Run the production-style simulation profile directly:

```bash
python3 scripts/validate_realism_profile.py
```

## 3. Dynamic Topology And Dependency Verification

Preferred operator launcher:

```bash
bash scripts/run_dynamic_demo.sh
bash scripts/run_dynamic_demo.sh 1 doip
bash scripts/run_dynamic_demo.sh 2 doip
bash scripts/run_dynamic_demo.sh 3 doip
bash scripts/run_dynamic_demo.sh 4 doip
bash scripts/run_dynamic_demo.sh 5 doip
bash scripts/run_dynamic_demo.sh 6 vcan
```

This launcher always uses:

```text
HTTPS campaign/artifact download + MQTT notify/status
```

And maps to scenario-driven orchestration:

```text
1. Default topology / all online
2. Body zone with 2 ECUs
3. Cluster depends on Gateway
4. Partial rollout / Cluster optional skip
5. Cluster offline
6. BCM + Cluster offline
```

Run:

```bash
python3 scripts/check_vehicle_topology.py
.venv/bin/python -m unittest test_vehicle_topology_validation.py test_update_scheduler_status.py
.venv/bin/python -m unittest test_dynamic_update_planner.py
.venv/bin/python -m unittest test_scenario_runner.py
```

Expected:

- topology loads from `vehicle/topology.json`
- every ECU is mapped to one zone, CAN channel, and logical address
- dependencies reference known ECUs only
- dependency cycles are rejected
- an online dependency that does not need an update is reported as `SATISFIED`
- unavailable or failed dependencies still follow `abort_campaign` or `skip`
  policy from `vehicle/topology.json`
- campaign-level `dependency_overrides` can change update order per campaign

Show the same live dynamic plan used by `python -m tcu.main`:

```bash
# Requires gateway/zone/ECU services to be running.
python3 scripts/show_dynamic_update_plan.py --transport DOIP
python3 scripts/show_dynamic_update_plan.py --transport VCAN
python3 -m tcu.scenario_runner scenarios/body_two_ecus_https_mqtt.json --prepare-only
```

The dynamic planner combines:

- campaign target list and mandatory/optional target policy
- live ECU discovery result
- firmware compatibility result
- current ECU software version
- topology dependencies from `vehicle/topology.json`
- campaign dependency overrides from `campaigns/campaign_v1.json`

Expected classifications:

```text
ELIGIBLE                         ECU can be updated in this run
ALREADY_SATISFIED                ECU is already at target version
SKIPPED_OPTIONAL:<reason>        optional ECU is offline/incompatible/skipped
BLOCKED_BY_DEPENDENCY:<reason>   ECU is skipped because dependency is unavailable
ABORT_REQUIRED:<reason>          required ECU blocks the campaign
```

Activate the alternate dependency campaign:

```bash
bash scripts/use_cluster_depends_gateway_campaign.sh
```

Demo-friendly selector:

```bash
bash scripts/select_campaign_scenario.sh
```

Non-interactive:

```bash
bash scripts/select_campaign_scenario.sh 1
bash scripts/select_campaign_scenario.sh 2
bash scripts/select_campaign_scenario.sh 3
bash scripts/select_campaign_scenario.sh 4
```

Then run the OTA flow. Expected dependency rule:

```text
Gateway ECU -> BCM ECU
Gateway ECU -> Cluster ECU
```

Restore default:

```bash
bash scripts/use_default_campaign.sh
```

Verify another campaign-specific dependency chain:

```bash
python3 scripts/show_dependency_plan.py campaigns/campaign_dependency_bcm_gateway_cluster.json
python3 scripts/show_dynamic_update_plan.py --campaign campaigns/campaign_dependency_bcm_gateway_cluster.json --transport DOIP
```

Expected:

```text
1. BCM ECU
2. Gateway ECU
3. Cluster ECU
```

## 4. Docker Terminal-Pair ECU + Zone Verification

Use this when you want one terminal per ECU container plus its matching zone
controller container.

Create VCAN first:

```bash
sudo ./scripts/setup_vcan_zones.sh
```

Run these in separate terminals:

```bash
bash scripts/run_gateway_zone_pair.sh
bash scripts/run_bcm_zone_pair.sh
bash scripts/run_cluster_zone_pair.sh
python -m ota_server.app
bash scripts/run_tcu_mqtt_job_demo.sh doip deep-zonal
```

HTTPS is the default when demo TLS files exist. You can also use the explicit
HTTPS helper:

```bash
bash scripts/run_ota_server_https.sh
```

The TCU wrapper defaults to:

```text
MQTT notify/status + HTTPS campaign/artifact download
```

Expected:

- Gateway terminal shows `Gateway Routing  : DoIP -> TCP zone services`
- gateway terminal runs `virtual-ota-zone-gateway` and `virtual-ota-gateway`
- BCM terminal runs `virtual-ota-zone-body` and `virtual-ota-bcm`
- cluster terminal runs `virtual-ota-zone-cluster` and `virtual-ota-cluster`
- each ECU terminal shows `DOCKER TERMINAL-PAIR ECU + ZONE RUNNER`
- each zone service shows its zone ID and CAN channel
- gateway logs show DoIP diagnostic messages
- zone logs show raw UDS forwarding to the ECU CAN FD segment

Offline terminal-pair variants:

```bash
# Cluster offline, expected skip
bash scripts/run_gateway_zone_pair.sh
bash scripts/run_bcm_zone_pair.sh
bash scripts/run_cluster_zone_pair_offline.sh

# BCM/body zone offline, expected abort
bash scripts/run_gateway_zone_pair.sh
bash scripts/run_bcm_zone_pair_offline.sh
bash scripts/run_cluster_zone_pair.sh

# Gateway zone offline, expected abort
bash scripts/run_gateway_zone_pair_offline.sh
bash scripts/run_bcm_zone_pair.sh
bash scripts/run_cluster_zone_pair.sh
```

Heartbeat-based offline variants:

```bash
# Cluster ECU application runs, but heartbeat is disabled. Expected skip.
bash scripts/run_gateway_zone_pair.sh
bash scripts/run_bcm_zone_pair.sh
bash scripts/run_cluster_zone_pair_heartbeat_offline.sh

# BCM heartbeat missing. Expected abort because BCM is critical.
bash scripts/run_gateway_zone_pair.sh
bash scripts/run_bcm_zone_pair_heartbeat_offline.sh
bash scripts/run_cluster_zone_pair.sh

# Gateway heartbeat missing. Expected abort because Gateway is critical.
bash scripts/run_gateway_zone_pair_heartbeat_offline.sh

## 5. Dynamic Mender Generic Artifact Verification

Use this when you have already uploaded one generic Mender artifact such as
`virtual-ota-dynamic.mender`.

Interactive launcher:

```bash
bash scripts/run_dynamic_mender_demo.sh
```

This launcher:

- lets you choose topology, dependency, offline ECUs, transport, and runtime
- updates `runtime/mender/active_scenario.json`
- prints the exact runtime start commands
- tells you to create a fresh Hosted Mender deployment using the same artifact

Show the selected runtime scenario directly:

```bash
python3 integrations/mender/set_dynamic_scenario.py --show
```

Docker-oriented example:

```bash
bash scripts/run_dynamic_mender_demo.sh 1 1 1 1 1
```

Python-process example:

```bash
bash scripts/run_dynamic_mender_demo.sh 1 1 1 2 2
```

After selecting the scenario:

```bash
journalctl -u mender-updated -f
```

Then create a new deployment in Hosted Mender using the same uploaded generic
artifact. Expected:

- the selected dynamic scenario is used
- Mender triggers the TCU on the host
- the local vehicle runtime handles the selected topology/transport/offline case

API-driven example:

```bash
export MENDER_BASE_URL=https://hosted.mender.io
export MENDER_API_TOKEN='<management-jwt-or-api-key>'
export MENDER_DEVICE_GROUP='<your-static-group-name>'

bash scripts/run_dynamic_mender_demo.sh 1 1 1 1 1 api
```

Expected:

- a fresh uniquely named artifact is built in `/tmp`
- the artifact is uploaded via the Mender Management API
- a deployment is created for the configured device group
- the host-side Mender client starts the TCU automatically
bash scripts/run_bcm_zone_pair.sh
bash scripts/run_cluster_zone_pair.sh
```

Check live zone health:

```bash
python3 scripts/check_zone_health.py
```

Dynamic runtime fault control after containers are already running:

```bash
# Show current control state
python3 scripts/ecu_fault_control.py status

# Make one ECU disappear from its zone by stopping heartbeat
python3 scripts/ecu_fault_control.py gateway heartbeat off
python3 scripts/ecu_fault_control.py bcm heartbeat off
python3 scripts/ecu_fault_control.py cluster heartbeat off

# Wait 3 to 5 seconds, then verify zone state changed
python3 scripts/check_zone_health.py

# Run DoIP with dynamic zone heartbeat blocking
bash scripts/run_tcu_mqtt_job_demo.sh doip deep-zonal

# Run VCAN with dynamic zone heartbeat blocking
bash scripts/run_tcu_mqtt_job_demo.sh vcan deep-zonal

# Restore an ECU
python3 scripts/ecu_fault_control.py gateway heartbeat on
python3 scripts/ecu_fault_control.py bcm heartbeat on
python3 scripts/ecu_fault_control.py cluster heartbeat on
python3 scripts/check_zone_health.py

# Simulate diagnostic/programming refusal while heartbeat remains online
python3 scripts/ecu_fault_control.py bcm diagnostics off
python3 scripts/ecu_fault_control.py cluster programming off
```

## 5. Docker ECU Stack Verification

Start ECU containers:

```bash
bash scripts/start_demo.sh
```

## 5A. Multi-ECU Body Zone Demo

This profile proves one zone controller can own more than one ECU:

```text
gateway_zone -> Gateway ECU
body_zone    -> BCM ECU + Cluster ECU
```

Run:

```bash
bash scripts/stop_demo.sh
bash scripts/reset_demo_state.sh
bash scripts/use_default_campaign.sh
bash scripts/run_body_multi_ecu_zone_stack.sh
```

All-in-one stack terminals:

```bash
python -m ota_server.app
bash scripts/run_tcu_body_multi_ecu_zone_demo.sh doip
```

Per-terminal variant:

```bash
# Terminal 1
bash scripts/run_body_multi_gateway_pair.sh

# Terminal 2
bash scripts/run_body_multi_body_zone.sh

# Terminal 3
bash scripts/run_body_multi_bcm_ecu.sh

# Terminal 4
bash scripts/run_body_multi_cluster_ecu.sh

# Terminal 5
python -m ota_server.app

# Terminal 6
bash scripts/run_tcu_body_multi_ecu_zone_demo.sh doip
```

Verify live body-zone inventory:

```bash
bash scripts/check_body_multi_ecu_zone_health.sh
```

Check logs:

```bash
docker compose -f docker/docker-compose.ecus.yml logs gateway
docker compose -f docker/docker-compose.ecus.yml logs bcm
docker compose -f docker/docker-compose.ecus.yml logs cluster
```

Expected:

- `VCAN PREFLIGHT`
- ECU startup
- firmware installation logs during OTA

## 6. DoIP OTA Verification

Start OTA server:

```bash
python -m ota_server.app
```

Run TCU:

```bash
python -m tcu.main
```

Choose:

- `2` for `DoIP`
- `1` or `2` for cloud control plane

Expected:

- DoIP discovery via DoIP inventory/version reads
- UDS flashing sequence
- post-reset version confirmation
- default DoIP diagnostic path uses raw UDS only

Legacy JSON-over-DoIP demo payloads are disabled by default. Enable them only
for compatibility testing:

```bash
OTA_DOIP_ALLOW_LEGACY_JSON=1 python run_gateway.py
```

## 7. VCAN OTA Verification

Run TCU:

```bash
python -m tcu.main
```

Choose:

- `1` for `VCAN`
- `1` or `2` for cloud control plane

Expected:

- zonal CAN discovery
- UDS over ISO-TP/CAN-FD flashing
- post-install validation and commit

## 8. Partial Rollout Policy Verification

Activate partial campaign:

```bash
bash scripts/use_partial_skip_campaign.sh
bash scripts/reset_demo_state.sh
```

Run OTA again.

Expected:

- `Cluster ECU` is optional and skipped
- `Gateway ECU` and `BCM ECU` update
- campaign accepted with skipped optional target

Restore default campaign:

```bash
bash scripts/use_default_campaign.sh
```

## 9. Final ECU State Verification

Run:

```bash
bash scripts/verify_demo_state.sh
python3 scripts/validate_demo_consistency.py
```

Expected:

- `current_version = 2.0.0`
- `confirmed_version = 2.0.0`
- `pending_version = ""`
- `pending_commit = false`
- flash layout exists for the active slot
- flash journal shows `VERIFIED` or later
- activation control block shows active/confirmed slot metadata
- consistency validator prints `[OK]` for each ECU

## 10. Reset Demo State

Run:

```bash
bash scripts/reset_demo_state.sh
```

This clears:

- ECU version state
- slot state
- downloaded images
- staged slot images
- emulated flash memory / journal / control block files

## 11. Interrupted Flash Recovery Verification

Run:

```bash
python3 scripts/demo_interrupted_flash_recovery.py
```

Expected:

- before reboot: journal state is `PROGRAMMED`
- after reboot: version remains `1.0.0`
- rollback reason is `INCOMPLETE_FLASH_JOURNAL`

## 12. Reality / Production-Style Caveat

These commands verify the implemented production-style software behavior.

They do not prove:

- real embedded flash partition integration
- production PKI/Uptane deployment
- full ISO-TP coverage
- full UDS/NRC/service coverage
- production automotive Ethernet switch/TSN/VLAN behavior
