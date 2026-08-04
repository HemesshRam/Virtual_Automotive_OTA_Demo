# Virtual Automotive OTA Framework

Production-style automotive OTA demo for Linux development environments.

This repository models:

- OTA backend over HTTPS and MQTT
- TCU orchestration
- DoIP and VCAN transport paths
- UDS programming flow
- ISO-TP over CAN FD-style segmented transfer
- zonal controller routing
- ECU A/B slot activation and rollback behavior
- Uptane-style metadata verification
- optional Mender-triggered TCU execution

It is a runnable simulation, not a production AUTOSAR stack or hardware ECU flasher.

## Architecture

```text
                           Cloud / Backend
    +--------------------------------------------------------------+
    | OTA Server                                                   |
    | - HTTPS campaign and firmware hosting                        |
    | - MQTT notify / status topics                                |
    | - Campaign / job publishing                                  |
    +-----------------------------+--------------------------------+
                                  |
                    HTTPS artifacts|campaign metadata
                     MQTT notify   |status reporting
                                  v
    +--------------------------------------------------------------+
    | TCU                                                          |
    | - cloud client                                               |
    | - OTA orchestrator                                           |
    | - trust verification                                         |
    | - dependency planner                                         |
    | - transport selector                                         |
    +-------------------+--------------------------+---------------+
                        |                          |
                        | DoIP backbone            | VCAN / CAN FD path
                        v                          v
          +---------------------------+     +---------------------------+
          | Central Gateway / DoIP    |     | Zoned CAN interfaces      |
          | - UDP discovery           |     | - vcan_gate               |
          | - TCP routing activation  |     | - vcan_bcm                |
          | - UDS forwarding          |     | - vcan_clus               |
          +-------------+-------------+     +-------------+-------------+
                        |                                 |
                        +------------ deep-zonal ---------+
                                      routing

    +------------------------+  +------------------------+  +------------------------+
    | gateway_zone           |  | body_zone              |  | cluster_zone           |
    | Zone Controller        |  | Zone Controller        |  | Zone Controller        |
    | policy + heartbeat     |  | policy + heartbeat     |  | policy + heartbeat     |
    +-----------+------------+  +-----------+------------+  +-----------+------------+
                |                           |                           |
                v                           v                           v
         +-------------+             +-------------+             +-------------+
         | Gateway ECU |             | BCM ECU     |             | Cluster ECU |
         | UDS server  |             | UDS server  |             | UDS server  |
         | A/B slots   |             | A/B slots   |             | A/B slots   |
         | flash model |             | flash model |             | flash model |
         +-------------+             +-------------+             +-------------+
```

## Runtime Models

- Docker ECU runtime
  - ECU and zone-controller services run in containers
  - TCU runs on the host
- Python-process ECU runtime
  - ECU and zone-controller services run directly on the host
  - TCU runs on the host
- Mender-triggered TCU runtime
  - Mender manages only the TCU side
  - ECUs still run through Docker or Python-process runtime

Default repo operating model:

- cloud path: `HTTPS artifacts + MQTT notify/status`
- vehicle path: `deep-zonal / zonal-controller routing`
- transport medium: `DoIP` or `VCAN`

## Vehicle Definition Files

- Active topology wrapper:
  - [vehicle/topology.json](/home/ubuntu-ota/virtual-automotive-ota/vehicle/topology.json)
- Default logical platform definition:
  - [vehicle/platform_definition.json](/home/ubuntu-ota/virtual-automotive-ota/vehicle/platform_definition.json)
- Default local runtime mapping:
  - [vehicle/runtime_mapping.local.json](/home/ubuntu-ota/virtual-automotive-ota/vehicle/runtime_mapping.local.json)
- Body-zone two-ECU topology:
  - [vehicle/topology.body_multi_ecu.json](/home/ubuntu-ota/virtual-automotive-ota/vehicle/topology.body_multi_ecu.json)
- Mid-size architecture example:
  - [vehicle/topology.midsize_demo.json](/home/ubuntu-ota/virtual-automotive-ota/vehicle/topology.midsize_demo.json)

Interpretation:

- `platform_definition.json`: logical vehicle architecture
- `runtime_mapping.local.json`: local Linux deployment mapping
- `topology.json`: active composition of platform + runtime

## Primary Code Areas

- TCU orchestrator:
  - [tcu/main.py](/home/ubuntu-ota/virtual-automotive-ota/tcu/main.py)
- Scenario compiler / runtime mutation:
  - [tcu/scenario_runner.py](/home/ubuntu-ota/virtual-automotive-ota/tcu/scenario_runner.py)
- DoIP gateway/server:
  - [transport/doip/server.py](/home/ubuntu-ota/virtual-automotive-ota/transport/doip/server.py)
- UDS client programming flow:
  - [transport/uds/client.py](/home/ubuntu-ota/virtual-automotive-ota/transport/uds/client.py)
- UDS flash transfer manager:
  - [transport/uds/flash_manager.py](/home/ubuntu-ota/virtual-automotive-ota/transport/uds/flash_manager.py)
- ECU-side UDS programmer:
  - [ecus/base/uds_can_programmer.py](/home/ubuntu-ota/virtual-automotive-ota/ecus/base/uds_can_programmer.py)
- OTA backend:
  - [ota_server/app.py](/home/ubuntu-ota/virtual-automotive-ota/ota_server/app.py)
- MQTT campaign publisher:
  - [ota_server/campaign_scheduler.py](/home/ubuntu-ota/virtual-automotive-ota/ota_server/campaign_scheduler.py)
- Mender bridge:
  - [integrations/mender/run_tcu_from_mender.py](/home/ubuntu-ota/virtual-automotive-ota/integrations/mender/run_tcu_from_mender.py)

## Tech Stack

| Component | Purpose |
| --- | --- |
| Python | TCU, OTA backend, ECU logic, transport logic |
| Flask | HTTPS OTA backend |
| MQTT / Mosquitto | campaign notify and status telemetry |
| TLS | HTTPS artifact and campaign transfer |
| `python-doipclient` | DoIP client-side tester behavior |
| UDS codec/client/server logic | OTA-relevant ISO 14229 programming flow |
| ISO-TP adapter | segmented transport over CAN |
| Linux `vcan_*` interfaces | CAN network simulation |
| Docker / Docker Compose | isolated ECU and zone-controller runtime |
| File-backed flash model | flashing, A/B activation, rollback, recovery |
| Uptane-style metadata verifier | trust chain and rollback protection |
| Mender integration | external TCU deployment orchestration |

## Documentation

Primary operational docs:

- Docker ECU runbook:
  - [docs/runbook_docker_ecus.md](/home/ubuntu-ota/virtual-automotive-ota/docs/runbook_docker_ecus.md)
- Python-process ECU runbook:
  - [docs/runbook_python_ecus.md](/home/ubuntu-ota/virtual-automotive-ota/docs/runbook_python_ecus.md)
- Mender TCU setup and deployment:
  - [docs/mender_tcu_runbook.md](/home/ubuntu-ota/virtual-automotive-ota/docs/mender_tcu_runbook.md)

Reference docs:

- Architecture design:
  - [docs/final_ota_architecture_design.md](/home/ubuntu-ota/virtual-automotive-ota/docs/final_ota_architecture_design.md)
- Verification commands:
  - [docs/final_verification_commands.md](/home/ubuntu-ota/virtual-automotive-ota/docs/final_verification_commands.md)
- Docker validation checklist:
  - [docs/docker_validation_checklist.md](/home/ubuntu-ota/virtual-automotive-ota/docs/docker_validation_checklist.md)

Dynamic demo launchers remain available but are lower priority than the fixed runbooks above.

## References

Official and primary references used to shape the architecture and operating model:

- Mender overview and client/server deployment model:
  - https://docs.mender.io/overview/introduction
  - Main areas used:
    - architecture of a software update
    - client/server roles
    - managed client behavior
- Mender deployment model:
  - https://docs.mender.io/overview/deployment
  - Main areas used:
    - deployment life-cycle
    - device deployment states
    - static vs dynamic targeting
    - already-installed / noartifact / failure result handling
- Uptane standard:
  - https://uptane.org/docs/2.0.0/standard/uptane-standard
  - Main areas used:
    - trust metadata chain
    - rollback protection
    - image / target verification concepts
    - vehicle software update security model
- AWS IoT Jobs device workflow:
  - https://docs.aws.amazon.com/iot/latest/developerguide/jobs-devices.html
  - Main areas used:
    - device job notification over MQTT
    - job status update flow
    - HTTPS/MQTT cloud-to-device control concepts
- AWS IoT Jobs key concepts:
  - https://docs.aws.amazon.com/iot/latest/developerguide/key-concepts-jobs.html
  - Main areas used:
    - job document structure
    - target and deployment concepts
    - rollout control vocabulary used to shape TCU-side orchestration
- Docker Compose:
  - https://docs.docker.com/compose
  - https://docs.docker.com/reference/cli/docker/compose
  - Main areas used:
    - multi-container service orchestration
    - compose-based startup / shutdown / logs flow
    - profile-driven runtime separation for ECU and zone services

Repository-specific reference documents:

- Architecture design:
  - [docs/final_ota_architecture_design.md](/home/ubuntu-ota/virtual-automotive-ota/docs/final_ota_architecture_design.md)
  - Main areas covered:
    - target architecture
    - control-plane / data-plane split
    - ECU, zone, gateway, and TCU responsibilities
- Verification commands:
  - [docs/final_verification_commands.md](/home/ubuntu-ota/virtual-automotive-ota/docs/final_verification_commands.md)
  - Main areas covered:
    - protocol checks
    - demo validation flow
    - runtime verification commands
- Mender integration details:
  - [docs/mender_tcu_runbook.md](/home/ubuntu-ota/virtual-automotive-ota/docs/mender_tcu_runbook.md)
  - Main areas covered:
    - Mender client setup
    - Update Module install
    - artifact packaging
    - deployment execution path
