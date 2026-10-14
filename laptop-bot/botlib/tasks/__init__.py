"""Task registry. A task is `fn(cfg) -> str` registered with @task("name")."""
import importlib

REGISTRY: dict = {}


def task(name):
    def deco(fn):
        REGISTRY[name] = fn
        return fn
    return deco


def load_all():
    for m in ("files", "reports", "email_task", "social"):
        importlib.import_module(f"botlib.tasks.{m}")
    return REGISTRY


def run(name: str, cfg: dict) -> str:
    reg = load_all()
    if name not in reg:
        raise SystemExit(f"Unknown task '{name}'. Available: {', '.join(sorted(reg))}")
    return reg[name](cfg)
