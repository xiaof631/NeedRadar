"""使用 trace 模块执行 pytest 并计算覆盖率。"""

from __future__ import annotations

import ast
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from trace import CoverageResults, Trace
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIRS = (PROJECT_ROOT / "app", PROJECT_ROOT / "jobs")
THRESHOLD = float(os.getenv("NEEDRADAR_COVERAGE_THRESHOLD", "75"))
SUMMARY_PATH = PROJECT_ROOT / "coverage-summary.json"


def main(argv: list[str] | None = None) -> int:
    """运行 pytest 并强制覆盖率不低于阈值。"""

    args = argv or []
    tracer = Trace(count=True, trace=False, ignoredirs=_ignored_dirs())
    exit_code = tracer.runfunc(pytest.main, args)
    summary = _build_summary(tracer.results())
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    if exit_code != 0:
        return exit_code
    coverage = summary["coverage"]
    if coverage < THRESHOLD:
        print(
            f"Test coverage {coverage:.2f}% is below required threshold {THRESHOLD}%",
            file=sys.stderr,
        )
        return 1
    return 0


def _ignored_dirs() -> list[str]:
    candidates = {sys.prefix, sys.exec_prefix}
    return [str(Path(item)) for item in candidates if item]


def _build_summary(results: CoverageResults) -> dict[str, Any]:
    counts = results.counts
    executed: dict[Path, set[int]] = defaultdict(set)
    for (filename, lineno), hit in counts.items():
        if hit <= 0:
            continue
        path = Path(filename).resolve()
        try:
            rel_path = path.relative_to(PROJECT_ROOT)
        except ValueError:
            continue
        executed[rel_path].add(lineno)

    files: list[dict[str, Any]] = []
    total_lines = 0
    covered_lines = 0
    for directory in TARGET_DIRS:
        for file in directory.rglob("*.py"):
            if "__pycache__" in file.parts:
                continue
            rel_path = file.resolve().relative_to(PROJECT_ROOT)
            trackable = _trackable_lines(file)
            if not trackable:
                continue
            executed_lines = executed.get(rel_path, set())
            hits = len(trackable & executed_lines)
            total = len(trackable)
            files.append(
                {
                    "path": str(rel_path),
                    "executed_lines": hits,
                    "total_lines": total,
                    "coverage": round(hits / total * 100, 2),
                }
            )
            total_lines += total
            covered_lines += hits

    overall = round(covered_lines / total_lines * 100, 2) if total_lines else 100.0
    return {
        "threshold": THRESHOLD,
        "coverage": overall,
        "files": sorted(files, key=lambda item: item["path"]),
    }


def _trackable_lines(file_path: Path) -> set[int]:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and hasattr(node, "lineno"):
            lines.add(node.lineno)
    return lines


if __name__ == "__main__":  # pragma: no cover - CLI 入口
    raise SystemExit(main(sys.argv[1:]))
