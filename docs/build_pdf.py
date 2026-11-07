"""Build docs/coach-overview.pdf from docs/overview.md: 2 A4 pages, black and grey only.

Run (the PDF libraries are fetched on the fly, not added to the project):
    uv run --with markdown-pdf python docs/build_pdf.py
Each part between `<!-- pagebreak -->` markers becomes one page. The script fails if the
result is not exactly 2 pages or if any pixel has colour.
"""

import sys
from pathlib import Path

import pymupdf  # type: ignore[import-not-found]
from markdown_pdf import MarkdownPdf, Section  # type: ignore[import-not-found]

DOCS = Path(__file__).parent
SOURCE = DOCS / "overview.md"
TARGET = DOCS / "coach-overview.pdf"
EXPECTED_PAGES = 2

CSS = """
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #111;
       line-height: 1.38; }
h1 { font-size: 17pt; margin: 0 0 2pt 0; color: #000; }
h2 { font-size: 13pt; margin: 8pt 0 4pt 0; color: #000; border-bottom: 0.6pt solid #888; }
p { margin: 0 0 5pt 0; }
em { color: #444; }
ul { margin: 0 0 5pt 0; }
li { margin: 0 0 1.5pt 0; }
pre { font-family: Courier, monospace; font-size: 7.8pt; line-height: 1.2; background: #f2f2f2;
      padding: 5pt; margin: 2pt 0 6pt 0; color: #111; }
code { font-family: Courier, monospace; font-size: 8.8pt; color: #222; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; margin-bottom: 8pt; }
th { text-align: left; background: #e6e6e6; border: 0.5pt solid #999; padding: 3pt; }
td { border: 0.5pt solid #bbb; padding: 3pt; vertical-align: top; }
"""


def max_channel_spread(pdf: Path) -> int:
    """Largest difference between R, G and B in any rendered pixel (0 = pure greyscale)."""
    worst = 0
    with pymupdf.open(pdf) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=100, colorspace=pymupdf.csRGB, alpha=False)
            data = pix.samples
            for i in range(0, len(data), 3):
                r, g, b = data[i], data[i + 1], data[i + 2]
                worst = max(worst, max(r, g, b) - min(r, g, b))
    return worst


def main() -> int:
    parts = SOURCE.read_text(encoding="utf-8").split("<!-- pagebreak -->")
    pdf = MarkdownPdf(toc_level=0, optimize=True)
    pdf.meta["title"] = "coach: a minimal agent that reviews a runner's week"
    pdf.meta["author"] = "Miguel"
    for part in parts:
        pdf.add_section(Section(part.strip(), paper_size="A4", borders=(40, 36, -40, -36)), CSS)
    pdf.save(TARGET)

    with pymupdf.open(TARGET) as doc:
        pages = doc.page_count
    spread = max_channel_spread(TARGET)
    print(f"{TARGET.name}: {pages} pages, max RGB channel spread {spread}")
    if pages != EXPECTED_PAGES:
        print(f"FAIL: expected {EXPECTED_PAGES} pages; shorten the text.", file=sys.stderr)
        return 1
    if spread > 0:
        print("FAIL: the PDF contains colour; use only black and greys.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
