#!/usr/bin/env python3
"""Extract floor areas from BOPTEST PDF specifications."""

import re
from pathlib import Path

pdf_dir = Path(r"C:\Users\AVoelser\OneDrive - Scientific Network South Tyrol\3_PhD\BopTest")

# Try to use PyPDF2 or pdfplumber if available
try:
    import pdfplumber
    
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
            print(f"{case_name:40s} | PDF NOT FOUND")
            continue
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = "".join(page.extract_text() or "" for page in pdf.pages)
                
                # Look for floor area patterns (m², m2, m^2, etc.)
                patterns = [
                    r"floor\s+area[:\s]*([0-9,\.]+)\s*m[²2]",
                    r"conditioned\s+floor\s+area[:\s]*([0-9,\.]+)\s*m[²2]",
                    r"gross\s+floor\s+area[:\s]*([0-9,\.]+)\s*m[²2]",
                    r"heated\s+floor\s+area[:\s]*([0-9,\.]+)\s*m[²2]",
                    r"floor\s+area:?\s*([0-9,\.]+)\s*m[²2]",
                    r"area:\s*([0-9,\.]+)\s*m[²2]",
                ]
                
                area_m2 = None
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    if matches:
                        # Clean and convert to float
                        area_str = matches[0].replace(",", "")
                        try:
                            area_m2 = float(area_str)
                            break
                        except ValueError:
                            continue
                
                if area_m2:
                    print(f"{case_name:40s} | {area_m2:10.1f} m²")
                else:
                    # Show first 500 chars to help manual extraction
                    print(f"{case_name:40s} | AREA NOT FOUND")
                    print(f"  First 500 chars: {text[:500]}")
                    
        except Exception as e:
            print(f"{case_name:40s} | ERROR: {e}")

except ImportError:
    print("pdfplumber not installed. Please install with: pip install pdfplumber")
    print("\nAlternatively, check PDFs manually for floor area information...")
