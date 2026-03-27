#!/usr/bin/env python3
"""
Extract the most likely "title" from a PDF using OCR.

Implementation notes:
- Uses Poppler (`pdftoppm`) to render the first page to an image.
- Uses Tesseract to run OCR and outputs word-level TSV with confidences.
- Groups words into lines, filters likely header/title lines near the top,
  then assembles a 1-2 line title from the best candidates.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


_TITLE_BLACKLIST_SUBSTRINGS = [
    "abstract",
    "keywords",
    "index terms",
    "introduction",
    "references",
]


@dataclass(frozen=True)
class Word:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float


@dataclass
class Line:
    key: Tuple[int, int, int]  # (block_num, par_num, line_num)
    words: List[Word]

    @property
    def text(self) -> str:
        # Words are already in reading order most of the time; we still sort by x.
        ws = sorted(self.words, key=lambda w: (w.left, w.top))
        joined = " ".join(w.text for w in ws if w.text)
        return _normalize_ws(joined)

    @property
    def y_min(self) -> int:
        return min(w.top for w in self.words) if self.words else 10**9

    @property
    def height_mean(self) -> float:
        hs = [w.height for w in self.words if w.height > 0]
        return float(statistics.mean(hs)) if hs else 1.0

    @property
    def conf_mean(self) -> float:
        cs = [w.conf for w in self.words if w.conf >= 0]
        return float(statistics.mean(cs)) if cs else -1.0

    @property
    def letters_count(self) -> int:
        return len(re.findall(r"[A-Za-z]", self.text))


def _normalize_ws(s: str) -> str:
    s = s.replace("\u00A0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    # Remove spaces before common punctuation.
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    return s


def _is_likely_title_line(text: str) -> bool:
    if not text or len(text) < 5:
        return False

    t = text.strip().lower()
    if any(sub in t for sub in _TITLE_BLACKLIST_SUBSTRINGS):
        return False

    # Avoid "mostly numbers" lines.
    letters = len(re.findall(r"[A-Za-z]", text))
    digits = len(re.findall(r"\d", text))
    if letters < 2 and digits > 5:
        return False

    # Title lines typically have at least a couple of alphabetic chars.
    if letters < 3:
        return False

    # Avoid lines that look like broken glyph soup.
    if len(text) > 250:
        return False

    return True


def _run(
    cmd: List[str],
    *,
    check: bool = True,
    timeout_sec: Optional[float] = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=True,
        timeout=timeout_sec,
    )


def _render_pdf_page_to_png(
    pdf_path: str,
    page: int,
    dpi: int,
    out_dir: str,
    *,
    timeout_sec: Optional[float] = None,
) -> str:
    # Use -singlefile to avoid directory scans and variable suffixes.
    prefix = os.path.join(out_dir, f"page{page}")
    cmd = [
        "pdftoppm",
        "-f",
        str(page),
        "-l",
        str(page),
        "-singlefile",
        "-png",
        "-r",
        str(dpi),
        pdf_path,
        prefix,
    ]
    _run(cmd, timeout_sec=timeout_sec)

    img_path = f"{prefix}.png"
    if not os.path.exists(img_path):
        raise RuntimeError(f"No PNG rendered for page {page} (dpi={dpi}).")
    return img_path


def _tesseract_tsv(image_path: str, psm: int, *, timeout_sec: Optional[float] = None) -> str:
    cmd = [
        "tesseract",
        image_path,
        "stdout",
        "--oem",
        "1",
        "--psm",
        str(psm),
        "tsv",
    ]
    res = _run(cmd, timeout_sec=timeout_sec)
    return res.stdout


def _parse_tesseract_tsv(tsv: str) -> List[Line]:
    """
    Parse Tesseract TSV into line objects.

    TSV columns (tab-separated):
    level page_num block_num par_num line_num word_num left top width height conf text
    """
    lines_map: Dict[Tuple[int, int, int], List[Word]] = defaultdict(list)

    it = iter(tsv.splitlines())
    header = next(it, None)
    if not header:
        return []

    for row in it:
        if not row.strip():
            continue
        fields = row.split("\t")
        if len(fields) < 12:
            continue
        # Some fields may be empty; treat them carefully.
        try:
            level = int(fields[0])
            if level != 5:
                # level 5 is word-level rows
                continue
            block_num = int(fields[2])
            par_num = int(fields[3])
            line_num = int(fields[4])
            left = int(float(fields[6]))
            top = int(float(fields[7]))
            width = int(float(fields[8]))
            height = int(float(fields[9]))
            conf = float(fields[10]) if fields[10] else -1.0
            text = fields[11].strip()
        except Exception:
            continue

        if not text:
            continue

        key = (block_num, par_num, line_num)
        lines_map[key].append(Word(text=text, left=left, top=top, width=width, height=height, conf=conf))

    out: List[Line] = []
    for key, words in lines_map.items():
        if not words:
            continue
        out.append(Line(key=key, words=words))
    return out


def extract_title_from_pdf(
    pdf_path: str,
    *,
    page: int = 1,
    dpi: int = 300,
    psm: int = 6,
    max_title_lines: int = 2,
    search_top_n_lines: int = 8,
    timeout_sec: Optional[float] = None,
    debug: bool = False,
) -> str:
    pdf_path = os.path.abspath(pdf_path)
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)

    with tempfile.TemporaryDirectory(prefix="title-extraction-ocr-") as tmp:
        img_path = _render_pdf_page_to_png(
            pdf_path,
            page=page,
            dpi=dpi,
            out_dir=tmp,
            timeout_sec=timeout_sec,
        )
        tsv = _tesseract_tsv(img_path, psm=psm, timeout_sec=timeout_sec)
        tlines = _parse_tesseract_tsv(tsv)

    # Sort by vertical position (top-most first).
    tlines_sorted = sorted(tlines, key=lambda ln: ln.y_min)

    # Only consider likely top-of-page lines.
    top_letters_lines = [ln for ln in tlines_sorted if ln.letters_count >= 3 and _is_likely_title_line(ln.text)]
    if debug:
        print(f"[debug] OCR line candidates (top {min(10, len(top_letters_lines))} shown):", file=sys.stderr)
        for ln in top_letters_lines[:10]:
            print(
                f"[debug] y={ln.y_min} conf={ln.conf_mean:.1f} h={ln.height_mean:.1f} text={ln.text!r}",
                file=sys.stderr,
            )

    if not top_letters_lines:
        # Fallback: just concatenate the first few non-empty lines from tesseract plain OCR.
        # (Still OCR, but less structured.)
        with tempfile.TemporaryDirectory(prefix="title-extraction-ocr-fallback-") as tmp:
            img_path = _render_pdf_page_to_png(
                pdf_path,
                page=page,
                dpi=dpi,
                out_dir=tmp,
                timeout_sec=timeout_sec,
            )
            res = _run(
                ["tesseract", img_path, "stdout", "--oem", "1", "--psm", str(psm)],
                timeout_sec=timeout_sec,
            )
            plain_lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
        # pick first 2 lines that look title-ish
        chosen = []
        for ln in plain_lines:
            if _is_likely_title_line(ln):
                chosen.append(ln)
            if len(chosen) >= max_title_lines:
                break
        if not chosen and plain_lines:
            chosen = plain_lines[:max_title_lines]
        return " ".join(chosen).strip()

    # Pick the best single line among the *top-of-page* candidates only.
    # If we don't restrict by vertical position, we may accidentally pick an
    # abstract sentence with high confidence.
    first_stage = top_letters_lines[: max(3, min(search_top_n_lines, len(top_letters_lines)))]
    best = max(
        first_stage,
        key=lambda ln: (
            ln.conf_mean,
            ln.letters_count,
            len(ln.text),
        ),
    )

    # Assemble multi-line title: include next lines directly below if they look consistent.
    title_parts = [best.text]
    if max_title_lines > 1:
        # Consider lines after best in y order.
        ordered = [
            ln
            for ln in tlines_sorted
            if _is_likely_title_line(ln.text) and ln.letters_count >= 3
        ]
        # Find index of best
        idx = None
        for i, ln in enumerate(ordered):
            if ln.key == best.key:
                idx = i
                break
        if idx is not None:
            line_h = best.height_mean
            best_conf = best.conf_mean
            for ln in ordered[idx + 1 :]:
                if len(title_parts) >= max_title_lines:
                    break
                delta_y = ln.y_min - best.y_min
                # Keep close lines together; allow a small margin.
                if delta_y < 0 or delta_y > (line_h * 1.8):
                    break
                if ln.conf_mean < max(0.0, best_conf - 15):
                    continue
                if not _is_likely_title_line(ln.text):
                    continue
                title_parts.append(ln.text)

    # Final cleanup.
    title = _normalize_ws(" ".join(title_parts))
    return title


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", help="Path to the input PDF")
    ap.add_argument("--page", type=int, default=1, help="1-based page number to scan")
    ap.add_argument("--dpi", type=int, default=300, help="Render DPI for OCR")
    ap.add_argument("--psm", type=int, default=6, help="Tesseract PSM mode")
    ap.add_argument("--max-lines", type=int, default=2, help="Max title lines to join")
    ap.add_argument("--search-top-n", type=int, default=8, help="How many top OCR lines to search for the title")
    ap.add_argument("--timeout-sec", type=float, default=None, help="Timeout for each OCR subprocess call")
    ap.add_argument("--debug", action="store_true", help="Print candidate lines to stderr")
    args = ap.parse_args()

    title = extract_title_from_pdf(
        args.pdf,
        page=args.page,
        dpi=args.dpi,
        psm=args.psm,
        max_title_lines=args.max_lines,
        search_top_n_lines=args.search_top_n,
        timeout_sec=args.timeout_sec,
        debug=args.debug,
    )
    print(title)


if __name__ == "__main__":
    main()

