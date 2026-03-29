#!/usr/bin/env python3
"""
convert_tex_to_pdf.py
A small Python wrapper to convert a .tex file to PDF.
Usage: convert_tex_to_pdf.py <input-tex-file> [output-dir]
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} <input-tex-file> [output-dir]", file=sys.stderr)
    sys.exit(2)

input_path = Path(sys.argv[1])
output_dir = Path(sys.argv[2]) if len(sys.argv) >= 3 else Path.cwd()

if not input_path.exists():
    print(f"Input file not found: {input_path}", file=sys.stderr)
    sys.exit(3)

name = input_path.stem

# Candidate engines in order
candidates = [
    '/Library/TeX/texbin/pdflatex',
    shutil.which('pdflatex'),
    shutil.which('xelatex'),
    shutil.which('lualatex'),
]

import tempfile
output_dir.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as tmpdir:
    last_err = None
    for c in candidates:
        if not c:
            continue
        engine_path = Path(c)
        if not engine_path.exists():
            continue
        print(f'Trying engine: {c}')
        cmd = [str(engine_path), '-interaction=nonstopmode', '-halt-on-error', f'-output-directory={tmpdir}', str(input_path)]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            pdf_path = Path(tmpdir) / f"{name}.pdf"
            if pdf_path.exists():
                dest = output_dir / f"{name}.pdf"
                shutil.copy2(pdf_path, dest)
                print(f'Wrote {dest}')
                sys.exit(0)
        except subprocess.CalledProcessError as e:
            last_err = e
            print(f'Engine {c} failed, trying next...', file=sys.stderr)

    print('All engines failed to produce a PDF.', file=sys.stderr)
    if last_err:
        print(f'Last error: {last_err}', file=sys.stderr)
    sys.exit(5)

sys.exit(0)
