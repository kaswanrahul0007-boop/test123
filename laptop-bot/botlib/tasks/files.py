import shutil
from pathlib import Path
from botlib.config import expand
from botlib.tasks import task


@task("organize_files")
def organize_files(cfg):
    t = cfg["tasks"]["organize_files"]
    folder = expand(t["folder"])
    ext_map = {e.lower(): cat for cat, exts in t["rules"].items() for e in exts}
    moved = []
    for f in folder.iterdir():
        if not f.is_file():
            continue
        cat = ext_map.get(f.suffix.lower())
        if not cat:
            continue
        dest_dir = folder / cat
        dest = dest_dir / f.name
        n = 1
        while dest.exists():  # never overwrite
            dest = dest_dir / f"{f.stem} ({n}){f.suffix}"
            n += 1
        if cfg["dry_run"]:
            moved.append(f"[dry-run] {f.name} -> {cat}/")
            continue
        dest_dir.mkdir(exist_ok=True)
        shutil.move(str(f), str(dest))
        moved.append(f"{f.name} -> {cat}/")
    return f"organize_files: {len(moved)} file(s)\n" + "\n".join(moved)
