#!/usr/bin/env bash
set -euo pipefail

# convert_tex_to_pdf.sh
# Usage: convert_tex_to_pdf.sh <input-tex-file> [output-dir]
# Detects an available TeX engine and converts the input .tex to PDF.

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <input-tex-file> [output-dir]" >&2
  exit 2
fi

INPUT="$1"
OUTDIR="${2:-$(pwd)}"

if [[ ! -f "$INPUT" ]]; then
  echo "Input file not found: $INPUT" >&2
  exit 3
fi

BASENAME=$(basename "$INPUT")
NAME="${BASENAME%.*}"

# Candidate engines in order of preference. We'll try each until one succeeds.
engines=("/Library/TeX/texbin/pdflatex" "$(command -v pdflatex 2>/dev/null || true)" "$(command -v xelatex 2>/dev/null || true)" "$(command -v lualatex 2>/dev/null || true)")

# Use a temporary directory for compilation artifacts
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

success=0
for e in "${engines[@]}"; do
  if [[ -z "$e" ]]; then
    continue
  fi
  if [[ ! -x "$e" ]]; then
    continue
  fi
  echo "Trying TeX engine: $e"
  # run twice to resolve references/outlines
  if "$e" -interaction=nonstopmode -halt-on-error -output-directory="$TMPDIR" "$INPUT" >/dev/null 2>&1 && \
     "$e" -interaction=nonstopmode -halt-on-error -output-directory="$TMPDIR" "$INPUT" >/dev/null 2>&1; then
    success=1
    engine="$e"
    break
  else
    echo "Engine $e failed; trying next..."
  fi
done

PDF="$TMPDIR/$NAME.pdf"
if [[ $success -ne 1 || ! -f "$PDF" ]]; then
  echo "All engines failed to produce a PDF. See temporary dir contents:" >&2
  ls -la "$TMPDIR" >&2 || true
  exit 5
fi

mkdir -p "$OUTDIR"
cp -f "$PDF" "$OUTDIR/${NAME}.pdf"

# Optionally copy log for debugging
cp -f "$TMPDIR/${NAME}.log" "$OUTDIR/" 2>/dev/null || true

echo "Wrote $OUTDIR/${NAME}.pdf"
exit 0
