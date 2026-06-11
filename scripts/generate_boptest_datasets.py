#!/usr/bin/env python3
"""
WP2 dataset generator for BOPTEST episodes.

- Uses manifest-driven episode definitions.
- Resolves signals with candidate lists to tolerate testcase differences.
- Exports JSON datasets that match data_contract/dataset_schema.json.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path
from typing import Any

import requests
import yaml


class BoptestConnectionError(RuntimeError):
    pass


class BoptestClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.testid: str | None = None
        self._assert_connection()

    def _assert_connection(self) -> None:
        try:
            resp = requests.get(f"{self.base_url}/version", timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise BoptestConnectionError(
                f"Could not connect to BOPTEST at {self.base_url}."
            ) from exc

    def _require_testid(self) -> str:
        if not self.testid:
            raise RuntimeError("No testcase selected.")
        return self.testid

    def select_test_case(self, case_name: str) -> str:
        for endpoint in (
            f"{self.base_url}/testcases/{case_name}/select-true",
            f"{self.base_url}/testcases/{case_name}/select",
        ):
            resp = requests.post(endpoint, timeout=900)
            if resp.ok:
                self.testid = resp.json().get("testid")
                if self.testid:
                    return self.testid
        raise RuntimeError(f"Failed to select testcase: {case_name}")

    def attach_testid(self, testid: str) -> None:
        """Attach to an already-Running testid, verifying its status."""
        resp = requests.get(f"{self.base_url}/status/{testid}", timeout=30)
        resp.raise_for_status()
        try:
            data = resp.json()
            status = data.get("payload") if isinstance(data, dict) else str(data)
        except Exception:
            status = resp.text.strip('"')
        if status != "Running":
            raise RuntimeError(f"Testid {testid} is not Running (status: {status}).")
        self.testid = testid
        print(f"Attached to existing Running testid: {testid}")

    def stop(self) -> bool:
        testid = self._require_testid()
        try:
            resp = requests.put(f"{self.base_url}/stop/{testid}", timeout=60)
            if not resp.ok:
                return False
            try:
                data = resp.json()
                return bool(data.get("payload", True))
            except Exception:
                return True
        except requests.RequestException:
            return False

    def wait_running(self, timeout_s: int = 1200, poll_interval_s: int = 5) -> None:
        testid = self._require_testid()
        start = time.time()
        while time.time() - start < timeout_s:
            resp = requests.get(f"{self.base_url}/status/{testid}", timeout=60)
            resp.raise_for_status()
            status = ""
            try:
                data = resp.json()
                status = data.get("payload") if isinstance(data, dict) else str(data)
            except Exception:
                status = resp.text.strip('"')
            elapsed = int(time.time() - start)
            print(f"Startup status: {status} (elapsed {elapsed}s)")
            if status == "Running":
                return
            time.sleep(max(1, poll_interval_s))
        raise TimeoutError("Timed out waiting for Running state.")

    def set_scenario(self, scenario: dict[str, Any]) -> None:
        if not scenario:
            return
        testid = self._require_testid()
        resp = requests.put(f"{self.base_url}/scenario/{testid}", json=scenario, timeout=120)
        if not resp.ok:
            # Not all deployments expose scenario endpoint equally.
            return

    def initialize(self, start_time_s: int, warmup_period_s: int) -> dict[str, Any]:
        testid = self._require_testid()
        resp = requests.put(
            f"{self.base_url}/initialize/{testid}",
            json={"start_time": start_time_s, "warmup_period": warmup_period_s},
            timeout=1200,
        )
        resp.raise_for_status()
        return resp.json().get("payload", {})

    def set_step(self, step_s: int) -> None:
        testid = self._require_testid()
        resp = requests.put(f"{self.base_url}/step/{testid}", json={"step": step_s}, timeout=60)
        resp.raise_for_status()

    def get_inputs(self) -> dict[str, Any]:
        testid = self._require_testid()
        resp = requests.get(f"{self.base_url}/inputs/{testid}", timeout=60)
        resp.raise_for_status()
        return resp.json().get("payload", {})

    def get_forecast(self, points: list[str], horizon_s: int, interval_s: int) -> dict[str, list[float]]:
        testid = self._require_testid()
        resp = requests.put(
            f"{self.base_url}/forecast/{testid}",
            json={"point_names": points, "horizon": horizon_s, "interval": interval_s},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("payload", {})

    def advance(self, u: dict[str, float]) -> dict[str, Any]:
        testid = self._require_testid()
        resp = requests.post(f"{self.base_url}/advance/{testid}", json=u, timeout=300)
        resp.raise_for_status()
        return resp.json().get("payload", {})


def pick_first(candidates: list[str], available: set[str]) -> str | None:
    for name in candidates:
        if name in available:
            return name
    return None


def pick_configured_or_candidate(
    mappings: dict[str, Any],
    configured_key: str,
    candidates_key: str,
    available: set[str],
) -> str | None:
    """Resolve a signal by preferring explicit mapping, then candidate fallback."""
    configured = mappings.get(configured_key)
    if isinstance(configured, str) and configured in available:
        return configured
    candidates = mappings.get(candidates_key, [])
    if isinstance(candidates, list):
        return pick_first([str(x) for x in candidates], available)
    return None


def to_deg_c(value: float | None) -> float | None:
    if value is None:
        return None
    if value > 200.0:
        return value - 273.15
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be map: {path}")
    return data


def resolve_boptest_url(url: str) -> str:
    candidates = [url.rstrip("/")]
    if "127.0.0.1" in url or "localhost" in url:
        candidates.extend([
            "http://127.0.0.1:5000",
            "http://127.0.0.1:8000",
            "http://localhost:5000",
            "http://localhost:8000",
        ])

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            resp = requests.get(f"{candidate}/version", timeout=3)
            if resp.ok:
                return candidate
        except requests.RequestException:
            continue

    raise BoptestConnectionError(
        "No reachable BOPTEST API found. Checked: " + ", ".join(seen)
    )


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_episode(
    client: BoptestClient,
    case_name: str,
    mappings: dict[str, Any],
    episode: dict[str, Any],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    step_s = int(defaults["control_interval_s"])
    length_days = int(episode.get("episode_length_days", defaults["episode_length_days"]))
    n_steps = int(length_days * 24 * 3600 / step_s)
    warmup_s = int(episode.get("warmup_period_s", defaults["warmup_period_s"]))
    start_time_s = int(episode.get("start_time_s", defaults["start_time_s"]))

    scenario = episode.get("scenario", {})
    client.set_scenario(scenario)

    init_payload = client.initialize(start_time_s=start_time_s, warmup_period_s=warmup_s)
    client.set_step(step_s)

    inputs = client.get_inputs()
    input_names = set(inputs.keys())
    available_names = set(init_payload.keys()) | input_names

    zone_signal = pick_first(mappings["zone_temp_candidates"], available_names)
    outdoor_signal = pick_configured_or_candidate(
        mappings,
        "outdoor_temp_signal",
        "outdoor_temp_candidates",
        available_names,
    )
    solar_signal = pick_configured_or_candidate(
        mappings,
        "solar_signal",
        "solar_candidates",
        available_names,
    )

    u_val_name = pick_configured_or_candidate(
        mappings,
        "control_value_signal",
        "control_value_candidates",
        input_names,
    )
    u_act_name = pick_configured_or_candidate(
        mappings,
        "control_activate_signal",
        "control_activate_candidates",
        input_names,
    )

    policy = defaults.get("control_policy", {})
    seed = int(policy.get("seed_base", 1)) + abs(hash(episode["id"])) % 100000
    rng = random.Random(seed)

    setpoint_min = float(policy.get("setpoint_min_degC", 19.0))
    setpoint_max = float(policy.get("setpoint_max_degC", 24.0))

    records: list[dict[str, Any]] = []
    heating_proxy_signal: str | None = None

    current = init_payload
    t_s = start_time_s
    for _ in range(n_steps):
        control_cmd: dict[str, float] = {}
        u_heating = 0.0

        if u_val_name:
            u_heating = rng.uniform(setpoint_min, setpoint_max)
            val = u_heating + 273.15 if "Set" in u_val_name or "TSet" in u_val_name else u_heating
            control_cmd[u_val_name] = float(val)
            if u_act_name:
                control_cmd[u_act_name] = 1.0

        payload = client.advance(control_cmd)

        if u_val_name is None:
            if heating_proxy_signal is None:
                for key in payload.keys():
                    if re.search(r"(reaQHea|QHea|PHea|hea)" , key, flags=re.IGNORECASE):
                        if isinstance(payload.get(key), (int, float)):
                            heating_proxy_signal = key
                            break
            if heating_proxy_signal and isinstance(payload.get(heating_proxy_signal), (int, float)):
                u_heating = float(payload[heating_proxy_signal])

        t_zone = to_deg_c(payload.get(zone_signal)) if zone_signal else None

        T_out = None
        H_glo = None
        if outdoor_signal and solar_signal:
            try:
                fc = client.get_forecast([outdoor_signal, solar_signal], horizon_s=step_s, interval_s=step_s)
                if outdoor_signal in fc and fc[outdoor_signal]:
                    T_out = to_deg_c(float(fc[outdoor_signal][0]))
                if solar_signal in fc and fc[solar_signal]:
                    H_glo = float(fc[solar_signal][0])
            except Exception:
                T_out = to_deg_c(payload.get(outdoor_signal))
                H_glo = payload.get(solar_signal)

        if t_zone is None:
            # Hard fail per episode for schema compliance.
            raise RuntimeError("Could not resolve T_zone signal for episode.")

        if T_out is None:
            T_out = 0.0
        if H_glo is None:
            H_glo = 0.0

        rec = {
            "time_s": t_s,
            "T_zone_degC": float(t_zone),
            "T_outdoor_degC": float(T_out),
            "H_global_Wm2": float(H_glo),
            "u_heating": float(u_heating),
        }

        p_terms = [v for k, v in payload.items() if isinstance(v, (int, float)) and ("reaP" in k or "Power" in k)]
        if p_terms:
            power_w = float(sum(float(x) for x in p_terms if x is not None))
            rec["power_W"] = power_w
            rec["energy_Wh_step"] = power_w * step_s / 3600.0

        records.append(rec)
        current = payload
        t_s += step_s

    return {
        "dataset_id": episode["id"],
        "split": episode["split"],
        "case_name": case_name,
        "weather_class": episode["weather_class"],
        "control_interval_s": step_s,
        "horizon_s": step_s,
        "records": records,
        "meta": {
            "scenario": scenario,
            "control_signal": u_val_name,
            "activate_signal": u_act_name,
            "heating_proxy_signal": heating_proxy_signal,
            "zone_signal": zone_signal,
            "generator": "scripts/generate_boptest_datasets.py",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate BOPTEST datasets for PINN training.")
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--case", default="singlezone_commercial_hydronic")
    parser.add_argument("--manifest", default="manifests/episode_split_phase1.yaml")
    parser.add_argument("--output", default="datasets/phase1_singlezone")
    parser.add_argument("--max-episodes", type=int, default=0, help="0 means all")
    parser.add_argument("--startup-timeout-s", type=int, default=1800)
    parser.add_argument("--startup-poll-interval-s", type=int, default=5)
    parser.add_argument("--reuse-testid", default="", help="Attach to an already-Running testid, skipping select+wait.")
    parser.add_argument("--recover-from-queued", action="store_true", help="If startup stays Queued, stop test and retry selection once.")
    parser.add_argument("--resume", action="store_true", help="Skip episodes that already have a valid output JSON file.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    manifest = load_yaml(root / args.manifest)
    defaults = manifest["defaults"]
    case_mappings = manifest["case_mappings"][args.case]
    episodes = manifest["episodes"]
    if args.max_episodes > 0:
        episodes = episodes[: args.max_episodes]

    output_dir = root / args.output
    json_dir = output_dir / "json"
    ensure_dir(json_dir)

    if args.resume:
        pending: list[dict[str, Any]] = []
        for episode in episodes:
            out_path = json_dir / f"{episode['id']}.json"
            if out_path.exists():
                continue
            pending.append(episode)
        print(f"Resume mode: {len(pending)} pending episode(s) out of {len(episodes)} total.")
        episodes = pending

    resolved_url = resolve_boptest_url(args.url)
    print(f"Using BOPTEST URL: {resolved_url}")
    client = BoptestClient(resolved_url)
    owns_test_session = not bool(args.reuse_testid)
    if args.reuse_testid:
        client.attach_testid(args.reuse_testid)
    else:
        testid = client.select_test_case(args.case)
        print(f"Selected testcase {args.case} with testid {testid}")
        try:
            client.wait_running(
                timeout_s=int(args.startup_timeout_s),
                poll_interval_s=int(args.startup_poll_interval_s),
            )
        except TimeoutError:
            if not args.recover_from_queued:
                raise
            print("Startup timeout in Queued state. Attempting one-time recovery ...")
            try:
                stopped = client.stop()
                print(f"stop({testid}) -> {stopped}")
            except Exception as exc:
                print(f"Warning: stop failed: {exc}")
            testid = client.select_test_case(args.case)
            print(f"Retry selected testcase {args.case} with testid {testid}")
            client.wait_running(
                timeout_s=int(args.startup_timeout_s),
                poll_interval_s=int(args.startup_poll_interval_s),
            )

    index: list[dict[str, Any]] = []
    existing_index_path = output_dir / "index.json"
    if args.resume and existing_index_path.exists():
        try:
            with existing_index_path.open("r", encoding="utf-8") as f:
                existing_index = json.load(f)
            if isinstance(existing_index, list):
                index.extend(existing_index)
        except Exception:
            pass
    for i, episode in enumerate(episodes, start=1):
        ep_id = episode["id"]
        print(f"[{i}/{len(episodes)}] Running episode {ep_id} ({episode['split']}, {episode['weather_class']})")
        index = [item for item in index if item.get("dataset_id") != ep_id]
        try:
            data = run_episode(client, args.case, case_mappings, episode, defaults)
            out_path = json_dir / f"{ep_id}.json"
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            index.append(
                {
                    "dataset_id": ep_id,
                    "split": episode["split"],
                    "weather_class": episode["weather_class"],
                    "path": str(out_path.relative_to(root)).replace("\\", "/"),
                    "n_records": len(data["records"]),
                }
            )
        except Exception as exc:
            index.append(
                {
                    "dataset_id": ep_id,
                    "split": episode["split"],
                    "weather_class": episode["weather_class"],
                    "error": str(exc),
                }
            )
            print(f"Episode {ep_id} failed: {exc}")

    index_path = output_dir / "index.json"
    ensure_dir(output_dir)
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    if owns_test_session:
        try:
            stopped = client.stop()
            print(f"Stopped test session: {stopped}")
        except Exception as exc:
            print(f"Warning: failed to stop test session: {exc}")

    print(f"Done. Wrote index: {index_path}")


if __name__ == "__main__":
    main()
