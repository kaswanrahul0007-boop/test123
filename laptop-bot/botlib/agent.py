"""AI agent: you give a goal in plain words, Claude drives the bot's tools (and, optionally, the screen)."""
import base64
import io
import subprocess
from pathlib import Path
import anthropic
from botlib import tasks
from botlib.config import expand

MODEL = "claude-sonnet-5-5"
MAX_STEPS = 25

TOOLS = [
    {"name": "run_task", "description": "Run a built-in bot task by name.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "list_dir", "description": "List files in a folder.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "read_file", "description": "Read a text file (max 20k chars).",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write a text file inside the bot workspace only.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                      "required": ["path", "content"]}},
    {"name": "run_command", "description": "Run a shell command. The user must approve each one.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "screenshot", "description": "Take a screenshot of the screen.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "click", "description": "Click at screen coordinates. User must approve.",
     "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                      "required": ["x", "y"]}},
    {"name": "type_text", "description": "Type text on the keyboard. User must approve.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
]
NEEDS_APPROVAL = {"run_command", "click", "type_text"}


def _approve(msg):
    return input(f"\n[APPROVE?] {msg}  (y/N) ").strip().lower() == "y"


def _exec(name, args, cfg):
    ws = expand(cfg["workspace"]).resolve()
    if name == "run_task":
        return tasks.run(args["name"], cfg)
    if name == "list_dir":
        return "\n".join(sorted(p.name for p in expand(args["path"]).iterdir()))
    if name == "read_file":
        return expand(args["path"]).read_text(encoding="utf-8", errors="replace")[:20000]
    if name == "write_file":
        p = (ws / args["path"]).resolve()
        if ws not in p.parents and p != ws:
            return "refused: path outside workspace"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(args["content"], encoding="utf-8")
        return f"wrote {p}"
    if name == "run_command":
        r = subprocess.run(args["command"], shell=True, capture_output=True, text=True, timeout=120)
        return (r.stdout + r.stderr)[:8000]
    import pyautogui
    if name == "click":
        pyautogui.click(args["x"], args["y"])
        return "clicked"
    if name == "type_text":
        pyautogui.write(args["text"], interval=0.02)
        return "typed"
    if name == "screenshot":
        buf = io.BytesIO()
        pyautogui.screenshot().save(buf, "PNG")
        return [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                              "data": base64.b64encode(buf.getvalue()).decode()}}]
    return f"unknown tool {name}"


def run_agent(goal: str, cfg: dict):
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    system = (f"You are a careful laptop assistant on Windows. Available tasks: {sorted(tasks.load_all())}. "
              f"Workspace: {cfg['workspace']}. dry_run={cfg['dry_run']}. Prefer built-in tasks over raw "
              "clicking. Never delete files, spend money, or send messages the user did not ask for. "
              "Stop and say what you did when finished.")
    msgs = [{"role": "user", "content": goal}]
    for _ in range(MAX_STEPS):
        resp = client.messages.create(model=MODEL, max_tokens=2048, system=system, tools=TOOLS, messages=msgs)
        msgs.append({"role": "assistant", "content": resp.content})
        for b in resp.content:
            if b.type == "text":
                print(b.text)
        calls = [b for b in resp.content if b.type == "tool_use"]
        if not calls:
            return
        results = []
        for c in calls:
            if c.name in NEEDS_APPROVAL and not _approve(f"{c.name} {c.input}"):
                out = "User denied this action."
            else:
                try:
                    out = _exec(c.name, c.input, cfg)
                except Exception as e:
                    out = f"error: {e}"
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": out})
        msgs.append({"role": "user", "content": results})
    print("Stopped: step limit reached.")
