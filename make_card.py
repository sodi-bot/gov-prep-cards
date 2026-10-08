"""Write today's Network Governance Prep card and send it to Telegram.

Runs inside GitHub Actions. Needs these repository secrets:
  ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Optional repository variable: CARD_MODEL (Claude model id).
"""
import datetime
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent
MODEL = os.environ.get("CARD_MODEL") or "claude-sonnet-4-5"

CONTEXT = """The reader is moving (around 1 Nov 2026) into a Manager Network Governance role at Telkom Infra (TIF), reporting to the SM Network & IT Governance (Mas Yoga), with a peer who is Mgr Cybersecurity Governance. Mas Yoga wants a unified governance framework spanning IT, network and cybersecurity (COBIT 2019 for IT, TM Forum for network, cybersecurity reference still open, e.g. NIST CSF 2.0 / ISO 27001), and a "COBIT-like" model for network. Autonomous networks will be one use case the governance covers. He advised studying GRC and ISACA's CGEIT, and expects resistance. The reader is an active CCIE (Enterprise Infrastructure) with years of hands-on network engineering, a Master's in Data Science and AI research experience, currently in L&D at Telkom CorpU. Be technically precise on networking and AI, but define governance jargon plainly."""

RULES = """Research the topic with web search (2-5 searches). Prefer primary sources: isaca.org, tmforum.org, nist.gov, iso.org, etsi.org, 3gpp.org, official Indonesian government/regulator sites (jdih, komdigi.go.id, ojk.go.id, bumn.go.id) and official Telkom Group / operator newsrooms. Never invent control IDs, clause numbers, percentages, autonomy-level definitions, operator claims or regulation numbers; if you cannot confirm one, leave it out.
For the "Autonomous Networks" track: anchor on TM Forum's Autonomous Networks work (levels L0-L5, framework, maturity assessment), and where useful ETSI ZSM, 3GPP SA5 autonomy levels, NIST AI RMF and ISO/IEC 42001. Always connect to governance questions: decision rights and accountability for automated changes, guardrails and human approval thresholds, risk and assurance, audit evidence, maturity measurement, and how it fits Mas Yoga's unified IT/network/cyber framework. Report only operator initiatives (including Telkom Group / Telkomsel / TIF) you confirmed in a reputable source.
{previous}
Reply with ONLY a JSON object, no other text, with these keys:
  "title": punchy, at most 8 words
  "concept": the core idea in plain English, 70-110 words
  "terms": array of 3-6 short key terms
  "why": why it matters for this role and the unified-framework vision, 40-60 words
  "question": one reflection question tied to the reader's real work at TIF, at most 40 words
  "source_label": name of the single best source you actually opened
  "source_url": its full URL
  "verified": true only if the key facts were confirmed on a primary source you read; otherwise false
English, plain and direct, no emoji."""


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
    return json.loads(text[start : end + 1])


def send_telegram(text):
    data = urllib.parse.urlencode({
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": text,
        "disable_web_page_preview": "true",
    }).encode()
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    with urllib.request.urlopen(url, data=data, timeout=60) as r:
        if json.load(r).get("ok") is not True:
            sys.exit("Telegram refused the message")


def main():
    now = datetime.datetime.now(ZoneInfo("Asia/Jakarta"))
    today = os.environ.get("CARD_DATE") or now.strftime("%Y-%m-%d")
    slots = json.loads((ROOT / "plan.json").read_text())["slots"]
    match = [(i + 1, s) for i, s in enumerate(slots) if s["date"] == today]
    if not match:
        print(f"No card scheduled for {today}.")
        return
    day, slot = match[0]

    out = ROOT / "cards" / f"{today}.txt"
    if out.exists():
        print(f"{out.name} already exists; sending it again.")
        send_telegram(out.read_text())
        return

    done = sorted((ROOT / "cards").glob("*.txt"))[-5:]
    titles = [p.read_text().split("\n")[3] for p in done if len(p.read_text().split("\n")) > 3]
    previous = ("Recent card titles (avoid repeating them): " + "; ".join(titles)) if titles else ""

    prompt = (
        f"Write today's bite-size study card.\n\nCONTEXT\n{CONTEXT}\n\n"
        f"TODAY'S TOPIC (track: {slot['track']})\n{slot['topic']}\n\n"
        + RULES.format(previous=previous)
    )
    c = call_claude(prompt)

    d = datetime.date.fromisoformat(today)
    text = (
        f"Network Governance Prep — Day {day} · {d.strftime('%a')} {d.day} {d.strftime('%b')}\n"
        f"Track: {slot['track']}\n\n"
        f"{c['title']}\n\n"
        f"THE IDEA\n{c['concept']}\n\n"
        f"KEY TERMS\n{' · '.join(c['terms'])}\n\n"
        f"WHY IT MATTERS\n{c['why']}\n\n"
        f"THINK ABOUT\n{c['question']}\n\n"
        f"Source: {c['source_label']} — {c['source_url']}\n"
        + ("Checked against source" if c.get("verified") is True else "Summary — verify before quoting")
        + "\n"
    )
    out.parent.mkdir(exist_ok=True)
    out.write_text(text)
    send_telegram(text)
    print(f"Sent: {c['title']}")


if __name__ == "__main__":
    main()
