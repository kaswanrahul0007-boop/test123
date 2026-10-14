"""Turn one photo into a 30s vertical reel (slow zoom, funny caption, optional music).

    python photo_reel.py "C:\\Users\\Rahul\\Desktop\\youtube test" --caption "When the umpire says not out" --music song.mp3

Takes the newest photo in the folder, writes reel.mp4 / reel.json / reel.jpg into <folder>/queue,
ready for:  python upload.py --queue-dir "<folder>\\queue" --region IN --privacy public
"""
import argparse
import json
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, SECONDS, FPS = 1080, 1920, 30, 25


def font(size):
    for p in ("C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def compose(photo, caption, dest):
    img = Image.open(photo).convert("RGB")
    bg = img.resize((W, H)).filter(ImageFilter.GaussianBlur(40))  # blurred fill, no stretched look
    fit = min(W / img.width, (H * 0.65) / img.height)
    fg = img.resize((int(img.width * fit), int(img.height * fit)))
    bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    d = ImageDraw.Draw(bg)
    f = font(68)
    lines = textwrap.wrap(caption, 22)
    y = 160
    for ln in lines:
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2, y), ln, font=f, fill="white", stroke_width=5, stroke_fill="black")
        y += 84
    bg.save(dest)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("folder")
    p.add_argument("--caption", required=True, help="funny line shown on the photo")
    p.add_argument("--title", help="video title (default: the caption)")
    p.add_argument("--description", default="")
    p.add_argument("--music", help="music file you may use (royalty-free / your own)")
    a = p.parse_args()

    folder = Path(a.folder)
    photos = sorted((f for f in folder.iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}),
                    key=lambda f: f.stat().st_mtime, reverse=True)
    if not photos:
        raise SystemExit(f"No photo found in {folder}")
    out = folder / "queue"
    out.mkdir(exist_ok=True)
    frame = out / "reel.jpg"
    compose(photos[0], a.caption, frame)

    frames = SECONDS * FPS
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(frame)]
    if a.music:
        cmd += ["-i", a.music]
    vf = (f"scale=2160:3840,zoompan=z='min(zoom+0.0006,1.2)':d={frames}:s={W}x{H}:fps={FPS},"
          f"fade=t=in:d=0.5,fade=t=out:st={SECONDS - 0.7}:d=0.7,format=yuv420p")
    cmd += ["-vf", vf, "-t", str(SECONDS), "-c:v", "libx264"]
    cmd += ["-c:a", "aac", "-af", f"afade=t=out:st={SECONDS - 1.5}:d=1.5", "-shortest"] if a.music else ["-an"]
    subprocess.run(cmd + [str(out / "reel.mp4")], check=True)

    (out / "reel.json").write_text(json.dumps({
        "title": (a.title or a.caption)[:90] + " #Shorts",
        "description": (a.description or a.caption) + "\n\n#Shorts",
        "tags": ["shorts", "funny", "viral"]}, indent=2))
    print(f"Created {out / 'reel.mp4'} (30s, vertical). Next: python upload.py --queue-dir \"{out}\" --region IN")


if __name__ == "__main__":
    main()
