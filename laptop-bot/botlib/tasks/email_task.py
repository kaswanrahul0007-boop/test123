import email
import imaplib
import os
import smtplib
from email.header import decode_header, make_header
from email.message import EmailMessage
from botlib.tasks import task


def _unread(t, limit=25):
    m = imaplib.IMAP4_SSL(t["imap_host"])
    m.login(t["user"], os.environ[t["password_env"]])
    m.select("INBOX", readonly=True)  # readonly: bot never marks mail as read
    _, ids = m.search(None, "UNSEEN")
    items = []
    for i in ids[0].split()[-limit:]:
        _, data = m.fetch(i, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
        msg = email.message_from_bytes(data[0][1])
        items.append((str(make_header(decode_header(msg.get("From", "")))),
                      str(make_header(decode_header(msg.get("Subject", ""))))))
    m.logout()
    return items


def send_mail(cfg, to, subject, body):
    t = cfg["tasks"]["email"]
    if cfg["dry_run"]:
        return f"[dry-run] would email {to}: {subject}"
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = t["user"], to, subject
    msg.set_content(body)
    with smtplib.SMTP_SSL(t["smtp_host"], 465) as s:
        s.login(t["user"], os.environ[t["password_env"]])
        s.send_message(msg)
    return f"emailed {to}: {subject}"


@task("email_digest")
def email_digest(cfg):
    t = cfg["tasks"]["email"]
    items = _unread(t)
    body = "\n".join(f"- {s}  (from {f})" for f, s in items) or "No unread mail."
    return f"email_digest: {len(items)} unread\n" + send_mail(cfg, t["digest_to"], "Daily inbox digest", body)
