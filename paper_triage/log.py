"""Logging helpers for the paper triage workflow."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

LOG_FIELDS = [
    "timestamp",
    "title",
    "path",
    "summary",
    "decision",
    "dry_run",
]


def append_log_entry(log_path: Path, entry: Dict[str, str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = log_path.exists()
    with log_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)


def write_digest(digest_dir: Path, actions: Iterable[Dict[str, str]]) -> Path:
    digest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H%M%S")
    digest_path = digest_dir / f"digest-{timestamp}.md"
    lines: List[str] = ["# Weekly Paper Digest", ""]
    for action in actions:
        lines.append(f"## {action['title']}")
        lines.append(f"- Decision: **{action['decision']}**")
        lines.append(f"- File: `{action['path']}`")
        lines.append("")
        lines.append(action.get("summary") or "(no summary)")
        lines.append("")
    digest_path.write_text("\n".join(lines), encoding="utf-8")
    return digest_path


__all__ = ["append_log_entry", "write_digest", "LOG_FIELDS"]
