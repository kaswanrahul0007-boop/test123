# Laptop Automation Bot

Type a prompt in plain language; the bot controls your laptop (shell commands, files,
opening apps/URLs, screenshots, mouse and keyboard) using Claude.

## Setup (Windows)
1. Install Python 3.10+.
2. Copy this folder to `C:\Users\Rahul\Desktop\laptop automation`.
3. In PowerShell inside that folder:
   ```
   pip install -r requirements.txt
   setx ANTHROPIC_API_KEY "your-key-here"   # then open a new terminal
   ```

## Run
```
python bot.py                                  # interactive
python bot.py "create a folder Reports on Desktop and open it"
python bot.py --auto "..."                     # no confirmations
```

## Examples
- "Open Chrome and search for today's weather"
- "Organize my Downloads folder by file type"
- "Take a screenshot and tell me what's open"
- "Write a to-do list in Notepad and save it on the Desktop"

## Safety
- Shell commands and file writes ask `y/N` unless you use `--auto`.
- A blocklist refuses disk formatting, shutdown, etc., even in `--auto`.
- Move the mouse into a screen corner to abort GUI control (pyautogui failsafe).
- It runs with your user permissions: review what it asks to do.
