from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml
from torch.utils.data import Dataset


SECONDS_PER_DAY = 24 * 3600
SECONDS_PER_YEAR = 365 * SECONDS_PER_DAY


def load_training_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Training config must be a mapping: {path}")
    return data


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _decode_u_heating(value: float) -> float:
    if value > 200.0:
        return value - 273.15
    return value


def _cyclical_features(time_s: int) -> tuple[float, float, float, float]:
    day_phase = 2.0 * math.pi * ((time_s % SECONDS_PER_DAY) / SECONDS_PER_DAY)
    year_phase = 2.0 * math.pi * ((time_s % SECONDS_PER_YEAR) / SECONDS_PER_YEAR)
    return (
        math.sin(day_phase),
        math.cos(day_phase),
        math.sin(year_phase),
        math.cos(year_phase),
    )


@dataclass
class Sample:
    episode_id: str
    split: str
    weather_class: str
    time_s: int
    dt_s: float
    t_zone: float
    t_outdoor: float
    h_global: float
    u_heating: float
    delta_u: float
    occupied: float
    power_w: float
    features: list[float]
    target_next_t_zone: float


@dataclass
class NormalizationStats:
    feature_mean: list[float]
    feature_std: list[float]
    target_mean: float
    target_std: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TransitionDataset(Dataset[dict[str, torch.Tensor]]):
    def __init__(self, samples: list[Sample], stats: NormalizationStats) -> None:
        self.samples = samples
        self.stats = stats
        self._feature_mean = torch.tensor(stats.feature_mean, dtype=torch.float32)
        self._feature_std = torch.tensor(stats.feature_std, dtype=torch.float32)
        self._target_mean = torch.tensor(stats.target_mean, dtype=torch.float32)
        self._target_std = torch.tensor(stats.target_std, dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        sample = self.samples[index]
        features = torch.tensor(sample.features, dtype=torch.float32)
        target = torch.tensor(sample.target_next_t_zone, dtype=torch.float32)
        return {
            "features": (features - self._feature_mean) / self._feature_std,
            "target": (target - self._target_mean) / self._target_std,
            "target_raw": target,
            "t_zone": torch.tensor(sample.t_zone, dtype=torch.float32),
            "t_outdoor": torch.tensor(sample.t_outdoor, dtype=torch.float32),
            "h_global": torch.tensor(sample.h_global, dtype=torch.float32),
            "u_heating": torch.tensor(sample.u_heating, dtype=torch.float32),
            "dt_s": torch.tensor(sample.dt_s, dtype=torch.float32),
        }


def _fit_normalization(samples: list[Sample]) -> NormalizationStats:
    feature_matrix = np.asarray([sample.features for sample in samples], dtype=np.float64)
    targets = np.asarray([sample.target_next_t_zone for sample in samples], dtype=np.float64)

    feature_mean = feature_matrix.mean(axis=0)
    feature_std = feature_matrix.std(axis=0)
    feature_std[feature_std < 1e-6] = 1.0

    target_mean = float(targets.mean())
    target_std = float(targets.std())
    if target_std < 1e-6:
        target_std = 1.0

    return NormalizationStats(
        feature_mean=feature_mean.tolist(),
        feature_std=feature_std.tolist(),
        target_mean=target_mean,
        target_std=target_std,
    )


def _build_samples(dataset_root: Path, index_entries: list[dict[str, Any]]) -> list[Sample]:
    samples: list[Sample] = []
    for entry in index_entries:
        episode = _read_json(dataset_root / entry["path"])
        records = episode["records"]
        if len(records) < 2:
            continue
        for current_record, next_record in zip(records[:-1], records[1:]):
            time_s = int(current_record["time_s"])
            next_time_s = int(next_record["time_s"])
            dt_s = float(next_time_s - time_s)
            u_heat = _decode_u_heating(float(current_record["u_heating"]))
            next_u_heat = _decode_u_heating(float(next_record["u_heating"]))
            power_w = float(current_record.get("power_W", 0.0))
            occupied = float(current_record.get("occupied", False))
            cyc = _cyclical_features(time_s)
            features = [
                float(current_record["T_zone_degC"]),
                float(current_record["T_outdoor_degC"]),
                float(current_record["H_global_Wm2"]),
                u_heat,
                next_u_heat - u_heat,
                occupied,
                *cyc,
            ]
            samples.append(
                Sample(
                    episode_id=str(episode["dataset_id"]),
                    split=str(episode["split"]),
                    weather_class=str(episode["weather_class"]),
                    time_s=time_s,
                    dt_s=dt_s,
                    t_zone=float(current_record["T_zone_degC"]),
                    t_outdoor=float(current_record["T_outdoor_degC"]),
                    h_global=float(current_record["H_global_Wm2"]),
                    u_heating=u_heat,
                    delta_u=next_u_heat - u_heat,
                    occupied=occupied,
                    power_w=power_w,
                    features=features,
                    target_next_t_zone=float(next_record["T_zone_degC"]),
                )
            )
    return samples


def _group_samples_by_episode(samples: list[Sample]) -> dict[str, list[Sample]]:
    grouped: dict[str, list[Sample]] = {}
    for sample in samples:
        grouped.setdefault(sample.episode_id, []).append(sample)
    return grouped


def build_datasets(config: dict[str, Any], root: Path) -> dict[str, Any]:
    data_cfg = config["data"]
    dataset_root = root / data_cfg["dataset_root"]
    index_entries = _read_json(dataset_root / "index.json")

    train_entries = [entry for entry in index_entries if entry["split"] == "train"]
    val_entries = [entry for entry in index_entries if entry["split"] == "val"]
    test_entries = [entry for entry in index_entries if entry["split"] == "test"]

    train_samples = _build_samples(root, train_entries)
    val_samples = _build_samples(root, val_entries)
    test_samples = _build_samples(root, test_entries)

    stats = _fit_normalization(train_samples)
    return {
        "train_dataset": TransitionDataset(train_samples, stats),
        "val_dataset": TransitionDataset(val_samples, stats),
        "test_dataset": TransitionDataset(test_samples, stats),
        "train_samples": train_samples,
        "val_samples": val_samples,
        "test_samples": test_samples,
        "train_episodes": _group_samples_by_episode(train_samples),
        "val_episodes": _group_samples_by_episode(val_samples),
        "test_episodes": _group_samples_by_episode(test_samples),
        "stats": stats,
        "feature_names": [
            "T_zone_degC",
            "T_outdoor_degC",
            "H_global_Wm2",
            "u_heating_degC",
            "delta_u_heating_degC",
            "occupied",
            "tod_sin",
            "tod_cos",
            "year_sin",
            "year_cos",
        ],
    }
