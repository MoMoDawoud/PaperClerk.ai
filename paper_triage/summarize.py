"""Summarization utilities backed by a local Ollama model."""
from __future__ import annotations

import logging
from typing import Optional

try:
    import ollama
except ImportError as exc:  # pragma: no cover - depends on local env
    ollama = None  # type: ignore

LOGGER = logging.getLogger(__name__)

SUMMARY_PROMPT = (
    "Summarize this academic paper in 1-2 concise lines: clearly describe the problem, "
    "method/approach, dataset or domain context, and key findings or implications. "
    "Highlight anything notable about limitations or future work if space allows."
)


def summarize_text(
    text: str,
    model: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
) -> str:
    """Send the extracted text to an Ollama model and return a summary."""

    if not text.strip():
        return "No extractable text found in the PDF."

    if ollama is None:
        raise RuntimeError(
            "ollama package is not installed. Install it with 'pip install ollama' to enable summaries."
        )

    system = system_prompt or (
        "You help researchers triage papers. Keep answers terse and factual."
    )

    try:
        response = ollama.chat(
            model=model,
            options={"temperature": temperature},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"{SUMMARY_PROMPT}\n\n{text}"},
            ],
        )
    except Exception as exc:  # pragma: no cover - depends on local runtime
        LOGGER.error("Failed to call Ollama: %s", exc)
        return "Ollama call failed. Check local model/runtime."

    message = response.get("message") or {}
    return (message.get("content") or "(no response)").strip()


__all__ = ["summarize_text", "SUMMARY_PROMPT"]
