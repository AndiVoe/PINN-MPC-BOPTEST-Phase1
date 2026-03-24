#!/usr/bin/env python3
"""Compare original vs improved PINN models."""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent

def load_history(path):
    """Load training history."""
    with open(path, 'r') as f:
        return json.load(f)

def load_metrics(path):
    """Load metrics."""
    with open(path, 'r') as f:
        data = json.load(f)
        return data.get("validation", data)

# Load data
hist_orig = load_history(ROOT / "artifacts/pinn_phase1/history.json")
hist_impr = load_history(ROOT / "artifacts/pinn_phase1_improved/history.json")
metrics_orig = load_metrics(ROOT / "artifacts/pinn_phase1/metrics.json")
metrics_impr = load_metrics(ROOT / "artifacts/pinn_phase1_improved/metrics.json")

# Extract arrays
epochs_orig = [h["epoch"] for h in hist_orig]
train_loss_orig = [h["train_loss"] for h in hist_orig]
val_loss_orig = [h["val_loss"] for h in hist_orig]

epochs_impr = [h["epoch"] for h in hist_impr]
train_loss_impr = [h["train_loss"] for h in hist_impr]
val_loss_impr = [h["val_loss"] for h in hist_impr]

if not train_loss_orig or not val_loss_orig or not train_loss_impr or not val_loss_impr:
    raise RuntimeError("Training histories are empty or missing required loss fields.")


def safe_pct(numerator: float, denominator: float) -> float:
    return 100.0 * float(numerator) / max(float(abs(denominator)), 1e-12)

# Print summary
print("=" * 70)
print("PINN MODEL COMPARISON: Original vs Improved")
print("=" * 70)
print()
print("TRAINING CONFIGURATION:")
print("-" * 70)
print(f"{'Metric':<30} {'Original':<20} {'Improved':<20}")
print("-" * 70)
print(f"{'Epochs':<30} {'150':<20} {'80':<20}")
print(f"{'Batch Size':<30} {'256':<20} {'64':<20}")
print(f"{'Lambda Physics':<30} {'0.01':<20} {'0.1':<20}")
print(f"{'Weight Decay':<30} {'1e-5':<20} {'1e-4':<20}")
print()

print("FINAL EPOCH LOSSES:")
print("-" * 70)
print(f"{'Metric':<30} {'Original':<20} {'Improved':<20}")
print("-" * 70)
print(f"{'Final Train Loss':<30} {train_loss_orig[-1]:<20.6f} {train_loss_impr[-1]:<20.6f}")
print(f"{'Final Val Loss':<30} {val_loss_orig[-1]:<20.6f} {val_loss_impr[-1]:<20.6f}")
print(f"{'Best Val Loss':<30} {min(val_loss_orig):<20.6f} {min(val_loss_impr):<20.6f}")
print(f"{'Best Epoch':<30} {epochs_orig[np.argmin(val_loss_orig)]:<20.0f} {epochs_impr[np.argmin(val_loss_impr)]:<20.0f}")
print()

# Convergence analysis
print("OVERFITTING ANALYSIS:")
print("-" * 70)
early_idx_orig = min(4, len(val_loss_orig) - 1)
early_idx_impr = min(4, len(val_loss_impr) - 1)
gap_orig_early = safe_pct(train_loss_orig[early_idx_orig] - val_loss_orig[early_idx_orig], val_loss_orig[early_idx_orig])
gap_orig_final = safe_pct(train_loss_orig[-1] - val_loss_orig[-1], val_loss_orig[-1])
gap_impr_early = safe_pct(train_loss_impr[early_idx_impr] - val_loss_impr[early_idx_impr], val_loss_impr[early_idx_impr])
gap_impr_final = safe_pct(train_loss_impr[-1] - val_loss_impr[-1], val_loss_impr[-1])

print(f"{'Metric':<30} {'Original':<20} {'Improved':<20}")
print("-" * 70)
print(f"{'Train-Val Gap (early)':<30} {gap_orig_early:<20.1f}% {gap_impr_early:<20.1f}%")
print(f"{'Train-Val Gap (final)':<30} {gap_orig_final:<20.1f}% {gap_impr_final:<20.1f}%")
print(f"{'Val Loss Volatility (std)':<30} {np.std(val_loss_orig):<20.5f} {np.std(val_loss_impr):<20.5f}")
print(f"{'Val Loss Improvement':<30} {'-':<20} {safe_pct(val_loss_orig[-1] - val_loss_impr[-1], val_loss_orig[-1]):<20.1f}%")
print()

print("VALIDATION METRICS:")
print("-" * 70)
print(f"{'Metric':<30} {'Original':<20} {'Improved':<20}")
print("-" * 70)
rmse_orig = metrics_orig.get("rmse_degC", "N/A")
rmse_impr = metrics_impr.get("rmse_degC", "N/A")
mae_orig = metrics_orig.get("mae_degC", "N/A")
mae_impr = metrics_impr.get("mae_degC", "N/A")

if isinstance(rmse_orig, (int, float)) and isinstance(rmse_impr, (int, float)):
    print(f"{'Val RMSE (°C)':<30} {rmse_orig:<20.4f} {rmse_impr:<20.4f}")
if isinstance(mae_orig, (int, float)) and isinstance(mae_impr, (int, float)):
    print(f"{'Val MAE (°C)':<30} {mae_orig:<20.4f} {mae_impr:<20.4f}")

print()
print("=" * 70)

# Create comparison plot
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

ax = axes[0]
ax.semilogy(epochs_orig, train_loss_orig, 'o-', label='Original: Train', alpha=0.7, markersize=3)
ax.semilogy(epochs_orig, val_loss_orig, 's-', label='Original: Val', alpha=0.7, markersize=3)
ax.semilogy(epochs_impr, train_loss_impr, 'o:', label='Improved: Train', alpha=0.7, markersize=3, linewidth=2)
ax.semilogy(epochs_impr, val_loss_impr, 's:', label='Improved: Val', alpha=0.7, markersize=3, linewidth=2)
ax.axvline(20, color='red', linestyle='--', alpha=0.5, label='Epoch 20 (stagnation point)')
ax.set_xlabel('Epoch')
ax.set_ylabel('Loss')
ax.set_title('Training Convergence: Original vs Improved')
ax.legend()
ax.grid(True, alpha=0.3)

ax = axes[1]
ax.plot(epochs_orig, val_loss_orig, 'o-', label='Original', alpha=0.7, markersize=4)
ax.plot(epochs_impr, val_loss_impr, 's-', label='Improved', alpha=0.7, markersize=4, linewidth=2)
ax.axhline(min(val_loss_orig), color='C0', linestyle=':', alpha=0.5)
ax.axhline(min(val_loss_impr), color='C1', linestyle=':', alpha=0.5)
ax.fill_between(epochs_orig, val_loss_orig, alpha=0.2)
ax.fill_between(epochs_impr, val_loss_impr, alpha=0.2)
ax.set_xlabel('Epoch')
ax.set_ylabel('Validation Loss')
ax.set_title('Validation Loss Comparison (Linear Scale)')
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(ROOT / "artifacts/pinn_phase1_improved/comparison.png", dpi=150, bbox_inches='tight')
print("\nComparison plot saved: artifacts/pinn_phase1_improved/comparison.png")
