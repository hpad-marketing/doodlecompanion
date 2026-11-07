"""Optional YouTube upload of an episode's publish folder.

Needs, once: `pip install google-api-python-client google-auth-oauthlib` into
Blender's Python, and an OAuth desktop client file saved as
DeepInDoodles/_youtube/client_secret.json. The first upload opens a Google
sign-in in the browser; the token is kept beside the client file.
"""
import datetime
import glob
import os

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]


def _dir(root):
    return os.path.join(root, "_youtube")


def ready(root):
    try:
        import googleapiclient  # noqa: F401
        import google_auth_oauthlib  # noqa: F401
    except ImportError:
        return False, "YouTube upload needs google-api-python-client and google-auth-oauthlib in Blender's Python"
    if not os.path.isfile(os.path.join(_dir(root), "client_secret.json")):
        return False, f"Save your Google OAuth client file as {os.path.join(_dir(root), 'client_secret.json')}"
    return True, "ready"


def _creds(root):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    tok = os.path.join(_dir(root), "token.json")
    creds = Credentials.from_authorized_user_file(tok, SCOPES) if os.path.isfile(tok) else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        creds = InstalledAppFlow.from_client_secrets_file(os.path.join(_dir(root), "client_secret.json"), SCOPES).run_local_server(port=0)
    with open(tok, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return creds


def _read(pub, name):
    p = os.path.join(pub, name)
    if not os.path.isfile(p):
        return ""
    with open(p, encoding="utf-8") as f:
        return f.read().strip()


def publish_at(schedule_ist):
    """'2026-11-10 18:00' in IST -> RFC 3339 UTC, or None."""
    s = (schedule_ist or "").strip()
    if not s:
        return None
    t = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M") - datetime.timedelta(hours=5, minutes=30)
    return t.strftime("%Y-%m-%dT%H:%M:00Z")


def upload(root, pub, privacy="private", schedule_ist=""):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    vids = [p for p in glob.glob(os.path.join(pub, "*.mp4")) if not os.path.basename(p).startswith("short_")]
    if not vids:
        return "No episode video in the publish folder yet"
    yt = build("youtube", "v3", credentials=_creds(root))
    desc = _read(pub, "description.txt")
    chapters = _read(pub, "chapters.txt")
    if chapters:
        desc += "\n\n" + chapters
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    when = publish_at(schedule_ist)
    if when:
        status.update(privacyStatus="private", publishAt=when)
    body = {"snippet": {"title": _read(pub, "title.txt")[:100], "description": desc[:5000],
                        "tags": [t.strip() for t in _read(pub, "tags.txt").split(",") if t.strip()], "categoryId": "1"},
            "status": status}
    req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(vids[0], chunksize=8 << 20, resumable=True))
    res = None
    while res is None:
        _, res = req.next_chunk()
    vid = res["id"]
    thumb = os.path.join(pub, "thumbnail.jpg")
    if os.path.isfile(thumb):
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb)).execute()
    for lang in ("en", "hi"):
        cap = os.path.join(pub, f"captions_{lang}.srt")
        if os.path.isfile(cap):
            yt.captions().insert(part="snippet", body={"snippet": {"videoId": vid, "language": lang, "name": lang.upper()}},
                                 media_body=MediaFileUpload(cap)).execute()
    return f"Uploaded: https://youtu.be/{vid}" + (f" (goes live {schedule_ist} IST)" if when else "")
