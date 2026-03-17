#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pinn_model import SingleZonePINN, build_datasets, load_training_config, train_model
from pinn_model.training import set_seed


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a physics-regularized PINN surrogate for Phase 1.")
    parser.add_argument("--config", default="configs/pinn_phase1.yaml")
    parser.add_argument("--artifact-dir", default="artifacts/pinn_phase1")
    args = parser.parse_args()

    root = ROOT
    config = load_training_config(root / args.config)
    set_seed(int(config["training"]["seed"]))

    datasets = build_datasets(config, root)
    model = SingleZonePINN(
        input_dim=len(datasets["feature_names"]),
        hidden_dim=int(config["model"]["hidden_dim"]),
        depth=int(config["model"]["depth"]),
        dropout=float(config["model"].get("dropout", 0.0)),
    )

    result = train_model(model, datasets, config, root / args.artifact_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
