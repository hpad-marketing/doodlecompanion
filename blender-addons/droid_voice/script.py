"""Sitcom script parsing and per-engine tag conversion.

Format:   NAME: line text [laugh] more text
          [action lines in brackets are stage directions, not spoken]
          (beat) on its own line = a pause marker
Tags performed by engines that can: [laugh] [chuckle] [sigh] [cough] [gasp]
[groan] [yawn] [sniff]. Other engines drop them."""
import re

TAGS = ("laugh", "chuckle", "sigh", "cough", "gasp", "groan", "yawn", "sniff", "clear throat")
_TAG_RE = re.compile(r"\[(%s)s?\]" % "|".join(TAGS), re.I)
_PAREN = {"laugh": "(laughs)", "chuckle": "(chuckles)", "sigh": "(sighs)", "cough": "(coughs)",
          "gasp": "(gasps)", "groan": "(groans)", "yawn": "(yawns)", "sniff": "(sniffs)",
          "clear throat": "(clears throat)"}
_ANGLE = {"laugh": "<laugh>", "chuckle": "<chuckle>", "sigh": "<sigh>", "cough": "<cough>", "gasp": "<gasp>",
          "groan": "<groan>", "yawn": "<yawn>", "sniff": "<sniffle>", "clear throat": "<cough>"}
_SQUARE = {"laugh": "[laugh]", "chuckle": "[chuckle]", "sigh": "[sigh]", "cough": "[cough]", "gasp": "[gasp]",
           "groan": "[groan]", "yawn": "[sigh]", "sniff": "[sniff]", "clear throat": "[cough]"}


def convert_tags(text, style):
    def sub(m):
        t = m.group(1).lower()
        return {"paren": _PAREN, "angle": _ANGLE, "square": _SQUARE}.get(style, {}).get(t, "")
    return re.sub(r"\s{2,}", " ", _TAG_RE.sub(sub, text)).strip()


def spoken(text):
    """Text with every tag removed (for captions and silent cadence)."""
    return convert_tags(text, "strip")


def parse(script):
    """-> list of {"kind": "line"|"action"|"beat", "who", "text"} in order."""
    out = []
    for raw in script.splitlines():
        s = raw.strip()
        if not s:
            continue
        if re.fullmatch(r"\(beat\)|\(pause\)", s, re.I):
            out.append({"kind": "beat"})
            continue
        if s.startswith("[") and s.endswith("]") and not _TAG_RE.fullmatch(s):
            out.append({"kind": "action", "text": s[1:-1].strip()})
            continue
        m = re.match(r"^([A-Za-z0-9][\w' .\-]{0,40}?)\s*:\s*(.+)$", s)
        if m:
            out.append({"kind": "line", "who": m.group(1).strip(), "text": m.group(2).strip()})
        elif out and out[-1]["kind"] == "line":
            out[-1]["text"] += " " + s     # wrapped line continues
    return out
