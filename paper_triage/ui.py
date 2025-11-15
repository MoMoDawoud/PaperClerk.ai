"""Simple CLI flow for triaging papers."""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Callable, Iterable, List, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from .discover import PaperCandidate

console = Console()

Action = Tuple[PaperCandidate, str, str]


def triage_papers(
    papers: Iterable[PaperCandidate],
    summary_fn: Callable[[PaperCandidate], str],
    *,
    dry_run: bool = False,
    auto_decision: str | None = None,
) -> List[Action]:
    """Iterate through papers and capture user decisions."""

    actions: List[Action] = []
    for index, paper in enumerate(papers, start=1):
        console.rule(f"Paper {index}")
        summary = summary_fn(paper)
        if auto_decision:
            decision = _auto_decide(auto_decision)
        else:
            decision = _prompt_for_decision(paper, summary, dry_run)
        actions.append((paper, summary, decision))
    return actions


def _prompt_for_decision(paper: PaperCandidate, summary: str, dry_run: bool) -> str:
    table = Table(show_header=False, box=None)
    table.add_row("Title", paper.title)
    table.add_row("Path", str(paper.path))
    if paper.metadata:
        for key, value in paper.metadata.items():
            if key == "file_key":
                continue
            table.add_row(key.title(), str(value))

    console.print(table)
    console.print(
        Panel(summary or "No summary available.", title="Summary", subtitle="llm", expand=False)
    )

    if dry_run:
        console.print("[yellow]Dry-run: files will not be moved or modified.[/yellow]")

    while True:
        choice = (
            Prompt.ask("Choose action [k]eep/[r]emove/[s]kip/[o]pen", default="k")
            .strip()
            .lower()
        )
        if choice == "o":
            _open_file(paper.path)
            continue
        if choice in {"k", "r", "s"}:
            return choice
        console.print("[red]Invalid choice. Use k, r, s, or o.[/red]")


def _open_file(path: Path) -> None:
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        elif system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as exc:  # pragma: no cover - platform dependent
        console.print(f"[red]Failed to open {path}: {exc}[/red]")


def _auto_decide(mode: str) -> str:
    allowed = {"k", "r", "s"}
    short = mode[0].lower()
    if short in allowed:
        return short
    raise ValueError(f"Unsupported auto decision '{mode}'")


__all__ = ["triage_papers"]
