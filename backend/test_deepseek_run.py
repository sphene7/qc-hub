"""Quick test DeepSeek API response and JSON parsing."""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app.parser import parse_workbook
from app.semantics import build_workbook_spec
from app.deepseek import analyze_excel_structure
from pathlib import Path

# Find any xlsx in project
root = Path(__file__).resolve().parents[1]
xlsx_files = list(root.rglob("*.xlsx"))
if not xlsx_files:
    print("No xlsx found, testing parse only on empty spec")
    sys.exit(1)

path = xlsx_files[0]
print(f"Testing with: {path}")

parsed = parse_workbook(path, path.name)
spec = build_workbook_spec(parsed)
print(f"Sheets: {len(spec.get('sheets', []))}")

design = analyze_excel_structure(parsed, spec)
print("\n=== RESULT ===")
print(f"type: {design.get('business_understanding', {}).get('type')}")
print(f"purpose: {design.get('business_understanding', {}).get('purpose')}")
print(f"kpis: {len(design.get('kpis', []))}")
print(f"charts: {len(design.get('charts', []))}")

if design.get('business_understanding', {}).get('type') == '解析失败':
    doc = design.get('design_document', '')[:2000]
    print("\n=== design_document preview ===")
    print(doc)
