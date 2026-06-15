#!/usr/bin/env python3
"""Scan Jupyter notebooks for secrets by converting them to plain Python first.

gitleaks already scans ``.ipynb`` files, but only as raw JSON: code lives in
escaped, per-line string arrays, so a secret split across array elements or
carrying escaped quotes can slip past the regex rules, and any finding is
reported against an opaque JSON line number. This hook extracts each notebook's
code cells into a throwaway ``.py`` file, runs ``gitleaks`` over that clean
Python, then deletes it -- giving gitleaks readable source and us actionable
output, without ever committing the generated file.

Usage: gitleaks_notebooks.py NOTEBOOK [NOTEBOOK ...]
Exit code: 0 if clean, 1 if any notebook leaks (or cannot be scanned).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def notebook_to_python(nb_path: Path) -> str:
    """Render a notebook's code cells as a single Python source string."""
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    chunks = [f"# notebook: {nb_path}"]
    for i, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        src = cell.get("source", "")
        if isinstance(src, list):
            src = "".join(src)
        chunks.append(f"# --- cell {i} ---\n{src}")
    return "\n\n".join(chunks) + "\n"


def scan_notebook(nb_path: Path, gitleaks: str) -> bool:
    """Convert one notebook to .py, scan it, clean up. True if clean."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="gitleaks-nb-"))
    try:
        py_path = tmp_dir / f"{nb_path.stem}.py"
        py_path.write_text(notebook_to_python(nb_path), encoding="utf-8")
        result = subprocess.run(
            [gitleaks, "dir", str(tmp_dir), "--no-banner"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"gitleaks flagged secrets in {nb_path}:")
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            return False
        return True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main(argv: list[str]) -> int:
    notebooks = [Path(a) for a in argv]
    if not notebooks:
        return 0

    gitleaks = shutil.which("gitleaks")
    if gitleaks is None:
        print(
            "gitleaks not found on PATH; cannot scan notebooks.\n"
            "Install it (e.g. `brew install gitleaks`) and retry.",
            file=sys.stderr,
        )
        return 1

    # Scan every notebook (no short-circuit) so all leaks are reported at once.
    results = [scan_notebook(nb, gitleaks) for nb in notebooks]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
