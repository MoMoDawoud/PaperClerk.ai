"""Email helper utilities for weekly digests."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Mapping, Sequence


def build_message(
    *,
    subject: str,
    sender: str,
    recipients: Sequence[str],
    body_lines: Iterable[str],
    attachments: Mapping[str, Path] | None = None,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content("\n".join(body_lines))

    if attachments:
        for filename, path in attachments.items():
            if not path.exists():
                continue
            subtype = "markdown" if path.suffix.lower() in {".md", ".markdown"} else "plain"
            data = path.read_text(encoding="utf-8")
            message.add_attachment(
                data,
                subtype=subtype,
                filename=filename,
            )
    return message


def send_message(
    message: EmailMessage,
    *,
    host: str,
    port: int,
    username: str | None = None,
    password: str | None = None,
    use_tls: bool = True,
) -> None:
    if use_tls:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            if username and password:
                server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port) as server:
            if username and password:
                server.login(username, password)
            server.send_message(message)


__all__ = ["build_message", "send_message"]
