"""CLI entry point for the paper triage assistant with optional email digests."""
from __future__ import annotations

import argparse
import logging
import os
import shutil
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler

from .discover import PaperCandidate, discover_papers
from .emailer import build_message, send_message
from .extract import extract_text
from .log import append_log_entry, write_digest
from .summarize import summarize_text
from .ui import triage_papers

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Weekly paper triage assistant")
    parser.add_argument("--config", default="config.yaml", help="Path to YAML config file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without moving files")
    parser.add_argument("--max-pages", type=int, help="Override max pages to read per paper")
    parser.add_argument("--max-chars", type=int, help="Override max chars per paper")
    parser.add_argument("--archive", help="Override archive directory")
    parser.add_argument("--log-path", help="Override triage log CSV path")
    parser.add_argument("--digest-dir", help="Directory for Markdown digests")
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run continuously with APScheduler using config schedule",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Force a single immediate run even if schedule is configured",
    )
    parser.add_argument(
        "--auto-decision",
        choices=["keep", "remove", "skip"],
        help="Automatically decide for each paper (overrides interactive UI)",
    )
    return parser.parse_args()


def load_config(path: Path) -> Dict[str, Any]:
    default = {
        "input_folders": [],
        "archive_dir": str(Path("archive")),
        "model": "llama3.2:latest",
        "max_pages": 3,
        "max_chars": 4000,
        "metadata_sources": [],
        "log_path": "triage_log.csv",
        "digest_dir": "digests",
        "digest": {"enabled": False},
        "email": {
            "enabled": False,
            "smtp_host": "localhost",
            "smtp_port": 587,
            "use_tls": True,
            "username": None,
            "password_env": None,
            "sender": "paper-triage@example.com",
            "recipients": [],
            "subject": "Weekly paper triage digest",
        },
        "schedule": {
            "enabled": False,
            "day_of_week": "sun",
            "hour": 9,
            "minute": 0,
        },
    }
    if not path.exists():
        LOGGER.warning("Config file %s not found. Using defaults.", path)
        return default

    with path.open("r", encoding="utf-8") as handle:
        user_cfg = yaml.safe_load(handle) or {}

    merged = {**default, **user_cfg}
    merged_schedule = {**default["schedule"], **(user_cfg.get("schedule") or {})}
    merged_digest = {**default["digest"], **(user_cfg.get("digest") or {})}
    merged_email = {**default["email"], **(user_cfg.get("email") or {})}
    merged_auto = {**default.get("auto_decision", {}), **(user_cfg.get("auto_decision") or {})}
    merged["schedule"] = merged_schedule
    merged["digest"] = merged_digest
    merged["email"] = merged_email
    merged["auto_decision"] = merged_auto
    return merged


def summarize_factory(model: str, max_pages: int, max_chars: int):
    @lru_cache(maxsize=None)
    def _summarize(path: Path) -> str:
        text = extract_text(path, max_pages=max_pages, max_chars=max_chars)
        return summarize_text(text, model=model)

    def wrapper(paper: PaperCandidate) -> str:
        return _summarize(paper.path)

    return wrapper


def triage_once(config: Dict[str, Any], args: argparse.Namespace) -> List[Dict[str, str]]:
    papers = discover_papers(config.get("input_folders", []), config.get("metadata_sources"))
    if not papers:
        LOGGER.info("No PDFs found in configured folders.%s", " (dry-run)" if args.dry_run else "")
        return []

    archive_dir = Path(args.archive or config.get("archive_dir", "archive")).expanduser()
    if not args.dry_run:
        archive_dir.mkdir(parents=True, exist_ok=True)

    log_path = Path(args.log_path or config.get("log_path", "triage_log.csv")).expanduser()
    digest_dir = Path(args.digest_dir or config.get("digest_dir", "digests")).expanduser()

    max_pages = args.max_pages or config.get("max_pages", 3)
    max_chars = args.max_chars or config.get("max_chars", 4000)
    model_name = config.get("model", "llama3.2:latest")

    summary_fn = summarize_factory(model_name, max_pages, max_chars)

    decision_mode = _resolve_decision_mode(config.get("auto_decision", {}), args)
    actions = triage_papers(
        papers,
        summary_fn,
        dry_run=args.dry_run,
        auto_decision=decision_mode,
    )

    log_entries: List[Dict[str, str]] = []
    for paper, summary, decision in actions:
        if decision == "r" and not args.dry_run:
            target = archive_dir / paper.path.name
            target = _unique_target(target)
            shutil.move(str(paper.path), target)
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "title": paper.title,
            "path": str(paper.path),
            "summary": summary,
            "decision": decision,
            "dry_run": str(args.dry_run),
        }
        append_log_entry(log_path, entry)
        log_entries.append(entry)

    digest_cfg = config.get("digest", {})
    digest_path = None
    if log_entries and digest_cfg.get("enabled", False):
        digest_path = write_digest(digest_dir, log_entries)

    maybe_send_email(config.get("email", {}), log_entries, digest_path)
    return log_entries


def maybe_send_email(
    email_cfg: Dict[str, Any],
    log_entries: List[Dict[str, str]],
    digest_path: Path | None,
) -> None:
    if not email_cfg.get("enabled"):
        return
    if not log_entries:
        LOGGER.info("Email enabled but no triage actions were taken; skipping send.")
        return

    sender = email_cfg.get("sender")
    recipients = email_cfg.get("recipients") or []
    if not sender or not recipients:
        LOGGER.error("Email sending requires 'sender' and 'recipients' in config.")
        return

    subject = email_cfg.get("subject", "Weekly paper triage digest")
    body_lines = ["Weekly paper triage report", ""]
    for entry in log_entries:
        body_lines.append(f"- {entry['title']} — decision: {entry['decision']} — file: {entry['path']}")
    body_lines.append("")
    body_lines.append("This email was generated automatically by the paper triage assistant.")

    attachments = {}
    if digest_path and digest_path.exists():
        attachments[digest_path.name] = digest_path

    message = build_message(
        subject=subject,
        sender=sender,
        recipients=recipients,
        body_lines=body_lines,
        attachments=attachments,
    )

    password = None
    password_env = email_cfg.get("password_env")
    if password_env:
        password = os.environ.get(password_env)
        if not password:
            LOGGER.error("Email password env var %s is not set; skipping email send.", password_env)
            return

    try:
        send_message(
            message,
            host=email_cfg.get("smtp_host", "localhost"),
            port=int(email_cfg.get("smtp_port", 587)),
            username=email_cfg.get("username"),
            password=password,
            use_tls=bool(email_cfg.get("use_tls", True)),
        )
    except Exception as exc:  # pragma: no cover - depends on SMTP runtime
        LOGGER.error("Failed to send email digest: %s", exc)
    else:
        LOGGER.info("Email digest sent to %s", ", ".join(recipients))


def _unique_target(target: Path) -> Path:
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _resolve_decision_mode(
    auto_cfg: Dict[str, Any],
    args: argparse.Namespace,
) -> str | None:
    if args.auto_decision:
        return args.auto_decision
    if auto_cfg.get("enabled"):
        return auto_cfg.get("default", "keep")
    return None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    config = load_config(Path(args.config).expanduser())

    schedule_cfg = config.get("schedule", {})
    should_schedule = args.schedule or (schedule_cfg.get("enabled") and not args.once)

    if not should_schedule:
        triage_once(config, args)
        return

    scheduler = BlockingScheduler()

    def scheduled_job():
        LOGGER.info("Starting scheduled triage run")
        triage_once(config, args)

    scheduler.add_job(
        scheduled_job,
        "cron",
        day_of_week=schedule_cfg.get("day_of_week", "sun"),
        hour=schedule_cfg.get("hour", 9),
        minute=schedule_cfg.get("minute", 0),
    )

    LOGGER.info("Scheduler started. Press Ctrl+C to exit.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.info("Scheduler stopped.")


if __name__ == "__main__":  # pragma: no cover
    main()
