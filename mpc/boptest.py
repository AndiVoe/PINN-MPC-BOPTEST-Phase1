"""Minimal BOPTEST HTTP client for WP4 MPC experiments."""

from __future__ import annotations

import time
from typing import Any

import requests


class BoptestConnectionError(RuntimeError):
    pass


class BoptestClient:
    """Thin wrapper over the BOPTEST REST API."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.testid: str | None = None
        self._assert_reachable()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _assert_reachable(self) -> None:
        try:
            resp = requests.get(f"{self.base_url}/version", timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise BoptestConnectionError(
                f"Could not reach BOPTEST at {self.base_url}."
            ) from exc

    def _testid(self) -> str:
        if not self.testid:
            raise RuntimeError("No testcase selected.")
        return self.testid

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def select_test_case(self, case_name: str) -> str:
        for endpoint in (
            f"{self.base_url}/testcases/{case_name}/select-true",
            f"{self.base_url}/testcases/{case_name}/select",
        ):
            resp = requests.post(endpoint, timeout=900)
            if resp.ok:
                testid = resp.json().get("testid")
                if testid:
                    self.testid = testid
                    return testid
        raise RuntimeError(f"Failed to select testcase: {case_name}")

    def attach_testid(self, testid: str) -> None:
        resp = requests.get(f"{self.base_url}/status/{testid}", timeout=30)
        resp.raise_for_status()
        try:
            data = resp.json()
            status = data.get("payload") if isinstance(data, dict) else str(data)
        except Exception:
            status = resp.text.strip('"')
        if status != "Running":
            raise RuntimeError(f"Testid {testid} is not Running (got: {status}).")
        self.testid = testid

    def wait_running(self, timeout_s: int = 1200, poll_s: int = 5) -> None:
        tid = self._testid()
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                resp = requests.get(f"{self.base_url}/status/{tid}", timeout=60)
                resp.raise_for_status()
                try:
                    data = resp.json()
                    status = data.get("payload") if isinstance(data, dict) else str(data)
                except Exception:
                    status = resp.text.strip('"')
            except requests.RequestException as exc:
                # BOPTEST web can restart while worker keeps running; keep polling.
                print(f"  [boptest] status check transient error: {exc}", flush=True)
                time.sleep(max(1, poll_s))
                continue
            print(f"  [boptest] status={status}", flush=True)
            if status == "Running":
                return
            time.sleep(poll_s)
        raise TimeoutError("Timed out waiting for Running state.")

    def set_scenario(self, scenario: dict[str, Any]) -> None:
        if not scenario:
            return
        resp = requests.put(
            f"{self.base_url}/scenario/{self._testid()}", json=scenario, timeout=120
        )
        if not resp.ok:
            raise RuntimeError(
                f"Failed to set scenario {scenario}: {resp.status_code} {resp.text[:300]}"
            )

    def initialize(self, start_time_s: int, warmup_period_s: int) -> dict[str, Any]:
        resp = requests.put(
            f"{self.base_url}/initialize/{self._testid()}",
            json={"start_time": start_time_s, "warmup_period": warmup_period_s},
            timeout=1200,
        )
        resp.raise_for_status()
        return resp.json().get("payload", {})

    def set_step(self, step_s: int) -> None:
        resp = requests.put(
            f"{self.base_url}/step/{self._testid()}",
            json={"step": step_s},
            timeout=60,
        )
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # Per-step API
    # ------------------------------------------------------------------

    def get_inputs(self) -> dict[str, Any]:
        resp = requests.get(f"{self.base_url}/inputs/{self._testid()}", timeout=60)
        resp.raise_for_status()
        return resp.json().get("payload", {})

    def get_forecast(
        self,
        point_names: list[str],
        horizon_s: int,
        interval_s: int,
    ) -> dict[str, list[float]]:
        resp = requests.put(
            f"{self.base_url}/forecast/{self._testid()}",
            json={"point_names": point_names, "horizon": horizon_s, "interval": interval_s},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("payload", {})

    def advance(self, u_dict: dict[str, float]) -> dict[str, Any]:
        resp = requests.post(
            f"{self.base_url}/advance/{self._testid()}",
            json=u_dict,
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json().get("payload", {})

    def kpi(self) -> dict[str, Any]:
        """Fetch KPIs from BOPTEST (available at end of episode)."""
        resp = requests.get(f"{self.base_url}/kpi/{self._testid()}", timeout=60)
        resp.raise_for_status()
        return resp.json().get("payload", {})

    def stop(self) -> bool:
        """Stop current test to release worker resources."""
        tid = self._testid()
        resp = requests.put(f"{self.base_url}/stop/{tid}", timeout=60)
        return bool(resp.ok)
