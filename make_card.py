"""Write today's Network Governance Prep card and send it to Telegram as an image.

Runs inside GitHub Actions. Needs these repository secrets:
  ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Optional repository variable: CARD_MODEL (Claude model id).
"""
import datetime
import html
import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent
CARDS = ROOT / "cards"
MODEL = os.environ.get("CARD_MODEL") or "claude-sonnet-4-5"

# Deliberately anonymous: no people or employer names, so none can leak into a card.
CONTEXT = """The reader will soon start a Manager Network Governance role at a large telecom infrastructure company in Indonesia (part of a listed state-owned telecom group). Their manager wants a unified governance framework spanning IT, network and cybersecurity (COBIT 2019 for IT, TM Forum for network, cybersecurity reference still open, e.g. NIST CSF 2.0 / ISO 27001), and a "COBIT-like" governance model for the network. Autonomous networks will be one use case the governance covers. Studying GRC and ISACA's CGEIT is recommended, and resistance to the framework is expected. The reader is an experienced CCIE network engineer with a Master's in Data Science and AI research experience. Be technically precise on networking and AI, but define governance jargon plainly."""

RULES = """Research the topic with web search (2-5 searches). Prefer primary sources: isaca.org, tmforum.org, nist.gov, iso.org, etsi.org, 3gpp.org, official Indonesian government/regulator sites and official operator newsrooms. Never invent control IDs, clause numbers, percentages, autonomy-level definitions, operator claims or regulation numbers; if you cannot confirm one, leave it out.
For the "Autonomous Networks" track: anchor on TM Forum's Autonomous Networks work (levels L0-L5, framework, maturity assessment), and where useful ETSI ZSM, 3GPP SA5 autonomy levels, NIST AI RMF and ISO/IEC 42001. Always connect to governance: decision rights and accountability for automated changes, guardrails and human approval thresholds, risk and assurance, audit evidence, maturity measurement, and how it fits a unified IT/network/cyber framework. Report only operator initiatives you confirmed in a reputable source.
PRIVACY: never name the reader, their manager, colleagues or their employer. Say "you", "your manager", "your organisation" or "the unified framework" instead.
{previous}
Reply with ONLY a JSON object, no other text, with these keys:
  "title": punchy, at most 8 words
  "concept": the core idea in plain English, 60-90 words
  "terms": array of 3-5 short key terms (each at most 4 words)
  "why": why it matters for this role and the unified-framework vision, 30-50 words
  "question": one reflection question tied to the reader's real work, at most 30 words
  "source_label": short name of the single best source you actually opened
  "source_url": its full URL
  "verified": true only if the key facts were confirmed on a primary source you read; otherwise false
Plain text only inside the JSON values: no citation tags, no markdown, no emoji. English, plain and direct."""

# Safety net: names that must never appear in a card.
BLOCKED = ["Mas Yoga", "Yoga", "Telkom Infra", "TIF", "Telkom CorpU", "CorpU"]


def clean(s):
    s = re.sub(r"[<(]\s*/?\s*cite\b[^>]*>", "", str(s))  # citation tags
    s = re.sub(r"</?[a-zA-Z][^>]*>", "", s)  # any other tags
    for name in BLOCKED:
        s = re.sub(rf"\b{re.escape(name)}\b", "your organisation" if name in ("Telkom Infra", "TIF") else "your manager" if "Yoga" in name else "", s)
    return re.sub(r"\s+", " ", s).strip()


def call_claude(prompt):
    body = {
        "model": MODEL,
        "max_tokens": 4000,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.load(r)
    text = "".join(b.get("text", "") for b in data["content"] if b["type"] == "text")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        sys.exit("No JSON in model reply:\n" + text)
    c = json.loads(text[start : end + 1])
    for k in ("title", "concept", "why", "question", "source_label"):
        c[k] = clean(c.get(k, ""))
    c["terms"] = [clean(t) for t in c.get("terms", [])]
    c["source_url"] = str(c.get("source_url", "")).strip()
    return c


def render_png(card, path):
    """Draw the card as a phone-friendly image. Returns True on success."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    e = html.escape
    terms = "".join(f"<span class='chip'>{e(t)}</span>" for t in card["terms"])
    page_html = f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0}}
body{{width:1080px;background:#eef1f4;font-family:Inter,Arial,sans-serif;color:#1c2430}}
.card{{margin:0;background:#f7f8fa;border-left:22px solid #1f5f8b;padding:70px 80px 60px;position:relative;overflow:hidden}}
.blob{{position:absolute;right:-120px;top:-120px;width:380px;height:380px;border-radius:50%;background:#dce8f1}}
.top{{display:flex;justify-content:space-between;align-items:center;position:relative}}
.track{{background:#1f5f8b;color:#fff;font-weight:600;font-size:28px;padding:10px 26px;border-radius:40px}}
.day{{font-weight:600;letter-spacing:3px;color:#5b6675;font-size:26px}}
h1{{font-size:68px;line-height:1.08;font-weight:800;margin:56px 0 34px;position:relative}}
.concept{{font-size:33px;line-height:1.5;color:#2b3442}}
.label{{font-size:24px;letter-spacing:3px;font-weight:700;color:#1f5f8b;margin:44px 0 16px}}
.chips{{display:flex;flex-wrap:wrap;gap:14px}}
.chip{{background:#e3ebf2;color:#1c3d57;font-size:27px;font-weight:600;padding:10px 22px;border-radius:12px}}
.why{{font-size:30px;line-height:1.5;color:#2b3442}}
.q{{border-left:8px solid #1f5f8b;padding:6px 0 6px 30px;font-size:33px;font-weight:600;line-height:1.4;margin-top:48px}}
.foot{{display:flex;justify-content:space-between;margin-top:56px;font-size:22px;color:#7a8594}}
</style></head><body><div class="card"><div class="blob"></div>
<div class="top"><span class="track">{e(card['track'])}</span><span class="day">DAY {card['day']} · {e(card['dow'].upper())}</span></div>
<h1>{e(card['title'])}</h1>
<p class="concept">{e(card['concept'])}</p>
<div class="label">KEY TERMS</div><div class="chips">{terms}</div>
<div class="label">WHY IT MATTERS</div><p class="why">{e(card['why'])}</p>
<div class="q">{e(card['question'])}</div>
<div class="foot"><span>{e(card['source_label'])}{' · checked' if card['verified'] else ' · verify before quoting'}</span><span>{e(card['date_label'])}</span></div>
</div></body></html>"""
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
            pg.set_content(page_html, wait_until="networkidle")
            pg.locator(".card").screenshot(path=str(path))
            b.close()
        return True
    except Exception as ex:  # fall back to text
        print("Image rendering failed:", ex)
        return False


def tg(method, fields, files=None):
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{method}"
    if files:
        boundary = uuid.uuid4().hex
        body = b""
        for k, v in fields.items():
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        for k, (name, data) in files.items():
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{name}\"\r\n"
                     "Content-Type: image/png\r\n\r\n").encode() + data + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode())
    with urllib.request.urlopen(req, timeout=60) as r:
        if json.load(r).get("ok") is not True:
            sys.exit("Telegram refused the message")


def as_text(c):
    return (
        f"Network Governance Prep — Day {c['day']} · {c['date_label']}\nTrack: {c['track']}\n\n"
        f"{c['title']}\n\nTHE IDEA\n{c['concept']}\n\nKEY TERMS\n{' · '.join(c['terms'])}\n\n"
        f"WHY IT MATTERS\n{c['why']}\n\nTHINK ABOUT\n{c['question']}\n\n"
        f"Source: {c['source_label']} — {c['source_url']}\n"
        + ("Checked against source" if c["verified"] else "Summary — verify before quoting") + "\n"
    )


def send(c, png):
    chat = os.environ["TELEGRAM_CHAT_ID"]
    if png.exists():
        caption = f"{c['title']}\nSource: {c['source_url']}"
        tg("sendPhoto", {"chat_id": chat, "caption": caption[:1000]}, {"photo": (png.name, png.read_bytes())})
    else:
        tg("sendMessage", {"chat_id": chat, "text": as_text(c), "disable_web_page_preview": "true"})


def main():
    now = datetime.datetime.now(ZoneInfo("Asia/Jakarta"))
    today = os.environ.get("CARD_DATE") or now.strftime("%Y-%m-%d")
    slots = json.loads((ROOT / "plan.json").read_text())["slots"]
    match = [(i + 1, s) for i, s in enumerate(slots) if s["date"] == today]
    if not match:
        print(f"No card scheduled for {today}.")
        return
    day, slot = match[0]
    CARDS.mkdir(exist_ok=True)
    saved, png = CARDS / f"{today}.json", CARDS / f"{today}.png"

    if saved.exists():
        print(f"{saved.name} already exists; sending it again.")
        c = json.loads(saved.read_text())
    else:
        titles = [json.loads(p.read_text())["title"] for p in sorted(CARDS.glob("*.json"))[-5:]]
        previous = ("Recent card titles (do not repeat them): " + "; ".join(titles)) if titles else ""
        prompt = (
            f"Write today's bite-size study card.\n\nCONTEXT\n{CONTEXT}\n\n"
            f"TODAY'S TOPIC (track: {slot['track']})\n{slot['topic']}\n\n"
            + RULES.format(previous=previous)
        )
        c = call_claude(prompt)
        d = datetime.date.fromisoformat(today)
        c.update(day=day, track=slot["track"], date=today, dow=d.strftime("%a"),
                 date_label=f"{d.strftime('%a')} {d.day} {d.strftime('%b')} {d.year}",
                 verified=c.get("verified") is True)
        saved.write_text(json.dumps(c, indent=2, ensure_ascii=False))
        (CARDS / f"{today}.txt").write_text(as_text(c))

    if not png.exists():
        render_png(c, png)
    send(c, png)
    print(f"Sent: {c['title']}")


if __name__ == "__main__":
    main()
