# Title Extraction (OCR-based)

This folder contains OCR-based scripts to extract paper titles from PDFs, especially when direct PDF text extraction is unreliable due to embedded font encoding issues.

## What has been implemented

- `extract_title.py`
  - Core OCR title extraction logic.
  - Renders page 1 using Poppler `pdftoppm`.
  - Runs OCR with `tesseract` TSV output.
  - Reconstructs line-level text from word boxes.
  - Chooses title from top-of-page candidates using confidence/length heuristics.
  - Supports timeouts for external subprocess calls.

- `extract_title_debug.py`
  - Debug helper to print top OCR line candidates and the chosen line.
  - Useful for inspecting why a title was selected.

- `batch_extract_titles.py`
  - Scalable batch runner for large collections (e.g., 1000 PDFs).
  - Uses in-process calls to `extract_title_from_pdf()` (avoids per-file Python process startup).
  - Uses bounded parallelism with `ThreadPoolExecutor`.
  - Supports fallback DPI retries and per-call timeouts.
  - Streams progress and prints final summary.

## Why OCR instead of direct PDF text extraction?

Early testing with `pdftotext` / `pdftohtml -xml` produced garbled text for target documents (font/glyph encoding problems). OCR reads the rendered page image and is therefore more robust for those files.

## Requirements

The scripts rely on system tools:

- `python3` (3.9+ recommended)
- `pdftoppm` (from Poppler)
- `tesseract`

Quick checks:

```bash
which python3
which pdftoppm
which tesseract
```

## How to run

### 1) Single PDF

```bash
python3 title-extraction/extract_title.py /path/to/file.pdf
```

Useful options:

```bash
python3 title-extraction/extract_title.py /path/to/file.pdf \
  --dpi 300 \
  --psm 6 \
  --search-top-n 8 \
  --timeout-sec 45
```

### 2) Debug one PDF

```bash
python3 title-extraction/extract_title_debug.py /path/to/file.pdf --search-top-n 8
```

### 3) Batch extraction (recommended for large runs)

```bash
python3 -B title-extraction/batch_extract_titles.py /path/to/pdf_folder \
  --recursive \
  --workers 8 \
  --timeout-sec 60
```

Notes:
- `-B` disables Python bytecode writes (`__pycache__`).
- Output format is line-based progress:
  - `[done/total] ok<TAB>filename<TAB>title`
  - final summary: `Completed: total=..., ok=..., failed=...`

## Current behavior and known limitations

- Some papers may still return author/affiliation lines instead of title.
- OCR quality depends on page layout, scan quality, and language/font characteristics.
- Timeout applies to each external OCR/render subprocess call, not the total file pipeline.

## Suggested next improvements

1. **Better title scoring**
   - Prefer larger text height and centered lines near the top.
   - Penalize lines with email addresses, institution keywords, and long number strings.

2. **Hybrid extraction pipeline**
   - Attempt lightweight text extraction first for clean PDFs.
   - Fallback to OCR only when text quality looks corrupted.

3. **Output options**
   - Add JSONL/CSV output mode for downstream processing.
   - Add confidence scores per extracted title.

4. **Performance tuning**
   - Auto-tune worker count based on CPU/memory.
   - Add optional image pre-processing for difficult scans.

5. **Evaluation harness**
   - Add a small benchmark set with expected titles.
   - Report accuracy and runtime before/after heuristic changes.

## Quick example for your current dataset

```bash
python3 -B title-extraction/batch_extract_titles.py \
  "/Users/jing/Desktop/Jing-Library/2025_NeurIPS_Best_Paper" \
  --workers 4 \
  --timeout-sec 60
```

