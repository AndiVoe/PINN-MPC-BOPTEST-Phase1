import json
import os
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

def export_json_folder_to_csv(json_dir, csv_dir):
    json_dir = Path(json_dir)
    csv_dir = Path(csv_dir)
    csv_dir.mkdir(parents=True, exist_ok=True)
    
    if not json_dir.exists():
        print(f"Directory {json_dir} does not exist.")
        return
        
    print(f"Exporting JSON files from {json_dir} to {csv_dir}...")
    for file in json_dir.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if "records" in data:
            records = data["records"]
        else:
            print(f"Skipping {file.name}: 'records' key not found.")
            continue
            
        df = pd.DataFrame(records)
        csv_file = csv_dir / (file.stem + ".csv")
        df.to_csv(csv_file, index=False)
        print(f"  Exported {file.name} -> {csv_file.name} ({len(df)} rows)")

if __name__ == "__main__":
    export_json_folder_to_csv(
        BASE / "datasets/phase1_singlezone/json",
        BASE / "datasets/phase1_singlezone/csv"
    )
    export_json_folder_to_csv(
        BASE / "datasets/phase1_excited/json",
        BASE / "datasets/phase1_excited/csv"
    )
    print("Export complete!")
