# Partial Rollout Demo

This demo shows that an unsupported optional ECU is skipped while the rest of the
campaign proceeds.

## Demo Campaign

Use:

- [campaigns/campaign_partial_skip_cluster.json](/home/ubuntu-ota/virtual-automotive-ota/campaigns/campaign_partial_skip_cluster.json)

Behavior:

- `Gateway ECU`: mandatory, eligible
- `BCM ECU`: mandatory, eligible
- `Cluster ECU`: optional, intentionally incompatible because
  `minimum_bootloader` is set to `9.9.0`

## Activate Demo Campaign

From the project root:

```bash
bash scripts/use_partial_skip_campaign.sh
```

To restore the normal full campaign:

```bash
bash scripts/use_default_campaign.sh
```

## Expected Behavior

During campaign compatibility validation:

- `Gateway ECU`: accepted
- `BCM ECU`: accepted
- `Cluster ECU`: skipped if incompatible

During update execution:

- Gateway updates
- BCM updates
- Cluster is not flashed

Expected outcome:

- campaign accepted
- skipped optional target reported
- final campaign result can remain successful for the mandatory chain

## Reality Match

This is closer to real OTA frameworks than an all-or-nothing policy because:

- optional targets can be skipped
- mandatory targets still enforce campaign correctness
- dependency failures can skip downstream ECUs instead of crashing the whole plan
