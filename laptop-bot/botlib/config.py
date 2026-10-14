from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent


def expand(p) -> Path:
    return Path(str(p)).expanduser()


def load(path: str | None = None) -> dict:
    f = Path(path) if path else ROOT / "config.yaml"
    if not f.exists():
        raise SystemExit(f"Missing {f}. Copy config.example.yaml to config.yaml first.")
    cfg = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    cfg.setdefault("dry_run", True)
    cfg.setdefault("tasks", {})
    cfg["workspace"] = str(expand(cfg.get("workspace", "~/BotWorkspace")))
    expand(cfg["workspace"]).mkdir(parents=True, exist_ok=True)
    return cfg
