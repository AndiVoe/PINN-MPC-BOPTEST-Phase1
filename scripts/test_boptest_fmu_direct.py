#!/usr/bin/env python3
"""
Minimal BOPTEST FMU tester - no MPC, no torch, just raw API calls.
Tests whether a given FMU can complete advance() calls without hanging.
"""

import sys
import time
from pathlib import Path

# Add parent to path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpc.boptest import BoptestClient


def test_fmu_case(
    case_name: str,
    step_s: int = 600,
    n_steps: int = 6,
    advance_timeout_s: int = 900,
    base_url: str = "http://localhost:8000"
) -> bool:
    """
    Test a single FMU case by advancing N steps.
    Returns True if successful, False on any advance timeout/error.
    """
    print(f"\n{'='*70}")
    print(f"Testing: {case_name}")
    print(f"  Step size: {step_s}s")
    print(f"  N steps: {n_steps} (total {step_s * n_steps}s = {step_s * n_steps / 3600:.1f} hours)")
    print(f"  Advance timeout: {advance_timeout_s}s")
    print(f"  URL: {base_url}")
    print(f"{'='*70}")
    
    try:
        # Initialize client
        client = BoptestClient(base_url=base_url, advance_timeout_s=advance_timeout_s)
        
        # Select test case
        print(f"\n[1/4] Selecting test case '{case_name}'...")
        client.select_test_case(case_name)
        print(f"  ✓ Selected")
        
        # Initialize simulation
        print(f"\n[2/4] Initializing simulation...")
        init_result = client.initialize(
            start_time_s=0,
            warmup_period_s=0
        )
        print(f"  ✓ Initialized")
        print(f"    Simulation start: {init_result.get('time_s', '?')}s")
        
        # Set control step
        print(f"\n[3/4] Setting control interval to {step_s}s...")
        client.set_step(step_s)
        print(f"  ✓ Control interval set")
        
        # Advance N steps
        print(f"\n[4/4] Advancing {n_steps} steps...")
        for i in range(n_steps):
            step_start = time.time()
            u_dict = {}  # No control inputs - passive simulation
            result = client.advance(u_dict)
            step_elapsed = time.time() - step_start
            
            current_time_s = result.get('time_s', 0)
            current_hour = current_time_s / 3600
            print(f"  Step {i+1}/{n_steps}: time={current_hour:.2f}h, elapsed={step_elapsed:.1f}s")
        
        # Success
        print(f"\n✓ SUCCESS: All {n_steps} steps completed!")
        client.stop()
        return True
        
    except Exception as e:
        print(f"\n✗ FAILURE: {type(e).__name__}: {e}")
        try:
            client.stop()
        except:
            pass
        return False


if __name__ == "__main__":
    # Test active case FMU only
    results = {}

    results["singlezone_commercial_hydronic"] = test_fmu_case(
        "singlezone_commercial_hydronic",
        step_s=600,
        n_steps=6,  # 6 steps * 600s = 1 hour (quick test)
        advance_timeout_s=900
    )
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for case, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {case}")
