# YouTube uploader with trending hashtags

Fetches the hashtags/tags used by today's most popular videos in your region and
adds them to the upload's description and tags.

## One-time setup
1. In Google Cloud Console create a project, enable **YouTube Data API v3**.
2. Create an **OAuth client ID** of type *Desktop app*, download it as
   `youtube_uploader/client_secret.json`.
3. `pip install -r youtube_uploader/requirements.txt`
4. First run opens a browser to sign in to Google. The token is cached in
   `token.json`. Your password is never seen by this script.

## Use
```
python youtube_uploader/upload.py --trending-only --region IN
python youtube_uploader/upload.py my.mp4 --title "My video" --description "Hello" --region IN --dry-run
python youtube_uploader/upload.py my.mp4 --title "My video" --description "Hello" --privacy public
```
Options: `--publish-at` (schedule), `--thumbnail`, `--category`, `--num-hashtags`.

## Daily knowledge videos
Put finished videos in a folder (e.g. `queue/`). Optionally add `<name>.json` next to each one
(`{"title": "...", "description": "...", "tags": ["science"]}`) and `<name>.jpg` as thumbnail.
Each run uploads the oldest video as category *Education* with today's trending hashtags,
then moves it to `queue/uploaded/`:
```
python youtube_uploader/upload.py --queue-dir queue --region IN --privacy public
```
Run it every day at 6 PM with cron (`crontab -e`):
```
0 18 * * * cd /path/to/test123 && python3 youtube_uploader/upload.py --queue-dir queue --region IN --privacy public >> upload.log 2>&1
```
Or batch-schedule several videos ahead using `--publish-at`.

## Notes
- Default privacy is `private`; pass `--privacy public` when ready.
- Unverified API projects have uploads locked to private until you pass Google's
  API audit. Daily quota is 10,000 units; one upload costs about 1,600.
- Run it on your own machine, since it needs your browser sign-in and your video file.
- Trending tags are popular, not necessarily relevant. Review them with `--dry-run`.
