#!/usr/bin/env python3
"""
Joyun Telegram Delivery
Sends 3 things to the team chat:
  1. Text summary
  2. Today's CSV
  3. Today's HTML dashboard
"""

import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DASHBOARD_PATH = ROOT / "dashboard.html"

IST = timezone(timedelta(hours=5, minutes=30))
TODAY = datetime.now(IST).strftime("%Y-%m-%d")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_text(text: str) -> None:
    r = requests.post(
        f"{API}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"},
        timeout=30,
    )
    r.raise_for_status()
    print("Sent text summary")


def send_document(path: Path, caption: str = "") -> None:
    with path.open("rb") as f:
        r = requests.post(
            f"{API}/sendDocument",
            data={"chat_id": CHAT_ID, "caption": caption},
            files={"document": (path.name, f)},
            timeout=60,
        )
    r.raise_for_status()
    print(f"Sent document: {path.name}")


def build_summary(findings: dict) -> str:
    stats = findings.get("stats", {})
    alert = findings.get("alert")

    parts = [
        f"*Joyun Daily Intel — {TODAY}*",
        "",
        findings.get("summary", "_No summary available._"),
        "",
        f"📊 Tracked: *{stats.get('items_tracked', 0)}* | "
        f"🔶 High: *{stats.get('high_threat', 0)}* | "
        f"🟡 Med: *{stats.get('medium_threat', 0)}* | "
        f"🟢 Low: *{stats.get('low_threat', 0)}* | "
        f"🟣 Adj: *{stats.get('adjacent', 0)}*",
    ]

    if alert:
        parts += ["", f"⚠️ *Alert:* {alert}"]

    # Top 3 opportunities
    opps = findings.get("opportunities", [])[:3]
    if opps:
        parts += ["", "*Top opportunities:*"]
        for o in opps:
            parts.append(f"• {o['opportunity']} → _{o['suggested_action']}_")

    parts += ["", "📎 CSV + dashboard attached below."]
    return "\n".join(parts)


def main() -> None:
    findings_path = DATA_DIR / f"findings_{TODAY}.json"
    csv_path = DATA_DIR / f"joyun_intel_{TODAY}.csv"

    if not findings_path.exists():
        raise SystemExit(f"Missing {findings_path} — run_intel.py must run first.")

    findings = json.loads(findings_path.read_text(encoding="utf-8"))

    send_text(build_summary(findings))
    send_document(csv_path, caption=f"Joyun intel CSV — {TODAY}")
    send_document(DASHBOARD_PATH, caption=f"Joyun dashboard — {TODAY}")
    print("✅ Telegram delivery complete.")


if __name__ == "__main__":
    main()
