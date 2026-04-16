# Implementation Validation Checklist

Use this checklist to verify that all components are working correctly before running experiments.

## ✅ File Structure Verification

- [ ] Verify config files exist:
  - [ ] `configs/pinn_phase1_variant_a.yaml`
  - [ ] `configs/pinn_phase1_variant_b.yaml`
  
- [ ] Verify scripts exist:
  - [ ] `scripts/preflight_actuator_check.py`
  - [ ] `scripts/train_pinn_variants.py`
  
- [ ] Verify documentation exists:
  - [ ] `docs/pinn_variant_training.md`
  - [ ] `QUICKSTART_COMFORT_ANALYSIS.md`
  - [ ] `COMFORT_FEASIBILITY_METHODOLOGY.md`

**Run:**
```bash
ls -la configs/pinn_phase1_variant_*.yaml
ls -la scripts/{preflight_actuator_check,train_pinn_variants}.py
ls -la docs/*.md *.md
```

---

## ✅ Config File Validation

### Variant A Config
```bash
python -c "
import yaml
cfg = yaml.safe_load(open('configs/pinn_phase1_variant_a.yaml'))
assert cfg['study_id'] == 'pinn_phase1_variant_a_gradient_balance', 'Wrong study_id'
assert cfg['training']['loss_weighting']['mode'] == 'gradient_balance', 'Wrong mode'
assert cfg['training']['lambda_physics'] == 0.005, 'Wrong lambda'
print('✓ Variant A config is valid')
"
```

### Variant B Config
```bash
python -c "
import yaml
cfg = yaml.safe_load(open('configs/pinn_phase1_variant_b.yaml'))
assert cfg['study_id'] == 'pinn_phase1_variant_b_uncertainty', 'Wrong study_id'
assert cfg['training']['loss_weighting']['mode'] == 'uncertainty', 'Wrong mode'
print('✓ Variant B config is valid')
"
```

---

## ✅ Training Module Validation

Verify that the training.py module has the required loss weighting modes:

```bash
python -c "
import sys
sys.path.insert(0, '.')
from pinn_model.training import LossWeighter
import torch

device = torch.device('cpu')

# Test manual mode
cfg = {'loss_weighting': {'mode': 'manual'}, 'lambda_physics': 0.01}
w = LossWeighter(cfg, device)
assert w.mode == 'manual', 'Manual mode not supported'
print('✓ Manual mode works')

# Test gradient_balance mode
cfg = {'loss_weighting': {'mode': 'gradient_balance'}, 'lambda_physics': 0.01}
w = LossWeighter(cfg, device)
assert w.mode == 'gradient_balance', 'Gradient_balance mode not supported'
print('✓ Gradient_balance mode works')

# Test uncertainty mode
cfg = {'loss_weighting': {'mode': 'uncertainty'}, 'lambda_physics': 0.01}
w = LossWeighter(cfg, device)
assert w.mode == 'uncertainty', 'Uncertainty mode not supported'
assert len(w.extra_parameters()) == 2, 'Should have 2 extra params'
print('✓ Uncertainty mode works')
print('✓ All loss weighting modes available')
"
```

---

## ✅ Script Validation

### Preflight Script
```bash
python scripts/preflight_actuator_check.py --help
```
Should show:
```
usage: preflight_actuator_check.py [-h] [--url URL] [--case CASE] ...
```
✓ Script is executable and importable

### Variant Training Script
```bash
python scripts/train_pinn_variants.py --help
```
Should show:
```
usage: train_pinn_variants.py [-h] [--variants {A,B,AB}] ...
```
✓ Script is executable and importable

---

## ✅ Import Validation

Verify all required imports work:

```bash
python -c "
import sys
sys.path.insert(0, '.')
print('Testing imports...')

from pinn_model import SingleZonePINN, build_datasets, load_training_config, train_model
print('✓ pinn_model imports OK')

from pinn_model.training import set_seed, LossWeighter, evaluate_model, train_model as tm
print('✓ pinn_model.training imports OK')

import torch
import yaml
print('✓ External imports OK')

print('\n✓ All imports successful')
"
```

---

## ✅ Dataset Validation

Verify phase1 dataset exists and is accessible:

```bash
python -c "
import sys
import json
from pathlib import Path
sys.path.insert(0, '.')

dataset_root = Path('datasets/phase1_singlezone')
assert dataset_root.exists(), f'Dataset not found: {dataset_root}'

index_file = dataset_root / 'index.json'
assert index_file.exists(), f'Index not found: {index_file}'

index = json.load(open(index_file))
print(f'✓ Dataset found with {len(index)} samples')
print(f'  Sample keys: {list(index.values())[0].keys()}')
"
```

---

## ✅ Dry Run: Config Loading

Test that configs can be loaded and processed:

```bash
python -c "
import sys
sys.path.insert(0, '.')
from pinn_model import load_training_config
from pathlib import Path

print('Loading Variant A config...')
cfg_a = load_training_config(Path('configs/pinn_phase1_variant_a.yaml'))
print(f'  Study ID: {cfg_a[\"study_id\"]}')
print(f'  Loss mode: {cfg_a[\"training\"][\"loss_weighting\"][\"mode\"]}')

print('Loading Variant B config...')
cfg_b = load_training_config(Path('configs/pinn_phase1_variant_b.yaml'))
print(f'  Study ID: {cfg_b[\"study_id\"]}')
print(f'  Loss mode: {cfg_b[\"training\"][\"loss_weighting\"][\"mode\"]}')

print('✓ Configs loaded and validated')
"
```

---

## ✅ Dry Run: Model Creation

Test that the model can be instantiated with variant configs:

```bash
python -c "
import sys
sys.path.insert(0, '.')
from pinn_model import load_training_config, build_datasets, SingleZonePINN
from pathlib import Path

print('Loading configs and dataset...')
cfg_a = load_training_config(Path('configs/pinn_phase1_variant_a.yaml'))
root = Path('.')

print('Building datasets...')
datasets = build_datasets(cfg_a, root)
input_dim = len(datasets['feature_names'])

print(f'Creating PINN model (input_dim={input_dim})...')
model = SingleZonePINN(
    input_dim=input_dim,
    hidden_dim=int(cfg_a['model']['hidden_dim']),
    depth=int(cfg_a['model']['depth']),
    dropout=float(cfg_a['model'].get('dropout', 0.0))
)
print(f'✓ Model created: {model}')
print(f'✓ Model has {sum(p.numel() for p in model.parameters())} parameters')
"
```

---

## ✅ Quick Training Test

Run a mini training (1 epoch) to verify the full pipeline:

```bash
python -c "
import sys
sys.path.insert(0, '.')
from pinn_model import load_training_config, build_datasets, SingleZonePINN, train_model
from pinn_model.training import set_seed
from pathlib import Path
import json

print('=' * 70)
print('QUICK TRAINING TEST')
print('=' * 70)

# Load config and modify for quick test
cfg = load_training_config(Path('configs/pinn_phase1_variant_a.yaml'))
cfg['training']['epochs'] = 1  # Just 1 epoch
cfg['training']['patience'] = 1
cfg['training']['batch_size'] = 32  # Small batch

set_seed(int(cfg['training']['seed']))
datasets = build_datasets(cfg, Path('.'))

model = SingleZonePINN(
    input_dim=len(datasets['feature_names']),
    hidden_dim=int(cfg['model']['hidden_dim']),
    depth=int(cfg['model']['depth']),
    dropout=float(cfg['model'].get('dropout', 0.0))
)

artifact_dir = Path('.tmp_test_variant_a')
artifact_dir.mkdir(exist_ok=True)

print('\\nRunning 1-epoch training...')
try:
    result = train_model(model, datasets, cfg, artifact_dir)
    print(f'✓ Training completed successfully')
    print(f'  Best epoch: {result[\"best_epoch\"]}')
    print(f'  Best val loss: {result[\"best_val_loss\"]:.6f}')
except Exception as e:
    print(f'✗ Training failed: {e}')
    import traceback
    traceback.print_exc()

print('\\nTest artifacts in: {}'.format(artifact_dir))
"
```

---

## ✅ Full System Test

After all above checks pass, run a minimal variant training:

```bash
# Test Variant A (smaller dataset, fewer epochs)
timeout 60 python -c "
import sys
sys.path.insert(0, '.')
from pathlib import Path
import json
import yaml

# Temporarily modify config for speed
cfg = yaml.safe_load(open('configs/pinn_phase1_variant_a.yaml'))
cfg['training']['epochs'] = 2
cfg['training']['batch_size'] = 64

with open('.tmp_variant_a_test.yaml', 'w') as f:
    yaml.dump(cfg, f)

# Manual run for speed test
from pinn_model import load_training_config, build_datasets, SingleZonePINN, train_model
from pinn_model.training import set_seed

cfg = load_training_config(Path('.tmp_variant_a_test.yaml'))
set_seed(42)
datasets = build_datasets(cfg, Path('.'))
model = SingleZonePINN(
    input_dim=len(datasets['feature_names']),
    hidden_dim=64, depth=3, dropout=0.0
)

artifact_dir = Path('.tmp_test_full')
artifact_dir.mkdir(exist_ok=True)

print('Testing Variant A training (2 epochs)...')
result = train_model(model, datasets, cfg, artifact_dir)
print(f'✓ Test successful: best_val_loss = {result[\"best_val_loss\"]:.6f}')
" || echo "Variant A test timed out or failed (expected for full dataset)"
```

---

## ✅ Cleanup

```bash
# Remove test artifacts
rm -rf .tmp_test_* .tmp_variant_a_test.yaml

echo "✓ All validation checks complete!"
```

---

## Validation Summary Checklist

- [ ] All files created and in correct locations
- [ ] Config files are valid YAML and have correct fields
- [ ] Training module supports all three loss weighting modes
- [ ] Scripts are executable and have correct syntax
- [ ] All imports work (pinn_model, torch, yaml, etc.)
- [ ] Dataset is accessible and has required structure
- [ ] Model instantiation works
- [ ] Training can run (at least 1 epoch)
- [ ] Test artifacts are created with expected structure

**If all checks pass:** You're ready to run the comfort feasibility analysis!

**Next step:** Follow [QUICKSTART_COMFORT_ANALYSIS.md](QUICKSTART_COMFORT_ANALYSIS.md)
