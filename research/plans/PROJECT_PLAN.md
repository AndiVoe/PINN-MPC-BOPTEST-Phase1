# Project Plan

## Objective

Develop and validate a PINN-based surrogate modeling and MPC benchmarking workflow for building thermal control, with clear reproducibility and traceability across datasets, model artifacts, and evaluation results.

## Work Packages

- WP1 Data and Contracts
	- Define and validate input/output contracts.
	- Generate structured BOPTEST datasets.
	- Ensure schema and file consistency checks.

- WP2 Surrogate Model (PINN)
	- Train and validate PINN surrogate models.
	- Track training metrics and model checkpoints.
	- Compare baseline and alternative training settings.

- WP3 MPC and Benchmarking
	- Run RC vs PINN MPC episodes on test/future-test splits.
	- Compute and compare comfort and energy KPIs.
	- Automate campaign execution and failure diagnostics.

## Deliverables

- Validated dataset and signal contracts.
- Reproducible PINN training artifacts.
- RC vs PINN MPC benchmark results with comparable KPI reports.
- Campaign logs and traceability metadata for publication/review.

## Current Priorities

- Stabilize end-to-end campaign reliability.
- Keep KPI comparability checks strict and explicit.
- Maintain reproducible scripts and artifacts for review/publication.
