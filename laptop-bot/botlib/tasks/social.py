import csv
from pathlib import Path
import yaml
from botlib.config import expand, ROOT
from botlib.tasks import task


def _run_recipe(page, steps, text, image):
    for step in steps:
        (op, arg), = step.items()
        if op == "goto":
            page.goto(arg)
        elif op == "click":
            page.click(arg)
        elif op == "fill":
            page.fill(arg[0], arg[1].format(text=text))
        elif op == "upload":
            if image:
                page.set_input_files(arg, image)
        elif op == "wait":
            page.wait_for_timeout(int(arg))


@task("social_post")
def social_post(cfg):
    """Posts every row in the queue CSV whose status is 'pending'."""
    t = cfg["tasks"]["social"]
    queue = expand(t["queue"])
    if not queue.exists():
        queue.write_text("platform,text,image,status\n", encoding="utf-8")
        return f"social_post: created empty queue at {queue}"
    rows = list(csv.DictReader(queue.open(newline="", encoding="utf-8")))
    pending = [r for r in rows if r["status"].strip().lower() == "pending"]
    if not pending:
        return "social_post: nothing pending"
    if cfg["dry_run"]:
        return "social_post [dry-run]:\n" + "\n".join(f"  {r['platform']}: {r['text'][:60]}" for r in pending)

    recipes = yaml.safe_load((ROOT / t["recipes_file"]).read_text(encoding="utf-8"))
    from playwright.sync_api import sync_playwright
    log = []
    with sync_playwright() as p:
        # Persistent profile = you log in manually once (headed), bot reuses the session.
        ctx = p.chromium.launch_persistent_context(str(expand(t["profile_dir"])), headless=False)
        page = ctx.new_page()
        for r in pending:
            try:
                _run_recipe(page, recipes[r["platform"]], r["text"], r["image"])
                r["status"] = "done"
                log.append(f"posted to {r['platform']}")
            except Exception as e:
                r["status"] = "failed"
                log.append(f"FAILED {r['platform']}: {e}")
        ctx.close()
    with queue.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["platform", "text", "image", "status"])
        w.writeheader()
        w.writerows(rows)
    return "social_post:\n" + "\n".join(log)


@task("social_login")
def social_login(cfg):
    """Opens the bot's browser so you can log in to your accounts once."""
    t = cfg["tasks"]["social"]
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(expand(t["profile_dir"])), headless=False)
        ctx.new_page()
        input("Log in to your accounts in the opened browser, then press Enter here...")
        ctx.close()
    return "social_login: session saved"
