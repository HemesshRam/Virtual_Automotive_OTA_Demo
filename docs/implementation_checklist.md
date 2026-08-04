# Virtual Automotive OTA
## Implementation Checklist by Module/File

This checklist converts the final OTA architecture into concrete work items mapped to the current repository structure.

Use this as the coding order:

1. protocol correctness
2. trust and artifact handling
3. ECU flash and rollback behavior
4. fleet orchestration and rollout policy
5. cleanup, tests, and hardening

---

## 0. Design-to-Code Mapping

This table maps the design blocks from `DESIGN.pdf` to the current repository.
Use it to decide what can be reused, what must be adapted, and what is still missing.

| Design block | Current module/file | Status | Notes |
|---|---|---|---|
| Central Compute / TCU orchestrator | `tcu/main.py`, `tcu/update_scheduler.py` | Partial | Campaign flow, inventory, planning, and execution are present. Needs stronger real-ECU lifecycle and protocol correctness. |
| Campaign validation / policy engine | `tcu/validation/campaign_validator.py`, `tcu/compatibility/validator.py` | Partial | Structural validation exists, but security, signature, and strict rollout policy are still incomplete. |
| Vehicle inventory manager | `tcu/ecu_discovery.py`, `tcu/models/vehicle.py`, `tcu/models/ecu.py` | Partial | Discovery and normalization exist. Needs fuller capability metadata and real post-boot inventory update. |
| Dependency planner | `tcu/dependency_manager.py`, `tcu/models/dependency_graph.py` | Mostly in place | Topological ordering exists. Needs richer group/zone-aware planning if we follow the zonal design closely. |
| Transport manager | `tcu/transport_manager.py`, `transport/base.py` | Partial | Adapter selection exists. Needs clearer separation between simulation, CAN/ISO-TP, and DoIP real-ECU modes. |
| DoIP backbone | `transport/doip/library_client.py`, `transport/doip/client.py`, `transport/doip/server.py` | Partial | `python-doipclient` is now primary and custom DoIP is preserved. Still using OTA JSON inside diagnostic payloads, not raw UDS. |
| Zonal controller / gateway router | `run_gateway.py`, `ecus/gateway/doip_server.py`, `transport/doip/server.py` | Partial | Gateway acts like a zonal bridge in the demo. It is not yet a full protocol-translating zonal controller. |
| In-zone CAN transport | `ecus/base/can_interface.py`, `transport/can/can_sender.py`, `common/can_protocol.py` | Partial | CAN FD is enabled, but payload handling still reflects a simulator protocol rather than UDS-over-CAN. |
| ISO-TP transport layer | `transport/can/isotp_adapter.py` | Scaffold | Exists as a minimal adapter only. Not yet wired into the active UDS flow or full flow-control behavior. |
| UDS programming client | `transport/uds/client.py`, `transport/uds/flash_manager.py`, `transport/uds/services.py` | Partial | Orchestration wrapper exists. Needs real UDS service payloads, NRC handling, session control, security access, and reset/reconnect behavior. |
| ECU bootloader / installer | `ecus/base/installer.py`, `ecus/base/version_manager.py`, `ecus/base/reboot_manager.py` | Partial | Good simulator-level lifecycle, but not true A/B bank flashing, commit, and rollback. |
| ECU state machine | `ecus/base/state_machine.py`, `ecus/base/ecu_state.py` | Partial | State concepts are present; transitions are still simplified. |
| Vehicle version / health reporting | `ecus/base/message_handler.py`, `tcu/status_reporter.py`, `ota_server/status_repository.py` | Partial | Inventory and status reporting exist. Needs stronger post-install evidence and persistent history. |
| Campaign backend / artifact store | `ota_server/app.py`, `ota_server/routes.py`, `ota_server/repository.py` | Partial | Works for the demo. Needs manifest/signature-awareness if we want to mirror the design more closely. |
| Uptane-style metadata / release governance | `tcu/firmware_manifest.py`, `docs/final_ota_architecture_design.md` | Not implemented | Structural alignment only. No real signature chain yet. |
| A/B activation and rollback | `ecus/base/installer.py`, `ecus/base/reboot_manager.py` | Not implemented | Current install path is host-file based and does not manage dual slots. |

---

## 0. Current Status Summary

### Completed or effectively in place

- [x] TCU selects a DoIP transport path through `python-doipclient` via `transport/doip/library_client.py` as the primary path
- [x] Custom-written DoIP client remains available in `transport/doip/client.py`
- [x] DoIP wrapper now uses `python-doipclient` by default and falls back to the custom client only when explicitly requested or when the library is unavailable
- [x] OTA campaign download and local campaign persistence
- [x] Campaign validation skeleton
- [x] Vehicle discovery skeleton
- [x] Dependency graph and topological planning
- [x] Status reporting endpoint and TCU status reporting
- [x] ECU discovery over CAN in the simulator path
- [x] ECU-side version and state models exist
- [x] CAN bus objects are now created as CAN-FD capable
- [x] CAN frame builders now emit CAN-FD frames

### Partially complete

- [~] UDS flow exists, but it is still a transport-wrapper and not a full protocol-correct implementation
- [~] DoIP flow uses `python-doipclient`, but the custom DoIP stack is separate and still incomplete
- [~] ECU install logic exists, but it is still simulator-style and not full ECU flash semantics
- [~] Post-install verification exists, but still relies heavily on discovery/model state
- [~] Status persistence exists, but it is minimal and not a full audit trail
- [~] ISO-TP adapter exists as a transport primitive, but it is not yet wired through the full UDS execution path

### Not complete yet

- [ ] Standards-based UDS request/response engine
- [ ] SecurityAccess / negative response handling / retry policy
- [ ] Signed artifact verification
- [ ] Real ECU rollback / fallback behavior
- [ ] Real DoIP gateway forwarding and ECU routing behavior
- [ ] Real post-boot health confirmation
- [ ] Persistent campaign history and release evidence
- [ ] Production-grade split between simulation and real-ECU execution

---

## 1. Backend / OTA Server

### [ ] `ota_server/routes.py`
- [ ] Add manifest version and schema validation before serving campaign data.
- [ ] Serve release metadata, signatures, and checksum data with the campaign.
- [ ] Add explicit status codes and richer error responses for invalid status payloads.
- [ ] Separate campaign read API from artifact read API if needed.

### [ ] `ota_server/repository.py`
- [ ] Normalize repository paths for campaigns, firmware, signatures, and manifests.
- [ ] Add helpers for artifact lookup by ECU name and release version.
- [ ] Add helpers for signature and manifest lookup.

### [ ] `ota_server/status_repository.py`
- [ ] Persist history, not only latest status.
- [ ] Record timestamp, ECU, campaign ID, state, progress, version, and error code.
- [ ] Add query helpers for campaign-level and ECU-level status.

### [ ] `ota_server/config.py`
- [ ] Add configurable repository root, campaign path, and artifact path.
- [ ] Add configurable server host/port.

---

## 2. Campaign and Release Model

### [ ] `tcu/models/campaign.py`
- [ ] Add fields for campaign release ID, rollout strategy, and approval state if needed.
- [ ] Keep target definitions explicit and versioned.
- [ ] Add validation-friendly helpers for mandatory targets and dependency groups.

### [ ] `tcu/models/ecu.py`
- [ ] Replace raw string version usage with a normalized version object or semver helper.
- [ ] Add ECU capability metadata:
  - [ ] DoIP support
  - [ ] UDS support
  - [ ] ISO-TP support
  - [ ] secure boot support
  - [ ] rollback support
- [ ] Add boot confirmation state and last install result.

### [ ] `tcu/models/dependency_graph.py`
- [ ] Ensure graph nodes can represent explicit dependency groups.
- [ ] Add cycle diagnostics that identify the exact loop path.

### [ ] `tcu/models/update_plan.py`
- [ ] Add support for staged plans, retries, and abort states.
- [ ] Add plan metadata: campaign ID, release version, timestamp, and execution mode.

---

## 3. Campaign Ingestion and Validation

### [ ] `tcu/campaign_manager.py`
- [ ] Load any new manifest fields added to campaign JSON.
- [ ] Validate target definitions while loading, not only later in execution.

### [ ] `tcu/validation/campaign_validator.py`
- [ ] Replace simple presence checks with strict schema validation.
- [ ] Validate campaign release metadata, artifact references, and target completeness.
- [ ] Validate mandatory vs optional target handling.
- [ ] Validate dependency policy fields if present.

### [ ] `tcu/compatibility/validator.py`
- [ ] Replace string comparisons with semantic version comparison.
- [ ] Make transport compatibility explicit per ECU capability.
- [ ] Enforce rollback support if campaign requires it.
- [ ] Report all incompatibility reasons, not just the first one.

### [ ] `tcu/firmware_compatibility.py`
- [ ] Bind campaign targets to signed artifacts and release manifest entries.
- [ ] Validate hardware variant, bootloader minimum, and transport compatibility.
- [ ] Validate artifact existence, checksum, and signature before scheduling.
- [ ] Return richer match records:
  - [ ] ECU
  - [ ] package
  - [ ] signature status
  - [ ] size
  - [ ] update path

### [ ] `tcu/firmware_manifest.py`
- [ ] Add manifest verification and signature verification hooks.
- [ ] Expose release metadata in a structured format.
- [ ] Ensure manifest and firmware package naming are consistent.

---

## 4. Vehicle Discovery and Inventory

### [ ] `tcu/ecu_discovery.py`
- [ ] Return normalized ECU metadata, not just current version.
- [ ] Include bootloader version, transport support, hardware variant, and health.
- [ ] Support discovery for DoIP as well as VCAN.
- [ ] Do not hardcode assumptions that only match the simulator.

### [ ] `tcu/models/vehicle.py`
- [ ] Store discovery timestamps and campaign association if needed.
- [ ] Add lookup helpers by ECU name and logical address.

### [ ] `common/ecu_registry.py`
- [ ] Keep registry as the source of logical addresses for simulation and gateway routing.
- [ ] Add transport and capability metadata if needed for real ECU mode.

---

## 5. Planning and Execution

### [ ] `tcu/dependency_manager.py`
- [ ] Keep topological planning isolated from transport and flashing.
- [ ] Add support for explicit dependency group validation.
- [ ] Improve cycle error output for debugging deployment graphs.

### [ ] `tcu/update_scheduler.py`
- [ ] Split execution into stages:
  - [ ] pre-check
  - [ ] download
  - [ ] transfer
  - [ ] install
  - [ ] reset
  - [ ] verification
  - [ ] final commit
- [ ] Track per-ECU state transitions during execution.
- [ ] Add retry/recovery policy for transport or download failures.
- [ ] Stop treating a local version update as success.
- [ ] Emit detailed failure codes and recovery reasons.

### [ ] `tcu/main.py`
- [ ] Preserve the current orchestration flow but route execution through the new standardized adapters.
- [ ] Add a clear execution mode selection:
  - [ ] simulation
  - [ ] VCAN/legacy CAN
  - [ ] DoIP real ECU
- [ ] Fail fast if campaign, manifest, or transport validation fails.

---

## 6. Transport Abstraction

### [ ] `tcu/transport_manager.py`
- [ ] Convert transport selection into a real adapter factory.
- [ ] Separate transport adapters by capability:
  - [ ] simulation
  - [ ] CAN/ISO-TP
  - [ ] DoIP
- [ ] Add a stable transport interface for:
  - [ ] connect
  - [ ] enter session
  - [ ] security access
  - [ ] request download
  - [ ] send transfer data
  - [ ] request transfer exit
  - [ ] reset
  - [ ] reconnect
  - [ ] read health/version

### [ ] `transport/base.py`
- [ ] Expand the abstract interface to cover the real update lifecycle.
- [ ] Keep simulation-only operations clearly separated from production operations.

### [ ] `transport/can/can_sender.py`
- [ ] Replace custom firmware message handling with standards-based UDS/ISO-TP flow if real CAN ECUs are targeted.
- [ ] Keep the simulator path only if explicitly selected.
- [ ] Add error handling for missing ACKs and invalid response types.

### [ ] `transport/can/firmware_chunker.py`
- [ ] Support chunk sizing based on transport constraints.
- [ ] Make sequence counters and payload sizing configurable.
- [ ] Ensure chunk boundaries align with actual protocol needs.

### [ ] `transport/can/frame_builder.py`
- [ ] Add validation for payload size and frame format.
- [ ] Enforce consistent addressing mode.

### [ ] `transport/can/segmentation.py`
- [ ] Review for ISO-TP alignment.
- [ ] Add tests for block segmentation and reassembly if used in real CAN mode.

### [ ] `transport/can/isotp_adapter.py`
- [ ] Implement ISO-TP adapter behavior if this module is used for real ECU programming.
- [ ] Add timeout, padding, and flow control configuration.

### [ ] `transport/uds/client.py`
- [ ] Implement a protocol-correct UDS programming flow.
- [ ] Add session control, security access, download, transfer, transfer exit, and reset.
- [ ] Handle negative responses and retries.
- [ ] Reconnect after ECU reset when needed.

### [ ] `transport/uds/flash_manager.py`
- [ ] Track expected block count and sequence numbers.
- [ ] Add failure recovery for mid-transfer aborts.
- [ ] Add verification that the whole payload was transferred.

### [ ] `transport/uds/server.py`
- [ ] Review whether this server is needed for simulation only.
- [ ] Add explicit simulation/production separation.

### [ ] `transport/doip/library_client.py`
- [ ] Use discovery and routing activation correctly.
- [ ] Make target address resolution and connection setup explicit.
- [ ] Add entity status and alive check support.
- [ ] Add reconnect after ECU reset.
- [ ] Add TLS support configuration for real deployments.

### [ ] `transport/doip/client.py`
- [ ] Keep only if it is required as a lower-level implementation detail.
- [ ] Verify that message packing and connection handling match the final adapter contract.

### [ ] `transport/doip/server.py`
- [ ] Implement actual DoIP endpoint behavior for the gateway simulator or real integration lab.
- [ ] Do not leave it as accept-and-close behavior.

### [ ] `transport/doip/routing_activation.py`
- [ ] Model routing activation request and response behavior explicitly.
- [ ] Ensure the gateway accepts only valid activations.

### [ ] `transport/doip/vehicle_discovery.py`
- [ ] Support vehicle announcement and entity discovery.
- [ ] Return address and logical address data in a usable form.

### [ ] `transport/doip/message.py`
- [ ] Keep message encode/decode aligned with the transport contract.
- [ ] Add tests for all application message variants.

### [ ] `transport/doip/packet.py`
- [ ] Validate packet header fields and lengths.
- [ ] Add tests for DoIP payload packing and unpacking.

### [ ] `transport/doip/protocol.py`
- [ ] Align protocol definitions with the final DoIP adapter contract.

---

## 7. ECU Runtime

### [ ] `ecus/base/ecu_base.py`
- [ ] Expand the ECU runtime loop beyond discovery responses.
- [ ] Introduce states for programming, verifying, resetting, and rollback.
- [ ] Add handlers for diagnostic requests relevant to flashing and verification.

### [ ] `ecus/base/message_handler.py`
- [ ] Extend message handling beyond discovery.
- [ ] Add response handlers for version readback, health readback, and diagnostic programming requests.

### [ ] `ecus/base/state_machine.py`
- [ ] Add all required OTA states.
- [ ] Enforce valid transitions.
- [ ] Emit transition reasons for debugging.

### [ ] `ecus/base/version_manager.py`
- [ ] Persist version information in a way that matches the real ECU lifecycle.
- [ ] Separate current version, pending version, and confirmed version.

### [ ] `ecus/base/config_manager.py`
- [ ] Load bootloader version, transport support, and hardware variant.
- [ ] Add flags for rollback and secure boot support.

### [ ] `ecus/base/reboot_manager.py`
- [ ] Distinguish planned reboot, reset after install, and rollback reboot.

### [ ] `ecus/base/installer.py`
- [ ] Replace host-file move logic with ECU flash semantics.
- [ ] Add pending image handling.
- [ ] Add confirm-or-revert logic.
- [ ] Add rollback path if boot confirmation fails.

### [ ] `ecus/base/can_interface.py`
- [ ] Ensure CAN traffic handling is compatible with the chosen simulation or real transport path.
- [ ] Add proper timeout and receive behavior for ECU reactions.

---

## 8. ECU Implementations

### [ ] `ecus/gateway/ecu.py`
- [ ] Add gateway ECU runtime behavior beyond startup.

### [ ] `ecus/gateway/doip_server.py`
- [ ] Implement actual DoIP accept, route, and diagnostic dispatch behavior.
- [ ] Do not close the connection immediately after accept.

### [ ] `ecus/gateway/uds_router.py`
- [ ] Route UDS payloads to the correct ECU instance.
- [ ] Add error handling for unknown logical addresses.

### [ ] `ecus/gateway/routing_table.py`
- [ ] Maintain address mappings for gateway routing.

### [ ] `ecus/gateway/routing_activation.py`
- [ ] Validate activation requests and permission rules.

### [ ] `ecus/gateway/diagnostic_dispatcher.py`
- [ ] Dispatch incoming diagnostic messages to the correct ECU/runtime handler.

### [ ] `ecus/gateway/integrity.py`
- [ ] Add image verification and trust checking hooks.

### [ ] `ecus/gateway/installer.py`
- [ ] Replace demo install path with gateway-aware programming flow if applicable.

### [ ] `ecus/gateway/version.json`
- [ ] Keep version metadata consistent with the TCU inventory and campaign manifest.

### [ ] `ecus/gateway/firmware_receiver.py`
- [ ] Verify received firmware size and checksum.
- [ ] Add signature verification integration.
- [ ] Add transfer completeness validation.

### [ ] `ecus/bcm/ecu.py`
- [ ] Add BCM-specific diagnostics and install behavior if BCM differs from base ECU.

### [ ] `ecus/bcm/can_receiver.py`
- [ ] Verify BCM message handling aligns with final CAN/UDS behavior.

### [ ] `ecus/bcm/installer.py`
- [ ] Ensure BCM install path matches the common ECU installer contract.

### [ ] `ecus/bcm/integrity.py`
- [ ] Add BCM-specific integrity verification if needed.

### [ ] `ecus/bcm/transport.py`
- [ ] Align BCM transport handling with the chosen simulation or real transport.

### [ ] `ecus/cluster/ecu.py`
- [ ] Add cluster-specific diagnostics and install behavior if cluster differs from base ECU.

### [ ] `ecus/cluster/can_receiver.py`
- [ ] Verify cluster message handling aligns with the final transport behavior.

### [ ] `ecus/cluster/installer.py`
- [ ] Ensure cluster install path matches the common ECU installer contract.

### [ ] `ecus/cluster/integrity.py`
- [ ] Add cluster-specific integrity verification if needed.

### [ ] `ecus/cluster/transport.py`
- [ ] Align cluster transport handling with the chosen simulation or real transport.

---

## 9. Status, Telemetry, and Verification

### [ ] `tcu/status_reporter.py`
- [ ] Add campaign ID and release version to all status reports.
- [ ] Include error codes and failure reasons.
- [ ] Make reporting resilient to partial network failure.

### [ ] `tcu/status_manager.py`
- [ ] Normalize status values across simulation and real execution.
- [ ] Add history and last-known-good state tracking.

### [ ] `tcu/post_install_validator.py`
- [ ] Query actual ECU state after reboot.
- [ ] Validate version, health, and boot confirmation.
- [ ] Do not mark success based only on rediscovery of the vehicle model.

---

## 10. Model and Utility Cleanup

### [ ] `common/constants.py`
- [ ] Verify IDs and chunk sizes match the final transport mode.
- [ ] Keep transport constants grouped by mode.

### [ ] `common/message_types.py`
- [ ] Ensure message types are only used for the simulation path if custom CAN messages remain.

### [ ] `common/checksum.py`
- [ ] Keep for integrity support only.
- [ ] Do not confuse checksum with authenticity.

### [ ] `common/logical_addresses.py`
- [ ] Ensure logical addresses align with the final gateway and ECU model.

### [ ] `common/progress_bar.py`
- [ ] Keep progress display decoupled from protocol logic.

### [ ] `common/utils.py`
- [ ] Add version parsing helpers if needed.
- [ ] Add reusable validation helpers for paths and manifests.

---

## 11. Tests

### [ ] `test_campaign.py`
- [ ] Update expectations to include new campaign fields if added.

### [ ] `test_campaign_validation.py`
- [ ] Add schema and signature validation scenarios.

### [ ] `test_compatibility.py`
- [ ] Add semantic versioning tests.
- [ ] Add bootloader and rollback compatibility tests.

### [ ] `test_dependency_graph.py`
- [ ] Add cycle detection coverage and dependency ordering cases.

### [ ] `test_firmware_manager.py`
- [ ] Add release inventory and artifact validation cases.

### [ ] `test_message_handler.py`
- [ ] Add diagnostic request/response handling tests.

### [ ] `test_state_machine.py`
- [ ] Add all valid and invalid OTA transitions.

### [ ] `test_update_planner.py`
- [ ] Add staged execution and dependency order tests.

### [ ] `test_vehicle_model.py`
- [ ] Add richer inventory and ECU capability tests.

### [ ] Add new tests
- [ ] `test_semver.py`
- [ ] `test_signature_validation.py`
- [ ] `test_uds_flow.py`
- [ ] `test_doip_flow.py`
- [ ] `test_rollback.py`
- [ ] `test_post_install_verification.py`

---

## 12. Suggested Coding Order

1. Fix version parsing and model consistency.
2. Expand campaign validation and artifact metadata.
3. Implement real UDS flow.
4. Implement real DoIP routing and reconnect behavior.
5. Add signature and manifest verification.
6. Implement ECU pending install and rollback.
7. Improve post-install verification.
8. Add audit trail and persistent status.
9. Expand tests for all the above.

---

## 13. Exact Implementation Order

Follow this order strictly:

1. `common/utils.py`
   - Add semantic version parsing helpers and shared validation helpers.

2. `tcu/models/ecu.py`
   - Normalize ECU version handling and capability metadata.

3. `tcu/models/campaign.py`
   - Add any campaign fields needed for release metadata and rollout policy.

4. `tcu/campaign_manager.py`
   - Load the expanded campaign format.

5. `tcu/validation/campaign_validator.py`
   - Enforce strict campaign schema validation.

6. `tcu/compatibility/validator.py`
   - Replace string comparisons with semantic version comparisons.

7. `tcu/firmware_manifest.py`
   - Add manifest loading and verification structure.

8. `tcu/firmware_compatibility.py`
   - Bind ECU targets to validated firmware artifacts.

9. `tcu/ecu_discovery.py`
   - Return normalized inventory data for each ECU.

10. `tcu/models/vehicle.py`
    - Support richer inventory records and lookup helpers.

11. `tcu/dependency_manager.py`
    - Finalize dependency graph validation and ordering.

12. `tcu/update_scheduler.py`
    - Split execution into proper stages and remove success-by-bookkeeping behavior.

13. `tcu/transport_manager.py`
    - Convert transport selection into a real adapter factory.

14. `transport/base.py`
    - Expand the transport interface to cover the full OTA lifecycle.

15. `transport/uds/client.py`
    - Implement real UDS programming flow.

16. `transport/uds/flash_manager.py`
    - Add block/sequence tracking and transfer completion checks.

17. `transport/doip/library_client.py`
    - Implement real DoIP discovery, routing activation, and reconnect behavior.

18. `ecus/gateway/doip_server.py`
    - Turn the gateway into a real diagnostic router for simulation/lab use.

19. `ecus/base/state_machine.py`
    - Add the full OTA state model.

20. `ecus/base/message_handler.py`
    - Handle diagnostic and verification messages beyond discovery.

21. `ecus/base/installer.py`
    - Replace host-file install logic with ECU install semantics.

22. `ecus/base/version_manager.py`
    - Split current, pending, and confirmed version handling.

23. `ecus/base/reboot_manager.py`
    - Add reboot, confirm, and rollback-aware behavior.

24. `ecus/base/ecu_base.py`
    - Wire the ECU runtime to the new state, install, and diagnostic flow.

25. `ecus/*/integrity.py`
    - Add authenticity/signature verification hooks where applicable.

26. `ota_server/repository.py`
    - Normalize artifact and manifest lookup paths.

27. `ota_server/routes.py`
    - Serve validated campaign, artifact, and status payloads.

28. `ota_server/status_repository.py`
    - Persist full campaign history and per-ECU status records.

29. `tcu/post_install_validator.py`
    - Verify boot and health using actual ECU state.

30. Tests
    - Add or update tests for every step above before moving to the next phase.

---

## 14. Done Criteria

The implementation is ready for a real ECU integration pass when:

- campaign validation fails for malformed or unsigned releases
- transport adapters implement real protocol behavior
- update execution handles retries, resets, and negative responses
- ECU install paths support pending, confirmed, and rollback states
- post-install verification reads actual ECU state
- audit and status data is persisted
- simulation mode still works without regression

---

## 15. One-Day Rush Plan

If the goal is to finish as much as possible by tomorrow, use this reduced scope:

### Must complete tomorrow

1. `common/utils.py`
   - semantic version parsing
   - shared validation helpers

2. `tcu/models/ecu.py`
   - normalize ECU version handling
   - add capability flags

3. `tcu/compatibility/validator.py`
   - replace string compares
   - enforce transport / bootloader checks

4. `tcu/firmware_manifest.py`
   - structured manifest loading
   - basic integrity/signature hooks

5. `tcu/firmware_compatibility.py`
   - bind ECU to artifact
   - validate file presence, version, variant

6. `tcu/transport_manager.py`
   - keep simulation and real adapter selection clean
   - expose one consistent programming API

7. `transport/uds/client.py`
   - implement the full UDS programming sequence
   - handle timeout and ACK/NRC failures

8. `transport/doip/library_client.py`
   - implement real routing activation and reconnect behavior

9. `ecus/base/state_machine.py`
   - add programming, verifying, rebooting, rollback states

10. `ecus/base/installer.py`
    - replace host-file move logic with ECU install semantics

11. `ecus/base/message_handler.py`
    - add version and health readback

12. `tcu/update_scheduler.py`
    - stage-by-stage execution
    - no success until verification is complete

13. `tcu/post_install_validator.py`
    - validate actual ECU boot and version

### Can defer until after tomorrow

- full rollback automation
- persistent audit history
- staged rollout / canary policy
- richer backend APIs
- extra transport hardening
- broader test expansion

### Suggested order for tomorrow

1. semantic versioning and model cleanup
2. manifest / artifact validation
3. UDS programming flow
4. DoIP routing activation
5. ECU state machine + installer
6. scheduler + post-install verification
7. smoke tests

### End-of-day acceptance target

By tomorrow night, the code should be able to:

- load a campaign
- validate compatibility correctly
- select the right artifact
- execute a protocol-correct update flow
- reboot the ECU
- confirm the version after boot
- fail clearly if anything is wrong
