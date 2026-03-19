# Folder Map and Parameter Guide

## Project Root Overview

- [artifacts](artifacts): trained model artifacts and checkpoints
- [configs](configs): adjustable configuration files
- [datasets](datasets): generated datasets used for training and evaluation
- [data_contract](data_contract): schema and signal contracts
- [logs](logs): execution and debugging logs
- [manifests](manifests): case mappings, episode definitions, and signal candidate lists
- [mpc](mpc): MPC implementation modules
- [pinn_model](pinn_model): PINN model and training implementation
- [results](results): run outputs, QC tables, figures, and summaries
- [scripts](scripts): operational scripts for generation, training, benchmarking, and QC

## Key Inputs

### Case/Episode Inputs

- [manifests/eu](manifests/eu)
- [manifests/eu/singlezone_commercial_hydronic_stage1.yaml](manifests/eu/singlezone_commercial_hydronic_stage1.yaml)
- [manifests/eu/bestest_hydronic_stage1.yaml](manifests/eu/bestest_hydronic_stage1.yaml)

### Dataset Inputs

- [datasets/eu](datasets/eu)
- [datasets/eu/singlezone_commercial_hydronic](datasets/eu/singlezone_commercial_hydronic)

### Data Contracts

- [data_contract/dataset_schema.json](data_contract/dataset_schema.json)
- [data_contract/signal_contract.yaml](data_contract/signal_contract.yaml)

## Adjustable Parameter Files

### MPC Parameters

- [configs/mpc_phase1.yaml](configs/mpc_phase1.yaml)
- Common edits: horizon, objective weights, comfort bounds, solver settings

### PINN Training Parameters

- [configs/pinn_phase1.yaml](configs/pinn_phase1.yaml)
- [configs/eu](configs/eu) per-case PINN configs

### Campaign-Level Parameters

- [configs/eu_rc_vs_pinn_campaign.yaml](configs/eu_rc_vs_pinn_campaign.yaml)

### Stage2 RC Variant Parameters

- [configs/eu/stage2/rc_variants.yaml](configs/eu/stage2/rc_variants.yaml)
- Common edits: RC scale factors for UA, solar gain, HVAC gain, and capacity

## Main Operational Scripts

- [scripts/run_eu_campaign_stage1.py](scripts/run_eu_campaign_stage1.py): main EU stage1 campaign
- [scripts/run_mpc_episode.py](scripts/run_mpc_episode.py): single predictor/episode MPC run
- [scripts/qc_eu_results.py](scripts/qc_eu_results.py): QC checks and figure generation
- [scripts/train_pinn.py](scripts/train_pinn.py): PINN training entry point

### Stage2 Utilities

- [scripts/stage2/run_eu_rc_variant_campaign.py](scripts/stage2/run_eu_rc_variant_campaign.py)
- [scripts/stage2/analyze_rc_variants_vs_pinn.py](scripts/stage2/analyze_rc_variants_vs_pinn.py)
- [scripts/stage2/README.md](scripts/stage2/README.md)

## Output Locations

- [results/eu_rc_vs_pinn](results/eu_rc_vs_pinn)
- [results/eu_rc_vs_pinn/raw](results/eu_rc_vs_pinn/raw): per-case predictor episode outputs
- [results/eu_rc_vs_pinn/qc](results/eu_rc_vs_pinn/qc): QC CSV/JSON and plots
- [artifacts/eu](artifacts/eu): trained checkpoints by case

## Error-Handling Documentation

- [SIMULATION_ERROR_HANDLING_PLAYBOOK.md](SIMULATION_ERROR_HANDLING_PLAYBOOK.md)

## Last Output: Folder Overview

### 1) Main Folder Overview

Project root docs and plans:

- [README.md](README.md)
- [PROJECT_PLAN.md](PROJECT_PLAN.md)
- [execution_plan_eu_rc_vs_pinn.md](execution_plan_eu_rc_vs_pinn.md)

Core code:

- [scripts](scripts)
- [mpc](mpc)
- [pinn_model](pinn_model)

Inputs and configuration:

- [datasets](datasets)
- [manifests](manifests)
- [configs](configs)
- [data_contract](data_contract)

Outputs:

- [results](results)
- [artifacts](artifacts)
- [logs](logs)

Error handling documentation:

- [SIMULATION_ERROR_HANDLING_PLAYBOOK.md](SIMULATION_ERROR_HANDLING_PLAYBOOK.md)

### 2) Where Your Input Files Are

Episode definitions and signal mappings (very important inputs for runs):

- [manifests/eu](manifests/eu)
- Example case manifest: [manifests/eu/singlezone_commercial_hydronic_stage1.yaml](manifests/eu/singlezone_commercial_hydronic_stage1.yaml)

Datasets used for training/evaluation:

- [datasets/eu](datasets/eu)
- Example per-case dataset folder: [datasets/eu/singlezone_commercial_hydronic](datasets/eu/singlezone_commercial_hydronic)

Data schema/contracts:

- [data_contract/dataset_schema.json](data_contract/dataset_schema.json)
- [data_contract/signal_contract.yaml](data_contract/signal_contract.yaml)

### 3) Parameter Files You Can Adjust

These are the main knobs:

MPC behavior:

- [configs/mpc_phase1.yaml](configs/mpc_phase1.yaml)
- Typical changes: horizon, bounds, objective weights, solver settings.

PINN training settings:

- Global/default: [configs/pinn_phase1.yaml](configs/pinn_phase1.yaml)
- Per-case PINN configs: [configs/eu](configs/eu)

Campaign-level settings:

- [configs/eu_rc_vs_pinn_campaign.yaml](configs/eu_rc_vs_pinn_campaign.yaml)

Stage2 RC-variant settings:

- [configs/eu/stage2/rc_variants.yaml](configs/eu/stage2/rc_variants.yaml)
- This is where you change RC variant scales for comparative testing.

Episode split (non-EU generic):

- [manifests/episode_split_phase1.yaml](manifests/episode_split_phase1.yaml)

### 4) Where to Run from (Main Operational Scripts)

Main EU stage1 campaign:

- [scripts/run_eu_campaign_stage1.py](scripts/run_eu_campaign_stage1.py)

Single episode MPC runner:

- [scripts/run_mpc_episode.py](scripts/run_mpc_episode.py)

QC and plots:

- [scripts/qc_eu_results.py](scripts/qc_eu_results.py)

Stage2 RC-variant workflow:

- [scripts/stage2/run_eu_rc_variant_campaign.py](scripts/stage2/run_eu_rc_variant_campaign.py)
- [scripts/stage2/analyze_rc_variants_vs_pinn.py](scripts/stage2/analyze_rc_variants_vs_pinn.py)
- [scripts/stage2/README.md](scripts/stage2/README.md)

### 5) Where Outputs Appear

Main RC vs PINN campaign results:

- [results/eu_rc_vs_pinn](results/eu_rc_vs_pinn)

Raw episode outputs:

- [results/eu_rc_vs_pinn/raw](results/eu_rc_vs_pinn/raw)

QC tables/plots:

- [results/eu_rc_vs_pinn/qc](results/eu_rc_vs_pinn/qc)

Trained models/checkpoints:

- [artifacts/eu](artifacts/eu)
