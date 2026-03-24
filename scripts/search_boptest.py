#!/usr/bin/env python3
"""Search BOPTEST PDFs for floor area information more thoroughly."""

from pathlib import Path

pdf_dir = Path(r"C:\Users\AVoelser\OneDrive - Scientific Network South Tyrol\3_PhD\BopTest")

try:
    from PyPDF2 import PdfReader
    import re
    
    pdf_files = {
        "bestest_hydronic": "BOPTEST-Bestest Hydronic.pdf",
        "bestest_hydronic_heat_pump": "BOPTEST-Bestest Hydronic HP.pdf",
        "singlezone_commercial_hydronic": "BOPTEST-Bestest SZ Com Hydronic.pdf",
        "twozone_apartment_hydronic": "BOPTEST-Bestest TZ App Hydronic.pdf",
    }
    
    print("=== SEARCHING BOPTEST PDFS FOR FLOOR AREA ===\n")
    
    for case_name, pdf_name in pdf_files.items():
        pdf_path = pdf_dir / pdf_name
        
        if not pdf_path.exists():
            continue
        
        try:
            reader = PdfReader(str(pdf_path))
            text = ""
            
            # Extract all text
            for page in reader.pages:
                text += page.extract_text() or ""
            
            print(f"{case_name:40s}")
            print(f"  Total chars extracted: {len(text)}")
            
            # Search for numbers with m2/m² (case-insensitive)
            matches = re.findall(r'(\d+[.,]\d+|\d+)\s*m[²2]', text, re.IGNORECASE)
            if matches:
                print(f"  Found {len(matches)} m² values: {matches[:5]}")
            
            # Search for "area" mentions
            area_lines = [line for line in text.split('\n') if 'area' in line.lower()]
            if area_lines:
                print(f"  Found {len(area_lines)} lines with 'area':")
                for line in area_lines[:3]:
                    clean_line = ' '.join(line.split())[:100]
                    print(f"    - {clean_line}")
            
            # Search for key properties
            for keyword in ['floor', 'dimension', 'building', 'volume']:
                matches = [line for line in text.split('\n') if keyword.lower() in line.lower()]
                if matches and keyword != 'area':
                    print(f"  Lines with '{keyword}': {len(matches)}")
                    for line in matches[:1]:
                        clean = ' '.join(line.split())[:80]
                        if clean:
                            print(f"    - {clean}")
            
            print()
                    
        except Exception as e:
            print(f"  ERROR: {e}\n")

except ImportError:
    print("PyPDF2 required")
