"""Laptop Automation Bot: type a prompt, Claude controls your laptop.

Usage:
    python bot.py                 # interactive chat
    python bot.py "open notepad and write hello"   # one-shot
    python bot.py --auto "..."    # skip confirmations (use with care)
"""
import base64
import io
import os
import platform
import re
import subprocess
import sys
import webbrowser
from pathlib import Path

import anthropic

MODEL = os.environ.get("BOT_MODEL", "claude-sonnet-5-5")
IS_WIN = platform.system() == "Windows"
AUTO = False

# Commands matching these are always refused, even in --auto mode.
BLOCKED = [
    r"\bformat\s+[a-z]:", r"\brm\s+-rf\s+/(\s|$)", r"\bdel\s+/[sfq].*[a-z]:\\\s*$",
    r"Remove-Item.*-Recurse.*\b[A-Za-z]:\\\s*$", r"\bdiskpart\b", r"\bmkfs\b",
    r"\bshutdown\b", r"\bbcdedit\b", r"reg\s+delete\s+HKLM",
]

SYSTEM = f"""You are a bot that controls the user's {platform.system()} laptop on their behalf.
Use the tools to carry out the request. Prefer shell commands and file tools over
GUI clicking; use screenshot/mouse/keyboard only when needed. Take a screenshot to
verify GUI results. Be concise. Never delete or overwrite user data unless asked.
Home directory: {Path.home()}. Shell: {"PowerShell" if IS_WIN else "bash"}."""

TOOLS = [
    {"name": "run_command", "description": "Run a shell command and return stdout/stderr.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read a text file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write text to a file (creates parent dirs).",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "list_dir", "description": "List files in a directory.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "open_target", "description": "Open a URL, file, folder or application.",
     "input_schema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}},
    {"name": "screenshot", "description": "Capture the screen.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "click", "description": "Click at screen coordinates.",
     "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "double": {"type": "boolean"}}, "required": ["x", "y"]}},
    {"name": "type_text", "description": "Type text with the keyboard.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "press_key", "description": "Press a key or combo, e.g. 'enter' or 'ctrl+s'.",
     "input_schema": {"type": "object", "properties": {"keys": {"type": "string"}}, "required": ["keys"]}},
]


def confirm(desc: str) -> bool:
    if AUTO:
        return True
    return input(f"\n  Allow: {desc}  [y/N] ").strip().lower() in ("y", "yes")


def gui():
    import pyautogui
    pyautogui.FAILSAFE = True  # slam mouse into a corner to abort
    return pyautogui


def run_tool(name: str, a: dict):
    """Returns a string or a list of content blocks."""
    try:
        if name == "run_command":
            cmd = a["command"]
            if any(re.search(p, cmd, re.I) for p in BLOCKED):
                return "Refused: command matches the safety blocklist."
            if not confirm(f"run `{cmd}`"):
                return "User denied this command."
            args = ["powershell", "-NoProfile", "-Command", cmd] if IS_WIN else ["bash", "-lc", cmd]
            r = subprocess.run(args, capture_output=True, text=True, timeout=120)
            return (r.stdout + r.stderr)[-8000:] or f"(exit {r.returncode}, no output)"
        if name == "read_file":
            return Path(a["path"]).expanduser().read_text(errors="replace")[:20000]
        if name == "write_file":
            p = Path(a["path"]).expanduser()
            if not confirm(f"write {len(a['content'])} chars to {p}"):
                return "User denied this write."
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(a["content"])
            return f"Wrote {p}"
        if name == "list_dir":
            return "\n".join(sorted(x.name + ("/" if x.is_dir() else "") for x in Path(a["path"]).expanduser().iterdir()))
        if name == "open_target":
            t = a["target"]
            if t.startswith(("http://", "https://")):
                webbrowser.open(t)
            elif IS_WIN:
                os.startfile(t)  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", t])
            else:
                subprocess.Popen(["xdg-open", t])
            return f"Opened {t}"
        if name == "screenshot":
            img = gui().screenshot()
            img.thumbnail((1568, 1568))
            buf = io.BytesIO()
            img.save(buf, "PNG")
            return [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                 "data": base64.b64encode(buf.getvalue()).decode()}}]
        if name == "click":
            g = gui()
            (g.doubleClick if a.get("double") else g.click)(a["x"], a["y"])
            return "Clicked"
        if name == "type_text":
            gui().write(a["text"], interval=0.02)
            return "Typed"
        if name == "press_key":
            gui().hotkey(*a["keys"].lower().split("+"))
            return "Pressed"
        return f"Unknown tool {name}"
    except Exception as e:  # report errors to the model so it can recover
        return f"Error: {e}"


def run_agent(client, history, prompt):
    history.append({"role": "user", "content": prompt})
    for _ in range(30):  # step limit per request
        resp = client.messages.create(model=MODEL, max_tokens=4096, system=SYSTEM,
                                      tools=TOOLS, messages=history)
        history.append({"role": "assistant", "content": resp.content})
        for b in resp.content:
            if b.type == "text" and b.text.strip():
                print(f"\nbot: {b.text}")
        calls = [b for b in resp.content if b.type == "tool_use"]
        if not calls:
            return
        results = []
        for c in calls:
            print(f"  -> {c.name} {str(c.input)[:120]}")
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": run_tool(c.name, c.input)})
        history.append({"role": "user", "content": results})
    print("\nbot: stopped after 30 steps.")


def main():
    global AUTO
    argv = sys.argv[1:]
    if "--auto" in argv:
        AUTO = True
        argv.remove("--auto")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first (see README).")
    client = anthropic.Anthropic()
    history: list = []
    if argv:
        run_agent(client, history, " ".join(argv))
        return
    print("Laptop bot ready. Type what you want done ('exit' to quit).")
    while True:
        try:
            p = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if p.lower() in ("exit", "quit"):
            break
        if p:
            run_agent(client, history, p)


if __name__ == "__main__":
    main()
