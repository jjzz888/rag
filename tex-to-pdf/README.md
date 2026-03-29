**File Conversion**

- **Purpose**: A small toolset to compile LaTeX (`.tex`) files to PDF, with engine fallback (prefers `pdflatex`, falls back to `xelatex`/`lualatex`) and safe temporary build directory handling. The test runner demonstrates converting a sample LaTeX file and writes the resulting PDF to this folder.

**Requirements**
- **OS**: macOS (scripts are POSIX-compatible and tested on zsh).
- **TeX distribution**: Install a TeX engine. Recommended options:
  - **MacTeX (full)**: provides `pdflatex`, `xelatex`, `lualatex` and many packages.
    - Install via Homebrew: ``brew install --cask mactex``
  - **BasicTeX (smaller)**: install and then add required packages via `tlmgr`.
    - Example:
      ```bash
      brew install --cask basictex
      sudo tlmgr update --self
      sudo tlmgr install collection-latexrecommended collection-latexextra collection-fontsrecommended latexmk
      ```
- **Python** (optional): `python3` if you want to use `convert_tex.py` wrapper.

**Files in this directory**
- `convert_tex_to_pdf.sh` — shell wrapper that tries multiple TeX engines, builds in a temporary directory, and copies the resulting PDF to the requested output directory.
- `convert_tex_to_pdf.py` — Python wrapper that provides the same functionality programmatically.
- `test_convert_tex_to_pdf.sh` — small test runner that compiles a LaTeX file (use `path-to-latex-file`) and writes the PDF into this directory.

**Basic Usage**

- Convert a `.tex` file with the shell script (preferred on macOS with MacTeX):

  ```bash
  # from repository root
  rag/file-conversion/convert_tex_to_pdf.sh path-to-latex-file rag/file-conversion
  ```

- Convert using the Python wrapper:

  ```bash
  python3 rag/file-conversion/convert_tex_to_pdf.py path-to-latex-file rag/file-conversion
  ```

- Run the included test script (will compile the latex file into this folder):

  ```bash
  cd rag/file-conversion
  ./test_convert_tex_to_pdf.sh
  ls -l *.pdf
  ```

**Notes & Troubleshooting**
- The scripts attempt engines in this order: `/Library/TeX/texbin/pdflatex`, `pdflatex`, `xelatex`, `lualatex`.
- For Chinese documents using the `ctex` package, `pdflatex` may fail due to fontset issues; `xelatex` is usually a good fallback.
- If the TeX engine is installed but not found, ensure TeX bin is in your `PATH` (macOS):

  ```bash
  export PATH="/Library/TeX/texbin:$PATH"
  # add the above line to ~/.zshrc to make it persistent
  ```

- If fonts or packages are missing, install them via `tlmgr` or install the full MacTeX distribution.

**Exit Codes**
- `2` — incorrect usage (missing argument).
- `3` — input file not found.
- `4` — no TeX engine found.
- `5` — TeX engine(s) tried but failed to produce a PDF.

**Further Improvements & Ideas**
- **Batch processing**: add a script to walk a folder and convert all `.tex` files in parallel (with concurrency limits).
- **Heuristic engine selection**: inspect the `.tex` contents for `\usepackage{ctex}` or non-ASCII characters and prefer `xelatex` for CJK documents.
- **Containerized build**: provide a `Dockerfile` using a TeX Live image (e.g., `tianon/latex` or `texlive/texlive`) so conversion works reproducibly in CI or on systems without MacTeX.
- **API/Service**: add a small HTTP service (Flask/FastAPI) that accepts a `.tex` upload and returns a compiled PDF. Important: sandbox execution and size limits are required for safety.
- **CI Integration**: add a GitHub Action workflow that can compile `.tex` files and attach generated PDFs as artifacts.
- **Logging & better error reporting**: capture and surface the LaTeX log output on failure to help users diagnose missing packages or font issues.
- **Cleanup modes**: add flags to keep or remove auxiliary files, or to save logs alongside PDFs.

**License / Attribution**
- Minimal scripts provided as-is for convenience. Modify to fit your environment and security model.
