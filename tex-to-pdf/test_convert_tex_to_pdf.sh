#!/usr/bin/env bash
set -euo pipefail

# test_convert_tex_to_pdf.sh
# Runs conversion to PDF on path-to-latex-file and writes output into this directory.

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# Usage: ./test_convert_tex_to_pdf.sh path-to-latex-file
INPUT="${1:-path-to-latex-file}"
OUTDIR="$(pwd)"

if [[ ! -f "$INPUT" ]]; then
  echo "Test input not found: $INPUT" >&2
  exit 3
fi

# prefer the shell script if available
if [[ -x "$(pwd)/convert_tex_to_pdf.sh" ]]; then
  bash "$(pwd)/convert_tex_to_pdf.sh" "$INPUT" "$OUTDIR"
else
  # fallback to python wrapper
  python3 "$(pwd)/convert_tex_to_pdf.py" "$INPUT" "$OUTDIR"
fi

ls -l "$OUTDIR/"*.pdf
