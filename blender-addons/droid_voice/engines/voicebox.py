"""Voicebox (MIT, github.com/jamiepine/voicebox) as the engine hub.

Uses its OpenAI-compatible endpoint POST /v1/audio/speech, which returns the
audio directly: model = Voicebox engine id, voice = profile name or id,
instructions = delivery note (Qwen engines). Droid profiles are created with
POST /profiles (designed voices for Qwen Voice Design, preset voices for
Kokoro, cloned-from-sample for Chatterbox)."""
import json
import urllib.error
import urllib.request

from .. import config, wavio

ID, LABEL, LICENCE = "voicebox", "Voicebox hub", "MIT (engines: Chatterbox MIT, Qwen3/Kokoro Apache-2.0)"
ENGINES = ("chatterbox_turbo", "chatterbox", "qwen", "qwen_voice_design", "qwen_custom_voice", "kokoro", "luxtts")


def _url(path):
    return config.settings()["voicebox_url"].rstrip("/") + path


def _req(method, path, body=None, timeout=10, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(_url(path), data=data, method=method,
                               headers={"Content-Type": "application/json", "X-Voicebox-Client-Id": "droid-voice"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        b = resp.read()
    return b if raw else json.loads(b or b"null")


def available():
    try:
        _req("GET", "/profiles", timeout=2)
        return True, "running"
    except Exception:
        return False, "Voicebox isn't running (open the app on this PC)"


def profiles():
    return {p["name"].lower(): p for p in _req("GET", "/profiles")}


def ensure_profile(name, engine, design_prompt=None, preset_voice=None, sample_wav=None, sample_text=None):
    """Create the droid's Voicebox profile once. Returns its id."""
    have = profiles().get(name.lower())
    if have:
        return have["id"]
    body = {"name": name, "language": "en", "default_engine": server_engine(engine),
            "description": "Droid Voice cast profile"}
    if engine == "qwen_voice_design":
        body.update(voice_type="designed", design_prompt=design_prompt or name)
    elif engine in ("kokoro", "qwen_custom_voice"):
        body.update(voice_type="preset", preset_engine=engine, preset_voice_id=preset_voice)
    else:
        body.update(voice_type="cloned")
    p = _req("POST", "/profiles", body, timeout=30)
    if body["voice_type"] == "cloned" and sample_wav:
        _upload_sample(p["id"], sample_wav, sample_text or "")
    return p["id"]


def _upload_sample(profile_id, wav_path, text):
    import uuid
    b = "----dv" + uuid.uuid4().hex
    with open(wav_path, "rb") as f:
        audio = f.read()
    parts = [
        f'--{b}\r\nContent-Disposition: form-data; name="reference_text"\r\n\r\n{text}\r\n'.encode(),
        f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="sample.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode()
        + audio + b"\r\n",
        f"--{b}--\r\n".encode(),
    ]
    r = urllib.request.Request(_url(f"/profiles/{profile_id}/samples"), data=b"".join(parts), method="POST",
                               headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    urllib.request.urlopen(r, timeout=60).read()


_API = {}


def _api():
    """What this Voicebox build offers. Builds with /v1/audio/speech take the
    OpenAI-style call; 0.5.x only has /generate (profile_id + engine enum, no
    qwen_voice_design: a 'designed' profile on the 'qwen' engine instead)."""
    url = config.settings()["voicebox_url"]
    if url in _API:
        return _API[url]
    info = {"openai": True, "engines": None, "paths": set()}
    try:
        spec = json.loads(_req("GET", "/openapi.json", timeout=5, raw=True))
        info["paths"] = set(spec.get("paths", {}))
        info["openai"] = "/v1/audio/speech" in info["paths"]
        eng = spec["components"]["schemas"]["GenerationRequest"]["properties"]["engine"]
        pat = next((a.get("pattern") for a in eng.get("anyOf", [eng]) if a.get("pattern")), None)
        if pat:
            info["engines"] = pat.strip("^$()").split("|")
    except Exception:
        pass
    _API[url] = info
    return info


def server_engine(engine):
    """Map our engine id to one this Voicebox build accepts."""
    allowed = _api()["engines"]
    if allowed and engine not in allowed and engine == "qwen_voice_design":
        return "qwen"
    return engine


def _wav_bytes(resp_bytes, ctype):
    return resp_bytes if (resp_bytes[:4] == b"RIFF" or ctype.startswith("audio")) else None


def _post_raw(path, body, timeout):
    data = json.dumps(body).encode()
    r = urllib.request.Request(_url(path), data=data, method="POST",
                               headers={"Content-Type": "application/json", "X-Voicebox-Client-Id": "droid-voice"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def _get_raw(path, timeout=60):
    r = urllib.request.Request(_url(path), headers={"X-Voicebox-Client-Id": "droid-voice"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def _generate(r, engine):
    """Voicebox 0.5.x: POST /generate/stream (audio back) or /generate + poll."""
    import time
    timeout = config.settings()["timeout_s"]
    prof = profiles().get((r.get("voice") or "").lower())
    if not prof:
        raise RuntimeError(f"Voicebox has no profile named {r.get('voice')!r}")
    body = {"profile_id": prof["id"], "text": r["text"], "language": "en",
            "engine": server_engine(r.get("engine") or engine)}
    if r.get("instruct"):
        body["instruct"] = r["instruct"][:500]
    if r.get("seed") is not None:
        body["seed"] = int(r["seed"]) % (2 ** 31)
    paths = _api()["paths"]
    if "/generate/stream" in paths:
        b, ct = _post_raw("/generate/stream", body, timeout)
        w = _wav_bytes(b, ct)
        if w:
            return w
    b, ct = _post_raw("/generate", body, timeout)
    w = _wav_bytes(b, ct)
    if w:
        return w
    g = json.loads(b)
    gid = g.get("id") or g.get("generation_id")
    t0 = time.time()
    while g.get("status") not in (None, "completed", "complete", "done", "succeeded") and time.time() - t0 < timeout:
        if g.get("status") in ("failed", "error", "cancelled"):
            raise RuntimeError(f"Voicebox generation failed: {str(g)[:300]}")
        time.sleep(0.5)
        g = _req("GET", f"/generate/{gid}/status", timeout=30)
    for p in (f"/audio/{gid}", f"/history/{gid}/audio", f"/generate/{gid}/audio", f"/history/{gid}/export-audio"):
        try:
            b, ct = _get_raw(p)
            w = _wav_bytes(b, ct)
            if w:
                return w
        except urllib.error.HTTPError:
            continue
    raise RuntimeError(f"Voicebox finished but no audio route worked for {gid}: {str(g)[:200]}")


def synth(reqs, engine="chatterbox_turbo"):
    out = []
    if not _api()["openai"]:
        for r in reqs:
            try:
                out.append(wavio.read(_generate(r, engine)))
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")
                raise RuntimeError(f"Voicebox refused the line: {msg[:300]}") from None
        return out
    for r in reqs:
        body = {"model": r.get("engine") or engine, "input": r["text"], "voice": r.get("voice"),
                "response_format": "wav", "speed": float(r.get("speed", 1.0))}
        if r.get("instruct"):
            body["instructions"] = r["instruct"]
        try:
            b = _req("POST", "/v1/audio/speech", body, timeout=config.settings()["timeout_s"], raw=True)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            raise RuntimeError(f"Voicebox refused the line: {msg[:300]}") from None
        out.append(wavio.read(b))
    return out
