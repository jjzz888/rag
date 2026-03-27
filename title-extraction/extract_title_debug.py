#!/usr/bin/env python3
"""
Debug helper for title extraction.

Prints the OCR line candidates near the top of the page so you can verify
why a specific title was chosen.
"""

from __future__ import annotations

import argparse
import sys

from extract_title import (
    _is_likely_title_line,
    _parse_tesseract_tsv,
    _render_pdf_page_to_png,
    _tesseract_tsv,
    Line,
)

import os
import tempfile
import subprocess
import math


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", help="Path to the input PDF")
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--psm", type=int, default=6)
    ap.add_argument("--search-top-n", type=int, default=8, help="How many top OCR lines to consider")
    args = ap.parse_args()

    pdf_path = os.path.abspath(args.pdf)
    with tempfile.TemporaryDirectory(prefix="title-extraction-debug-") as tmp:
        img_path = _render_pdf_page_to_png(pdf_path, page=args.page, dpi=args.dpi, out_dir=tmp)
        tsv = _tesseract_tsv(img_path, psm=args.psm)
        lines = _parse_tesseract_tsv(tsv)

    lines_sorted = sorted(lines, key=lambda ln: ln.y_min)
    candidates = [ln for ln in lines_sorted if _is_likely_title_line(ln.text)]

    candidates = candidates[: max(1, min(args.search_top_n, len(candidates)))]
    for ln in candidates:
        print(f"y={ln.y_min:>5} conf={ln.conf_mean:>6.1f} h={ln.height_mean:>5.1f} | {ln.text}")

    if candidates:
        print("\nChosen (first best by conf/length heuristic):")
        best = max(candidates, key=lambda ln: (ln.conf_mean, ln.letters_count, len(ln.text)))
        print(best.text)


if __name__ == "__main__":
    main()

