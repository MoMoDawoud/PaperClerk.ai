"""Utilities for finding papers and optional metadata."""
from __future__ import annotations

import json
import logging
import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Any

LOGGER = logging.getLogger(__name__)


@dataclass
class PaperCandidate:
    """Represents a PDF to triage."""

    path: Path
    title: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def discover_papers(
    folders: Iterable[str],
    metadata_sources: Optional[Iterable[Dict[str, str]]] = None,
) -> List[PaperCandidate]:
    """Scan folders for PDFs and enrich with optional metadata."""

    metadata_lookup = _build_metadata_lookup(metadata_sources or [])
    candidates: List[PaperCandidate] = []
    seen_paths = set()

    for folder in folders:
        folder_path = Path(folder).expanduser()
        if not folder_path.exists():
            LOGGER.warning("Input folder does not exist: %s", folder)
            continue

        for pdf_path in sorted(folder_path.rglob("*.pdf")):
            norm_key = pdf_path.name.lower()
            info = metadata_lookup.get(norm_key, {})
            title = info.get("title") or pdf_path.stem
            if pdf_path in seen_paths:
                continue
            seen_paths.add(pdf_path)
            candidates.append(PaperCandidate(path=pdf_path, title=title, metadata=info))

    return candidates


def _build_metadata_lookup(sources: Iterable[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for source in sources:
        source_type = (source.get("type") or "bookmarks").lower()
        path = Path(source["path"]).expanduser()
        if not path.exists():
            LOGGER.warning("Metadata source not found: %s", path)
            continue

        try:
            if source_type == "bookmarks":
                records = _parse_bookmarks_json(path)
            elif source_type in {"zotero", "mendeley"}:
                records = _parse_reference_export(path)
            else:
                LOGGER.warning("Unknown metadata source type '%s'", source_type)
                continue
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.exception("Failed to parse metadata source %s: %s", path, exc)
            continue

        for record in records:
            file_key = record.get("file_key")
            if not file_key:
                continue
            lookup[file_key] = record

    return lookup


def _parse_bookmarks_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    records: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        entries = data.get("bookmarks") or []
    else:
        entries = data

    for entry in entries:
        file_path = entry.get("path") or entry.get("file") or ""
        if not file_path:
            continue
        file_key = Path(file_path).name.lower()
        records.append(
            {
                "title": entry.get("title") or Path(file_path).stem,
                "file_key": file_key,
                "source": str(path),
            }
        )
    return records


def _parse_reference_export(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            attachment = (
                row.get("File Attachments")
                or row.get("Attachments")
                or row.get("file")
                or row.get("path")
                or ""
            )
            if not attachment:
                continue
            attachment = attachment.split(";", 1)[0].strip()
            if not attachment:
                continue
            file_key = Path(attachment).name.lower()
            records.append(
                {
                    "title": row.get("Title") or row.get("title") or Path(attachment).stem,
                    "file_key": file_key,
                    "authors": row.get("Author") or row.get("Authors"),
                    "year": row.get("Year"),
                    "source": str(path),
                }
            )
    return records


__all__ = ["discover_papers", "PaperCandidate"]
