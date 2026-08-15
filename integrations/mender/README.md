# Mender TCU Integration

This repository integrates Mender at the TCU layer, not at the ECU layer.

The intended architecture is:

```text
Mender UI / Mender backend
        ->
Mender Client on TCU
        ->
TCU OTA orchestrator in this repository
        ->
DoIP / VCAN / zone controllers
        ->
ECUs
```

This follows current Mender documentation patterns for:

- device-side Mender Client in managed mode
- Update Modules for custom application-level update behavior
- inventory scripts for searchable device metadata

References:

- Mender Client overview:
  - https://docs.mender.io/client-installation/overview
- Mender deployment overview:
  - https://docs.mender.io/overview/deployment
- Mender Update Modules:
  - https://docs.mender.io/client-installation/use-an-updatemodule
  - https://docs.mender.io/artifact-creation/create-a-custom-update-module
- Mender inventory:
  - https://docs.mender.io/overview/inventory
  - https://docs.mender.io/client-installation/inventory

## What This Integration Does

- The Mender deployment targets the TCU only.
- A custom Update Module invokes the TCU orchestrator.
- The TCU then performs the automotive-specific update flow:
  - campaign acquisition
  - trust verification
  - vehicle discovery
  - dependency planning
  - DoIP / VCAN execution
  - ECU flashing and validation

## Files

- `integrations/mender/update-modules/v3/tcu-ota-module`
  - Mender Update Module entry point
- `integrations/mender/run_tcu_from_mender.py`
  - bridge from the extracted Mender payload to the TCU runtime
- `integrations/mender/inventory/mender-inventory-virtual-ota`
  - emits TCU/vehicle inventory attributes for the Mender UI
- `integrations/mender/build_payload_dir.py`
  - creates a local payload directory with `deployment.json` and `campaign.json`
- `integrations/mender/set_dynamic_scenario.py`
  - writes the active runtime scenario consumed by the generic Mender artifact

## Payload Format

The Update Module expects a `deployment.json` file in the extracted payload
directory.

Example:

```json
{
  "scenario": "scenarios/dynamic_demo_template.json",
  "scenario_name": "mender_tcu_rollout",
  "transport": "doip",
  "topology_mode": "default",
  "dependency_mode": "topology_default",
  "offline_ecus": [],
  "server_url": "https://127.0.0.1:8080",
  "cloud_control": "http",
  "quiet": 1,
  "campaign_file": "campaign.json",
  "tls_verify": "docker/tls/demo-ca.crt"
}
```

Generic dynamic artifact example:

```json
{
  "scenario": "scenarios/dynamic_demo_template.json",
  "scenario_name": "mender_dynamic_demo",
  "transport": "doip",
  "topology_mode": "default",
  "dependency_mode": "topology_default",
  "offline_ecus": [],
  "server_url": "https://127.0.0.1:8080",
  "cloud_control": "http",
  "quiet": 1,
  "campaign_file": "campaign.json",
  "tls_verify": "docker/tls/demo-ca.crt",
  "use_active_scenario": true,
  "active_scenario_file": "runtime/mender/active_scenario.json"
}
```

Notes:

- `cloud_control` should normally be `http` for Mender-triggered updates,
  because Mender is already the trigger; the TCU does not need to wait on MQTT.
- `campaign_file` is optional. If supplied, the TCU loads that campaign from the
  local payload instead of calling `/campaign/latest`.
- firmware artifacts are still expected to be served from the OTA server unless
  you add a local artifact handoff path later.
- if `use_active_scenario` is true, the bridge merges
  `runtime/mender/active_scenario.json` into the deployment defaults at runtime.
  This is the recommended way to keep a single generic artifact and switch demo
  scenarios without repackaging for every case.

## Install On TCU

Install the Update Module:

```bash
sudo install -D -m 0755 \
  integrations/mender/update-modules/v3/tcu-ota-module \
  /usr/share/mender/modules/v3/tcu-ota-module
```

Install the inventory script:

```bash
sudo install -D -m 0755 \
  integrations/mender/inventory/mender-inventory-virtual-ota \
  /usr/share/mender/inventory/mender-inventory-virtual-ota
```

Set the repository path for installed Mender scripts:

```bash
echo 'export OTA_PROJECT_ROOT=/home/ubuntu-ota/Virtual_Automotive_OTA_Demo' | sudo tee /etc/profile.d/virtual-ota-mender.sh
sudo chmod 0644 /etc/profile.d/virtual-ota-mender.sh
```

For the current shell session, export it explicitly before testing:

```bash
export OTA_PROJECT_ROOT=/home/ubuntu-ota/Virtual_Automotive_OTA_Demo
```

## How The Flow Works

1. Mender deploys a custom Artifact to the TCU.
2. The TCU Mender Client extracts the payload and invokes `tcu-ota-module`.
3. The Update Module calls `run_tcu_from_mender.py`.
4. The bridge prepares the selected scenario and sets:
   - topology
   - transport
   - cloud mode
   - local campaign override if present
5. The bridge invokes the existing `tcu.main` flow.
6. The TCU executes the OTA update over DoIP or VCAN.

## Local Validation Without Mender

Create a payload directory:

```bash
mkdir -p /tmp/mender-tcu-payload
cp campaigns/campaign_v1.default.json /tmp/mender-tcu-payload/campaign.json
cat > /tmp/mender-tcu-payload/deployment.json <<'EOF'
{
  "scenario": "scenarios/dynamic_demo_template.json",
  "scenario_name": "mender_local_test",
  "transport": "doip",
  "topology_mode": "default",
  "dependency_mode": "topology_default",
  "offline_ecus": [],
  "server_url": "https://127.0.0.1:8080",
  "cloud_control": "http",
  "quiet": 1,
  "campaign_file": "campaign.json",
  "tls_verify": "docker/tls/demo-ca.crt"
}
EOF
```

Run the bridge directly:

```bash
python3 integrations/mender/run_tcu_from_mender.py /tmp/mender-tcu-payload
```

Build the payload directory automatically instead:

```bash
python3 integrations/mender/build_payload_dir.py /tmp/mender-tcu-payload
```

List the built-in runnable deployment profiles:

```bash
python3 integrations/mender/build_payload_dir.py /tmp/unused --list-profiles
```

Build from a named profile:

```bash
python3 integrations/mender/build_payload_dir.py /tmp/mender-default-doip --profile default_doip
python3 integrations/mender/build_payload_dir.py /tmp/mender-default-vcan --profile default_vcan
python3 integrations/mender/build_payload_dir.py /tmp/mender-body-two-doip --profile body_two_doip
python3 integrations/mender/build_payload_dir.py /tmp/mender-body-two-vcan --profile body_two_vcan
python3 integrations/mender/build_payload_dir.py /tmp/mender-gateway-offline --profile gateway_offline
python3 integrations/mender/build_payload_dir.py /tmp/mender-partial-skip --profile partial_skip_cluster
```

## Dynamic Mender Scenario Mode

For a more production-style demo, use one generic artifact and update the active
scenario separately.

Set the active scenario to a built-in profile:

```bash
python3 integrations/mender/set_dynamic_scenario.py --profile default_doip
python3 integrations/mender/set_dynamic_scenario.py --profile body_two_doip
python3 integrations/mender/set_dynamic_scenario.py --profile partial_skip_cluster
```

Set the active scenario with explicit runtime choices:

```bash
python3 integrations/mender/set_dynamic_scenario.py \
  --transport doip \
  --topology-mode body_two_ecus \
  --dependency-mode bcm_before_gateway \
  --offline-ecus "Cluster ECU"
```

Inspect the active scenario:

```bash
python3 integrations/mender/set_dynamic_scenario.py --show
```

Reset back to the default dynamic scenario:

```bash
python3 integrations/mender/set_dynamic_scenario.py --reset
```

Build one generic artifact:

```bash
python3 integrations/mender/package_artifact.py \
  /tmp/virtual-ota-dynamic.mender \
  --device-type virtual-ota-tcu \
  --profile dynamic_generic
```

Then reuse that same uploaded artifact in Mender while changing only the active
scenario file on the TCU host.

## Interactive Dynamic Mender Launcher

Use the terminal-driven launcher when you want a menu flow similar to the local
dynamic OTA demo:

```bash
bash scripts/run_dynamic_mender_demo.sh
```

This launcher lets you choose:

- topology
- dependency mode
- offline ECU set
- transport
- runtime style: Docker stack or Python processes

It then:

- writes the selected scenario into `runtime/mender/active_scenario.json`
- prints the exact runtime bring-up commands
- tells you to create a fresh deployment in Hosted Mender using the same
  generic artifact

Non-interactive example:

```bash
bash scripts/run_dynamic_mender_demo.sh 2 3 4 1 1
```

Meaning:

- topology `2` = body two ECUs
- dependency `3` = BCM before Gateway before Cluster
- offline `4` = Cluster ECU offline
- transport `1` = DoIP
- runtime `1` = Docker

API-driven mode:

```bash
export MENDER_BASE_URL=https://hosted.mender.io
export MENDER_API_TOKEN='<management-jwt-or-api-key>'
export MENDER_DEVICE_GROUP='<your-static-group-name>'

bash scripts/run_dynamic_mender_demo.sh 1 1 1 1 1 api
```

This mode:

- updates `runtime/mender/active_scenario.json`
- packages a fresh uniquely named artifact for the selected scenario
- uploads the artifact via the Mender Management API
- creates a deployment for the configured device group

Why the artifact name changes on every API-driven run:

- Mender skips deployment of an artifact if the same artifact is already
  installed on the device
- therefore the launcher creates a fresh artifact name each run, while still
  using the same generic update-module design and the same scenario-driven
  TCU logic

Then run:

```bash
python3 integrations/mender/run_tcu_from_mender.py /tmp/mender-tcu-payload
```

## Execution Summary

The bridge now writes a summary file by default:

- `/tmp/mender-tcu-payload/tcu_execution_summary.json`

This file is intended to be easy for Mender-side tooling, CI, or demo wrappers
to consume. It includes:

- final status
- transport
- cloud control mode
- campaign id
- reason
- discovered ECUs
- eligible ECUs
- update order
- platform/runtime definition files
- per-ECU results

## Inventory In Mender UI

The provided inventory script reports attributes such as:

- `vehicle_model`
- `vehicle_architecture`
- `vehicle_platform`
- `vehicle_topology_file`
- `vehicle_platform_definition`
- `vehicle_runtime_mapping`
- `ecu_count`
- `zone_count`
- `ecu_names`
- `gateway_version`
- `bcm_version`
- `cluster_version`

This gives the Mender UI enough context to present the TCU as a fleet-managed
vehicle update orchestrator rather than as a generic Linux node.

## Built-In Deployment Profiles

The repository includes profile presets in:

- `integrations/mender/deployment_profiles.json`

Current profiles:

- `dynamic_generic`
- `default_doip`
- `default_vcan`
- `body_two_doip`
- `body_two_vcan`
- `dependency_cluster_gateway`
- `dependency_bcm_before_gateway`
- `gateway_offline`
- `cluster_offline`
- `partial_skip_cluster`

These map directly to the main runnable demo cases:

- default topology
- one zone with two ECUs
- dependency override cases
- offline ECU cases
- DoIP / VCAN selection

## Packaging A `.mender` Artifact

Use the packaging helper to convert a named deployment profile into an uploadable
Mender Artifact for the `tcu-ota-module` Update Module.

Print the command only:

```bash
python3 integrations/mender/package_artifact.py \
  /tmp/virtual-ota-default-doip.mender \
  --device-type virtual-ota-tcu \
  --profile default_doip \
  --print-only
```

Create the Artifact:

```bash
python3 integrations/mender/package_artifact.py \
  /tmp/virtual-ota-default-doip.mender \
  --device-type virtual-ota-tcu \
  --profile default_doip
```

Body-two-ECU VCAN example:

```bash
python3 integrations/mender/package_artifact.py \
  /tmp/virtual-ota-body-two-vcan.mender \
  --device-type virtual-ota-tcu \
  --profile body_two_vcan
```

Gateway-offline failure profile:

```bash
python3 integrations/mender/package_artifact.py \
  /tmp/virtual-ota-gateway-offline.mender \
  --device-type virtual-ota-tcu \
  --profile gateway_offline
```

Notes:

- This script requires `mender-artifact` to be installed in your shell `PATH`.
- The Artifact payload type is `tcu-ota-module`, matching the installed Update Module.
- The script builds a payload directory automatically unless you pass `--payload-dir`.

## Mender UI Flow

After building the `.mender` file:

1. Open **Software** in Mender UI
2. Upload the generated `.mender` Artifact
3. Open **Deployments**
4. Click **Create a deployment**
5. Select the uploaded release
6. Select the TCU device or device group
7. Start the deployment

The TCU Mender Client will invoke `tcu-ota-module`, which then runs the
automotive OTA orchestration from this repository.
