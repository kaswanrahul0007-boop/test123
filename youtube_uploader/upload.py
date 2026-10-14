"""Upload a video to YouTube with today's trending hashtags.

Setup: see README.md. Usage:
    python upload.py video.mp4 --title "My title" --description "About" --region IN
    python upload.py --trending-only --region US
"""
import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]
HERE = Path(__file__).parent
HASHTAG_RE = re.compile(r"#(\w{2,30})", re.UNICODE)


def get_service():
    token, secret = HERE / "token.json", HERE / "client_secret.json"
    creds = Credentials.from_authorized_user_file(token, SCOPES) if token.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(secret, SCOPES).run_local_server(port=0)
        token.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def trending_hashtags(yt, region, category=None, limit=10):
    """Most frequent tags/hashtags among today's most popular videos (1 quota unit)."""
    params = dict(part="snippet", chart="mostPopular", regionCode=region, maxResults=50)
    if category:
        params["videoCategoryId"] = category
    counts = Counter()
    for item in yt.videos().list(**params).execute().get("items", []):
        sn = item["snippet"]
        found = set(HASHTAG_RE.findall(sn["title"] + " " + sn.get("description", "")))
        found |= {t.replace(" ", "") for t in sn.get("tags", []) if len(t) < 30}
        counts.update(t.lower() for t in found if t)
    return [t for t, _ in counts.most_common(limit)]


def next_from_queue(args):
    """Pick the oldest video in the queue; read title/description from <name>.json if present
    ({"title": ..., "description": ..., "tags": [...]}), else use the file name as the title."""
    videos = sorted((f for f in Path(args.queue_dir).iterdir()
                     if f.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}),
                    key=lambda f: f.stat().st_mtime)
    if not videos:
        print("Queue is empty, nothing to upload today.")
        return False
    video = videos[0]
    meta_file = video.with_suffix(".json")
    meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    args.video = str(video)
    args.title = meta.get("title") or video.stem.replace("_", " ").replace("-", " ").title()
    args.description = meta.get("description", args.description)
    args.tags = meta.get("tags", args.tags)
    thumb = next((str(t) for t in (video.with_suffix(".jpg"), video.with_suffix(".png")) if t.exists()), None)
    args.thumbnail = args.thumbnail or thumb
    return True


def trending_songs(yt, region, limit=10):
    """Today's most popular music videos (category 10) - pick one in the Shorts/Reels sound library."""
    items = yt.videos().list(part="snippet", chart="mostPopular", regionCode=region,
                             videoCategoryId="10", maxResults=limit).execute().get("items", [])
    return [f"{i['snippet']['title']} - https://youtu.be/{i['id']}" for i in items]


def upload(yt, args, hashtags):
    # First 3 hashtags in the description show above the title on YouTube.
    description = f"{args.description}\n\n" + " ".join(f"#{t}" for t in hashtags)
    body = {
        "snippet": {"title": args.title[:100], "description": description,
                    "tags": hashtags + args.tags, "categoryId": args.category},
        "status": {"privacyStatus": args.privacy, "selfDeclaredMadeForKids": False},
    }
    if args.publish_at:
        body["status"].update(privacyStatus="private", publishAt=args.publish_at)
    media = MediaFileUpload(args.video, chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")
    vid = resp["id"]
    if args.thumbnail:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(args.thumbnail)).execute()
    print(f"Done: https://youtu.be/{vid} ({body['status']['privacyStatus']})")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("video", nargs="?")
    p.add_argument("--title", default="")
    p.add_argument("--description", default="")
    p.add_argument("--tags", nargs="*", default=[], help="extra tags")
    p.add_argument("--region", default="US", help="ISO country code for trends")
    p.add_argument("--category", default="27", help="YouTube category id (27=Education)")
    p.add_argument("--queue-dir", help="daily mode: upload the oldest video in this folder, then move it to uploaded/")
    p.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    p.add_argument("--publish-at", help="RFC3339 time, e.g. 2026-10-15T18:00:00Z")
    p.add_argument("--thumbnail")
    p.add_argument("--num-hashtags", type=int, default=8)
    p.add_argument("--trending-songs", action="store_true", help="list today's trending music and exit")
    p.add_argument("--trending-only", action="store_true", help="print trends and exit")
    p.add_argument("--dry-run", action="store_true", help="show metadata, don't upload")
    args = p.parse_args()

    yt = get_service()
    if args.trending_songs:
        print("\n".join(trending_songs(yt, args.region)))
        return
    hashtags = trending_hashtags(yt, args.region, limit=args.num_hashtags)
    print("Trending hashtags:", " ".join(f"#{t}" for t in hashtags))
    if args.trending_only:
        return
    if args.queue_dir:
        if not next_from_queue(args):
            return
    if not args.video or not args.title:
        sys.exit("video path and --title are required")
    if args.dry_run:
        print("Dry run: nothing uploaded.")
        return
    upload(yt, args, hashtags)
    if args.queue_dir:
        done = Path(args.queue_dir) / "uploaded"
        done.mkdir(exist_ok=True)
        for f in Path(args.video).parent.glob(Path(args.video).stem + ".*"):
            shutil.move(str(f), done / f.name)


if __name__ == "__main__":
    main()
