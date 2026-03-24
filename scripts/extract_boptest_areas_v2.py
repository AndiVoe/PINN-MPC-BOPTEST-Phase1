#!/usr/bin/env python3
"""Extract floor areas from BOPTEST PDF specifications using simpler method."""

import re
from pathlib import Path

pdf_dir = Path(r"C:\Users\AVoelser\OneDrive - Scientific Network South Tyrol\3_PhD\BopTest")

try:
    from PyPDF2 import PdfReader
    
    pdf_files = {
        "bestest_hydronic": "BOPTEST-Bestest Hydronic.pdf",
        "bestest_hydronic_heat_pump": "BOPTEST-Bestest Hydronic HP.pdf",
        "singlezone_commercial_hydronic": "BOPTEST-Bestest SZ Com Hydronic.pdf",
        "twozone_apartment_hydronic": "BOPTEST-Bestest TZ App Hydronic.pdf",
    }
    
    print("=== FLOOR AREAS FROM BOPTEST PDF FILES ===\n")
    
    for case_name, pdf_name in pdf_files.items():
        pdf_path = pdf_dir / pdf_name
        
        if not pdf_path.exists():
            print(f"{case_name:40s} | PDF NOT FOUND: {pdf_path}")
            continue
        
        try:
            reader = PdfReader(str(pdf_path))
            text = ""
            
            # Extract text from first 5 pages
            for page_num in range(min(5, len(reader.pages))):
                page = reader.pages[page_num]
                text += page.extract_text() or ""
            
            # Look for floor area patterns
            patterns = [
                r"floor\s+area[:\s]*([0-9,\.]+)\s*m[²2]",
                r"conditioned\s+floor\s+area[:\s]*([0-9,\.]+)\s*m[²2]",
                r"gross\s+floor\s+area[:\s]*([0-9,\.]+)\s*m[²2]",
                r"heated\s+floor\s+area[:\s]*([0-9,\.]+)\s*m[²2]",
                r"floor\s+area:?\s*([0-9,\.]+)\s*m[²2]",
                r"area:\s*([0-9,\.]+)\s*m[²2]",
                r"(\d+)\s*m[²2]\s+floor",
            ]
            
            area_m2 = None
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    area_str = matches[0].replace(",", "")
                    try:
                        area_m2 = float(area_str)
                        break
                    except ValueError:
                        continue
            
            if area_m2:
                print(f"{case_name:40s} | {area_m2:10.1f} m²  ✓ FOUND")
            else:
                print(f"{case_name:40s} | NOT FOUND in text extraction")
                # Show snippet with "area" or "floor"
                for i, match in enumerate(re.finditer(r"(?i)(floor|area|size|dimension)[^\n]*\n[^\n]*\n", text)):
                    if i < 3:
                        snippet = match.group(0).replace("\n", " ")[:100]
                        print(f"  Snippet {i+1}: ...{snippet}...")
                    
        except Exception as e:
            print(f"{case_name:40s} | ERROR: {str(e)[:80]}")

except ImportError:
    print("PyPDF2 not installed. Installing...")
    import subprocess
    subprocess.run([".venv/Scripts/pip", "install", "PyPDF2"], cwd=".")
    print("Please run the script again.")
