import json
import os
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

def export_closed_loop_to_csv(json_path, csv_path):
    json_path = Path(json_path)
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not json_path.exists():
        print(f"File {json_path} does not exist.")
        return
        
    print(f"Exporting step records from {json_path} to {csv_path}...")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if "step_records" in data:
        step_records = data["step_records"]
    else:
        print(f"Skipping {json_path.name}: 'step_records' key not found.")
        return
        
    df = pd.DataFrame(step_records)
    df.to_csv(csv_path, index=False)
    print(f"  Exported -> {csv_path.name} ({len(df)} steps)")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export closed-loop step records to CSV.")
    parser.add_argument("--episode", default="te_long_01", help="Episode stem name.")
    args = parser.parse_args()

    export_closed_loop_to_csv(
        BASE / f"results/mpc_phase1/rc/{args.episode}.json",
        BASE / f"results/mpc_phase1/rc/{args.episode}_steps.csv"
    )
    export_closed_loop_to_csv(
        BASE / f"results/mpc_phase1/pinn/{args.episode}.json",
        BASE / f"results/mpc_phase1/pinn/{args.episode}_steps.csv"
    )
    print("Closed-loop step records export complete!")
