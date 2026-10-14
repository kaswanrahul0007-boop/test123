"""Build a fact-based explainer video from Wikipedia text and openly licensed images.

    python make_video.py "Black hole" --out queue

Facts come from the Wikipedia article summary (real, cited). Images come from Wikimedia Commons
and only openly licensed ones (public domain / CC) are used. The video's description lists the
source article and every image credit. Review the result before publishing.
Writes <slug>.mp4, <slug>.json (title/description/tags) and <slug>.jpg (thumbnail) for upload.py.
"""
import argparse
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

W, H = 1280, 720
WRAP, FONT_SIZE = 48, 38
HEADERS = {"User-Agent": "knowledge-video-bot/1.0 (personal educational channel)"}
OK_LICENSE = re.compile(r"public domain|^cc|pd", re.I)


def get_summary(topic, lang="en"):
    r = requests.get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{topic.replace(' ', '_')}",
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    d = r.json()
    if d.get("type") == "disambiguation":
        raise SystemExit(f"'{topic}' is ambiguous; use a more specific title.")
    return d["title"], d["extract"], d["content_urls"]["desktop"]["page"]


def get_images(topic, count):
    """Openly licensed images from Wikimedia Commons, with credits."""
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=HEADERS, timeout=30, params={
        "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{topic} filetype:bitmap",
        "gsrnamespace": 6, "gsrlimit": 30, "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
        "iiurlwidth": W})
    r.raise_for_status()
    out = []
    for page in r.json().get("query", {}).get("pages", {}).values():
        info = page["imageinfo"][0]
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if info["mime"] not in ("image/jpeg", "image/png") or not OK_LICENSE.search(lic):
            continue
        artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "Unknown"))
        out.append({"url": info["thumburl"], "credit": f"{artist.strip()} ({lic}) {info['descriptionurl']}"})
        if len(out) == count:
            break
    return out


def split_sentences(text, max_slides):
    s = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if len(x.strip()) > 20]
    return s[:max_slides]


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def make_slide(image_path, text, dest):
    img = Image.open(image_path).convert("RGB")
    scale = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)))
    img = img.crop(((img.width - W) // 2, (img.height - H) // 2, (img.width + W) // 2, (img.height + H) // 2))
    img = ImageEnhance.Brightness(img).enhance(0.45)
    d = ImageDraw.Draw(img)
    f = font(FONT_SIZE)
    step = FONT_SIZE + 12
    lines = textwrap.wrap(text, WRAP)
    y = H - 160 - len(lines) * step
    for ln in lines:
        d.text((60, y), ln, font=f, fill="white", stroke_width=2, stroke_fill="black")
        y += step
    img.save(dest)


def narrate(text, dest):
    try:
        from gtts import gTTS
        gTTS(text).save(str(dest))
        return True
    except Exception as e:  # gTTS missing or offline: silent video with timed captions
        print("No narration:", e)
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("topic")
    p.add_argument("--out", default="queue")
    p.add_argument("--slides", type=int, default=6)
    p.add_argument("--reel", action="store_true", help="vertical 1080x1920, max 59s (YouTube Shorts / Reels)")
    p.add_argument("--music", help="background music file you have the right to use (volume is lowered)")
    a = p.parse_args()
    global W, H, WRAP, FONT_SIZE
    if a.reel:
        W, H, WRAP, FONT_SIZE = 1080, 1920, 22, 64

    title, extract, page_url = get_summary(a.topic)
    sentences = split_sentences(extract, a.slides)
    images = get_images(a.topic, len(sentences))
    if not images:
        raise SystemExit("No openly licensed images found; try a different topic.")
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    slug = re.sub(r"\W+", "_", title.lower()).strip("_")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clips = []
        any_audio = False
        for i, sentence in enumerate(sentences):
            raw = tmp / f"raw{i}.img"
            raw.write_bytes(requests.get(images[i % len(images)]["url"], headers=HEADERS, timeout=60).content)
            slide = tmp / f"s{i}.png"
            make_slide(raw, sentence, slide)
            if i == 0:
                Image.open(slide).convert("RGB").save(out / f"{slug}.jpg")
            audio, clip = tmp / f"a{i}.mp3", tmp / f"c{i}.mp4"
            has_audio = narrate(sentence, audio)
            any_audio = any_audio or has_audio
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(slide)]
            if has_audio:
                cmd += ["-i", str(audio), "-shortest"]
            else:
                cmd += ["-t", str(max(4, len(sentence.split()) / 2.5))]
            cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24"]
            cmd += (["-c:a", "aac"] if has_audio else ["-an"]) + [str(clip)]
            subprocess.run(cmd, check=True)
            clips.append(clip)
        listing = tmp / "list.txt"
        listing.write_text("".join(f"file '{c}'\n" for c in clips))
        joined = tmp / "joined.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", str(joined)], check=True)
        final = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined)]
        if a.music:
            final += ["-stream_loop", "-1", "-i", a.music]
            if any_audio:  # keep the voice loud, music quiet underneath
                final += ["-filter_complex", "[1:a]volume=0.15[m];[0:a][m]amix=inputs=2:duration=first[a]",
                          "-map", "0:v", "-map", "[a]"]
            else:
                final += ["-map", "0:v", "-map", "1:a", "-shortest"]
            final += ["-c:v", "copy", "-c:a", "aac"]
        else:
            final += ["-c", "copy"]
        if a.reel:
            final += ["-t", "59"]
        subprocess.run(final + [str(out / f"{slug}.mp4")], check=True)

    credits = "\n".join(f"- {i['credit']}" for i in images[:len(sentences)])
    description = (f"{title}: key facts explained.{chr(10) + '#Shorts' if a.reel else ''}\n\nSource: Wikipedia - {page_url} (CC BY-SA 4.0)\n\n"
                   f"Image credits:\n{credits}")
    import json
    (out / f"{slug}.json").write_text(json.dumps(
        {"title": f"{title} Explained in 1 Minute", "description": description,
         "tags": [title, "education", "facts", "science"]}, indent=2))
    print(f"Created {out / (slug + '.mp4')} - review it, then run upload.py --queue-dir {out}")


if __name__ == "__main__":
    main()
