# Quick Start: Comfort Feasibility Analysis

This guide walks you through running the preflight actuator check and PINN variants to validate the thermal comfort feasibility hypothesis.

## Step 1: Preflight Actuator Validation

Before running MPC benchmarks, verify that your BOPTEST test case has responsive heating:

```bash
# With BOPTEST running on localhost:8000
python scripts/preflight_actuator_check.py \
  --case bestest_hydronic_heat_pump \
  --url http://127.0.0.1:8000 \
  --output-dir artifacts/preflight_results
```

Expected outputs:
- **PASS:** Heating rise ≥1.5K → Case is responsive, proceed to benchmarking
- **WARN:** Heating rise 0.5-1.5K → Case is weak, prepare for poor control
- **FAIL:** Heating rise <0.5K → Case is non-responsive, skip benchmarking

**Interpretation:** If most/all test cases produce upper-bound violations, but heating responsiveness is normal, then the issue is **feasibility** (insufficient cooling capacity), not control quality.

## Step 2: Train PINN Variants

Run both variants (A & B) on your phase1 dataset:

```bash
python scripts/train_pinn_variants.py \
  --variants AB \
  --artifact-dir artifacts \
  --configs-dir configs
```

This will:
1. Load `configs/pinn_phase1_variant_a.yaml` and `configs/pinn_phase1_variant_b.yaml`
2. Build datasets from `datasets/phase1_singlezone/`
3. Train both models with different loss weighting strategies
4. Save results to:
   - `artifacts/pinn_phase1_variant_a_gradient_balance/`
   - `artifacts/pinn_phase1_variant_b_uncertainty/`
   - `artifacts/variant_training_summary.json`

Expected duration: 5-15 minutes per variant (depending on CPU/GPU)

## Step 3: Compare Results

After training, examine the results:

```bash
# View training summary
cat artifacts/variant_training_summary.json

# Compare convergence (Variant A)
python -c "import json; h=json.load(open('artifacts/pinn_phase1_variant_a_gradient_balance/history.json')); print('Best epoch:', h[-1]['epoch']); print('Final loss:', h[-1]['val_loss'])"

# Compare convergence (Variant B)
python -c "import json; h=json.load(open('artifacts/pinn_phase1_variant_b_uncertainty/history.json')); print('Best epoch:', h[-1]['epoch']); print('Final loss:', h[-1]['val_loss'])"

# View final metrics (Variant A)
python -c "import json; m=json.load(open('artifacts/pinn_phase1_variant_a_gradient_balance/metrics.json')); print('Val RMSE:', m['validation']['rmse_degC']); print('Test RMSE:', m['test']['rmse_degC'])"

# View final metrics (Variant B)
python -c "import json; m=json.load(open('artifacts/pinn_phase1_variant_b_uncertainty/metrics.json')); print('Val RMSE:', m['validation']['rmse_degC']); print('Test RMSE:', m['test']['rmse_degC']); print('Learned uncertainties:', {k:v for k,v in m['loss_weighting'].items() if 'sigma' in k})"
```

## Step 4: Run MPC Benchmarks & Compare Discomfort

After training, proceed with MPC benchmarking using both variants:

```bash
# Benchmark Variant A
python scripts/run_mpc_episode.py \
  --model artifacts/pinn_phase1_variant_a_gradient_balance/best_model.pt \
  --case bestest_hydronic_heat_pump

# Benchmark Variant B
python scripts/run_mpc_episode.py \
  --model artifacts/pinn_phase1_variant_b_uncertainty/best_model.pt \
  --case bestest_hydronic_heat_pump

# Generate discomfort comparison
# (Assuming your benchmark script generates discomfort_comparison.csv)
head -20 results/mpc_phase1/discomfort_comparison.csv
```

## Key Hypotheses to Validate

### Hypothesis 1: Feasibility Limits Exist
- **Evidence:** PINN and RC model have similar upper-bound violation rates
- **Indicator:** Look at `discomfort_comparison.csv` - if both models show ~20% upper violations, the problem is infeasible, not training

### Hypothesis 2: Loss Weighting Helps Model Learning
- **Evidence:** Both variants converge to similar RMSE despite different loss strategies
- **Indicator:** `variant_training_summary.json` shows both A and B have similar `best_val_loss`

### Hypothesis 3: Variant B Learns Confidence Bounds
- **Evidence:** `log_sigma_physics` is learned and non-zero in metrics.json
- **Indicator:** `loss_weighting.log_sigma_physics` should show model uncertainty is highest in warm periods

## Expected Outcomes

| Finding | Interpretation |
|---------|-----------------|
| PINN & RCuppers are ~equal | Problem is infeasibility (can't cool with heating-only) |
| Variant A & B have equal RMSE | Loss weighting doesn't hurt fit quality |
| Variant B uncertainty high in warm periods | Model correctly identifies infeasible regions |
| Heating responsiveness is PASS | Control authority is adequate; violations are truly infeasible |

## Troubleshooting

**Variant training fails:**
- Check that `configs/pinn_phase1_variant_*.yaml` files exist
- Confirm `datasets/phase1_singlezone/` has training data
- Try with smaller batch size: edit config `training.batch_size: 128`

**Preflight check shows FAIL on all cases:**
- Check BOPTEST server is running and accessible
- Try increasing `--pulse-duration-s` (default 3600s = 1h)
- May indicate system-level control issues; consult BOPTEST docs

**MPC benchmarking shows huge discomfort:**
- If **both** PINN and RC fail equally → Problem is infeasible (expected)
- If **only** PINN fails → PINN training issue (unexpected with variants A & B)
- Check that MPC actually uses the control objectives (oveTSet_u setpoint)

## References

- Kendall et al., 2018. "Multi-Task Learning Using Uncertainty to Weigh Losses" (arXiv:1802.07335)
- Gradient balancing: Custom approach based on multi-task learning theory
