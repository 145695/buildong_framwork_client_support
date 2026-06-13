import pdfplumber
from pathlib import Path
import sys

# Set UTF-8 encoding for stdout on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

policies_dir = Path("policies")  # adjust path if needed
output_dir = Path("policies_text")
output_dir.mkdir(exist_ok=True)

for pdf_path in sorted(policies_dir.glob("*.pdf")):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text.strip())
            
            full_text = "\n\n".join(pages)
            
            if len(full_text.strip()) > 50:
                output_path = output_dir / (pdf_path.stem + ".txt")
                output_path.write_text(full_text, encoding="utf-8")
                print(f"[OK] {pdf_path.name} -> {output_path.name} ({len(full_text)} chars)")
            else:
                print(f"[SKIP] {pdf_path.name} -> too short, skipped")
    except Exception as e:
        print(f"[ERROR] {pdf_path.name} -> error: {e}")

print(f"\nDone. Text files saved to: {output_dir}")
