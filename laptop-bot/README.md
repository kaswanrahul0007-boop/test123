# Laptop Bot (Windows)

A bot that does your computer work for you. Three modes, one tool:

| Mode | Command | Use for |
|---|---|---|
| **Scheduled tasks** | `python bot.py schedule` | Repeating jobs: organize files, reports, email digest, social posts |
| **AI agent** | `python bot.py agent "goal in plain words"` | One-off jobs described in plain English; Claude uses the tools (asks approval for risky steps) |
| **Record & replay** | `python bot.py record a.json` / `python bot.py replay a.json` | Anything else you can click through once |

## Setup (Windows, PowerShell)
```powershell
cd laptop-bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
copy config.example.yaml config.yaml     # then edit it
setx ANTHROPIC_API_KEY "sk-ant-..."       # only for agent mode
setx BOT_EMAIL_PASSWORD "your-app-password"
```
Reopen the terminal after `setx`.

## First run
```powershell
python bot.py list                 # shows tasks
python bot.py run organize_files   # dry-run: only prints what it WOULD do
```
When the output looks right, set `dry_run: false` in `config.yaml`.

## Tasks
- `organize_files` – sorts Downloads into folders by type (never overwrites).
- `report` – turns CSVs in your data folder into an Excel/Word report.
- `email_digest` – summarizes unread mail and emails you the digest (reads without marking as read).
- `social_login` – run once; log in to your accounts in the bot's browser.
- `social_post` – posts rows marked `pending` in `posts.csv` (`platform,text,image,status`).

Run on startup: put a shortcut to `start_bot.bat` in `shell:startup`.

## Add your own task
Create `botlib/tasks/mytask.py` with `@task("mytask") def f(cfg): ...`, add its module name to `load_all()` in `botlib/tasks/__init__.py`, then add it to `schedule:`.

## Safety notes
- `dry_run: true` is the default; nothing is sent/posted/moved until you turn it off.
- Agent mode asks y/N before every shell command, click, or typing. Slam the mouse into a screen corner to abort click/replay.
- Keep passwords in environment variables only. `config.yaml` is git-ignored.
- Social sites change their pages and many restrict automation in their Terms; if a recipe breaks, edit selectors in `recipes.yaml`, and use official APIs where possible to avoid account bans.
