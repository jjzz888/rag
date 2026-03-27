#!/usr/bin/env python3
"""
Scalable batch title extraction for large PDF folders.

This runner calls extract_title_from_pdf() directly in-process (instead of
spawning `python extract_title.py` per file), and parallelizes work with a
bounded worker pool.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from extract_title import extract_title_from_pdf


def _list_pdfs(folder: Path, recursive: bool) -> List[Path]:
    if recursive:
        return sorted(p for p in folder.rglob("*.pdf") if p.is_file())
    return sorted(p for p in folder.glob("*.pdf") if p.is_file())


def _process_one(
    pdf_path: Path,
    *,
    page: int,
    dpi: int,
    fallback_dpi: Optional[int],
    psm: int,
    max_lines: int,
    search_top_n: int,
    timeout_sec: Optional[float],
) -> Dict[str, str]:
    attempts = [dpi]
    if fallback_dpi and fallback_dpi != dpi:
        attempts.append(fallback_dpi)

    last_error = None
    for attempt_dpi in attempts:
        try:
            title = extract_title_from_pdf(
                str(pdf_path),
                page=page,
                dpi=attempt_dpi,
                psm=psm,
                max_title_lines=max_lines,
                search_top_n_lines=search_top_n,
                timeout_sec=timeout_sec,
                debug=False,
            )
            return {
                "file": str(pdf_path),
                "status": "ok",
                "dpi": str(attempt_dpi),
                "title": title.strip(),
            }
        except TimeoutError as exc:
            last_error = f"timeout: {exc}"
        except Exception as exc:  # noqa: BLE001
            last_error = f"error: {exc}"

    return {
        "file": str(pdf_path),
        "status": "timeout" if last_error and last_error.startswith("timeout") else "error",
        "dpi": str(attempts[-1]),
        "title": "",
        "message": last_error or "unknown error",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="Folder containing PDFs")
    ap.add_argument("--recursive", action="store_true", help="Scan subfolders recursively")
    ap.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 4), help="Concurrent worker count")
    ap.add_argument("--max-files", type=int, default=None, help="Limit number of PDFs processed")
    ap.add_argument("--page", type=int, default=1, help="1-based page number to scan")
    ap.add_argument("--dpi", type=int, default=300, help="Primary OCR render DPI")
    ap.add_argument("--fallback-dpi", type=int, default=220, help="Fallback DPI if primary attempt fails")
    ap.add_argument("--psm", type=int, default=6, help="Tesseract PSM mode")
    ap.add_argument("--max-lines", type=int, default=2, help="Max title lines to join")
    ap.add_argument("--search-top-n", type=int, default=8, help="How many top OCR lines to search for title")
    ap.add_argument("--timeout-sec", type=float, default=45.0, help="Timeout per subprocess call")
    args = ap.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        raise SystemExit(f"Invalid folder: {folder}")

    pdfs = _list_pdfs(folder, recursive=args.recursive)
    if args.max_files is not None:
        pdfs = pdfs[: max(0, args.max_files)]

    if not pdfs:
        print("No PDFs found.")
        return

    total = len(pdfs)
    print(f"Found {total} PDFs in {folder}")
    print(f"Running with workers={args.workers}, dpi={args.dpi}, fallback_dpi={args.fallback_dpi}, timeout_sec={args.timeout_sec}")

    done = 0
    ok = 0
    failed = 0

    futures: Dict[concurrent.futures.Future[Dict[str, str]], Path] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        for pdf in pdfs:
            fut = executor.submit(
                _process_one,
                pdf,
                page=args.page,
                dpi=args.dpi,
                fallback_dpi=args.fallback_dpi,
                psm=args.psm,
                max_lines=args.max_lines,
                search_top_n=args.search_top_n,
                timeout_sec=args.timeout_sec,
            )
            futures[fut] = pdf

        for fut in concurrent.futures.as_completed(futures):
            done += 1
            result = fut.result()
            status = result["status"]
            file_name = Path(result["file"]).name
            if status == "ok":
                ok += 1
                title = result.get("title", "").replace("\t", " ").strip()
                print(f"[{done}/{total}] ok\t{file_name}\t{title}")
            else:
                failed += 1
                msg = result.get("message", "").replace("\t", " ").strip()
                print(f"[{done}/{total}] {status}\t{file_name}\t{msg}")

    print(f"Completed: total={total}, ok={ok}, failed={failed}")


if __name__ == "__main__":
    main()

