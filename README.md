# PaperClerk AI

PaperClerk AI keeps your research library tidy. It scans folders, extracts the first pages, summarizes them with a local Ollama/LLaMA model, and records keep/remove decisions. You can drive it interactively in a Rich CLI or let it run unattended (auto-keep/skip/remove) while emailing a digest every day or week.

## Why PaperClerk?
- **Hands-off triage** – auto-summarize and auto-decide (keep/remove/skip) when you cannot babysit the CLI.
- **Research context** – each summary highlights problem, method, domain, findings, and notable limitations.
- **Safe archiving** – removals get moved into an archive folder; nothing is deleted.
- **Audit trail** – CSV log + Markdown digest documenting every action.
- **Daily/weekly cadence** – APScheduler and LaunchAgents keep the workflow running in the background.
- **Bring-your-own model** – uses local Ollama models (defaults to `llama3.2:latest`).

## Quickstart
```bash
cd paper_triage_tool
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
ollama pull llama3.2:latest   # or another local model
```
Run a manual session:
```bash
python -m paper_triage.main --config config.yaml --dry-run
```
Drop `--dry-run` (and optionally add `--auto-decision keep|skip|remove`) once you trust the flow.

## Configuration
Edit `config.yaml` (or pass another file via `--config`):
```yaml
input_folders:
  - /path/to/papers
archive_dir: /path/to/archive
model: llama3.2:latest
max_pages: 3
max_chars: 4000
metadata_sources:
  - type: bookmarks
    path: /path/to/bookmarks.json
  - type: zotero
    path: /path/to/zotero-export.csv
log_path: triage_log.csv
digest_dir: digests
schedule:
  enabled: true
  day_of_week: "*"
  hour: 9
  minute: 0
digest:
  enabled: true
auto_decision:
  enabled: true
  default: keep
email:
  enabled: true
  smtp_host: smtp.gmail.com
  smtp_port: 587
  use_tls: true
  username: you@university.edu
  password_env: TRIAGE_EMAIL_PASSWORD
  sender: you@university.edu
  recipients:
    - you@university.edu
  subject: "PaperClerk AI digest"
```
Key options:
- `auto_decision` – set to `true` for unattended runs; `default` can be `keep`, `skip`, or `remove`.
- `schedule.enabled` – run continuously via APScheduler; configure day/time using cron-style values.
- `email.password_env` – expose your SMTP password/app-password via env var or Keychain before launching.

## CLI reference
- `--dry-run` – log/summary only, no file moves.
- `--max-pages` / `--max-chars` – override extraction limits.
- `--archive`, `--log-path`, `--digest-dir` – override destinations per run.
- `--auto-decision keep|remove|skip` – override config to force unattended mode.
- `--schedule` – keep the scheduler alive; combine with `auto_decision` for daily/weekly digests.

## Email digests & automation
1. Fill out the `email` block; store the SMTP secret as `export TRIAGE_EMAIL_PASSWORD='app password'` or in Keychain (`security add-generic-password ...`).
2. Enable `digest.enabled` so each run writes `digests/digest-YYYY-MM-DD-HHMMSS.md`.
3. Run `python -m paper_triage.main --config config.yaml --schedule` (optionally via a LaunchAgent/cron). Sample macOS LaunchAgent:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.papertriage.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd /path/to/paper_triage_tool && source .venv/bin/activate && export TRIAGE_EMAIL_PASSWORD="$(security find-generic-password -a TRIAGE_EMAIL_PASSWORD -s paper_triage_pwd -w)" && python -m paper_triage.main --config config.yaml --schedule</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/papertriage.log</string>
  <key>StandardErrorPath</key><string>/tmp/papertriage.err</string>
</dict>
</plist>
```
With `auto_decision` enabled the scheduler will keep/skip/remove automatically and email the digest daily.

## Architecture at a glance
- `discover.py` – walks folders and merges bookmark/Zotero/Mendeley CSV metadata.
- `extract.py` – pulls text from the first few pages using `pypdf`.
- `summarize.py` – sends the extracted text to an Ollama chat model with a concise, context-rich prompt.
- `ui.py` – Rich CLI plus auto-decision helper.
- `log.py` – CSV logging + Markdown digest writer.
- `emailer.py` – builds/sends SMTP messages with optional digest attachment.
- `main.py` – configuration, scheduling, archiving, email dispatch.

## Extending the project
- Swap the model in `summarize.py` for your favorite Ollama build or a different local API.
- Add OCR for scanned PDFs by integrating `pytesseract` in `extract.py`.
- Implement richer auto-decision heuristics (e.g., priority scoring) inside `ui.py`.
- Add new notification backends (Slack/Teams/Notion) following the email pattern.
- Wire up pytest to cover discovery/extraction/summarization helpers before large refactors.

## Contributing
1. Fork the repo and create a feature branch.
2. `pip install -r requirements.txt` in a virtualenv.
3. Add tests/docs for any new config options or flows.
4. Open a PR describing the changes and any manual testing.

## License
 **Apache 2.0** 
