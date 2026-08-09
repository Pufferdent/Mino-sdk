"""Thin wrapper around knewjade's ``sfinder.jar`` (solution-finder).

The SDK intentionally does **not** ship a native Python PC solver: sfinder's
C/Java search is far faster than anything reimplemented here, so for solving we
shell out to it. This module manages the subprocess, temp files, and CSV output
resolution; callers get back a parsed percent or raw CSV rows.

Set the jar location with :data:`SFINDER_JAR` env var, or pass ``jar_path``.
"""

from __future__ import annotations

import csv
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass

_PERCENT_RE = re.compile(r"success\s*=\s*([\d.]+)%")


def _resolve_jar(jar_path: str | None) -> str:
    jar = jar_path or os.environ.get("SFINDER_JAR")
    if not jar:
        raise RuntimeError(
            "sfinder.jar not found: pass jar_path or set SFINDER_JAR env var")
    if not os.path.isfile(jar):
        raise FileNotFoundError(f"sfinder jar not found at {jar!r}")
    return jar


def percent(
    fumen: str,
    pattern: str,
    *,
    clear_lines: int = 4,
    jar_path: str | None = None,
    kicks: str | None = None,
) -> float | None:
    """Run ``sfinder percent`` and return the solve rate (0-100), or ``None``."""
    jar = _resolve_jar(jar_path)
    args = ["java", "-jar", jar, "percent", "-t", fumen,
            "-c", str(clear_lines), "-p", pattern]
    if kicks:
        args += ["-K", kicks]
    out = subprocess.run(args, capture_output=True, text=True, check=False)
    m = _PERCENT_RE.search(out.stdout)
    return float(m.group(1)) if m else None


@dataclass
class PathResult:
    """Parsed ``sfinder path`` CSV (``-k pattern``)."""

    header: list[str]
    rows: list[dict]


def path(
    fumen: str,
    pattern: str | list[str],
    *,
    clear_lines: int = 4,
    fmt_key: str = "pattern",
    jar_path: str | None = None,
    kicks: str | None = None,
) -> PathResult:
    """Run ``sfinder path -f csv`` and return the parsed unique-solution CSV.

    ``pattern`` may be a single pattern string or a list (written to a ``-pp``
    patterns file). The CSV columns are sfinder's (often Japanese) headers, e.g.
    ``ツモ`` (queue), ``使用ミノ`` (used), ``未使用ミノ`` (unused).
    """
    jar = _resolve_jar(jar_path)
    with tempfile.TemporaryDirectory(prefix="sf_path_") as tmp:
        base = os.path.join(tmp, "out")
        args = ["java", "-jar", jar, "path", "-t", fumen,
                "-c", str(clear_lines), "-f", "csv", "-k", fmt_key, "-o", base]
        if kicks:
            args += ["-K", kicks]
        if isinstance(pattern, list):
            pp = os.path.join(tmp, "patterns.txt")
            with open(pp, "w") as fh:
                fh.write("\n".join(pattern))
            args += ["-pp", pp]
        else:
            args += ["-p", pattern]
        subprocess.run(args, capture_output=True, text=True, check=False)

        csv_path = _find_csv(base)
        if csv_path is None:
            return PathResult(header=[], rows=[])
        with open(csv_path, newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            header = reader.fieldnames or []
        return PathResult(header=list(header), rows=rows)


def _find_csv(base: str) -> str | None:
    for suffix in ("_unique.csv", "_minimal.csv", ".csv"):
        cand = base + suffix
        if os.path.isfile(cand):
            return cand
    return None
