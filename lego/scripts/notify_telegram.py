#!/usr/bin/env python3
"""Send a Telegram message for sets discovered on today's run.

Optional. Runs only when TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set as
repository secrets; without them the workflow skips this step entirely.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_SETS_PATH = os.path.join(ROOT, "data", "new_sets.json")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SITE = os.environ.get("SITE_URL", "")


def api(method, payload):
    data = urllib.parse.urlencode(payload).encode()
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as resp:
        return json.load(resp)


def main():
    if not TOKEN or not CHAT_ID:
        print("Telegram not configured, skipping")
        return

    with open(NEW_SETS_PATH, encoding="utf-8") as fh:
        sets = json.load(fh)["sets"]

    today = date.today().isoformat()
    fresh = [s for s in sets if s["found"] == today]
    if not fresh:
        print("nothing new today")
        return

    for s in fresh[:20]:
        caption = (
            f"<b>סט לגו חדש בקטלוג</b>\n\n"
            f"{s['name']}\n"
            f"מספר סט: <code>{s['num']}</code>\n"
            f"שנה: {s['year']}\n"
            f"סדרה: {s['theme']}\n"
            f"חלקים: {s['parts']:,}"
        )
        if SITE:
            caption += f"\n\n<a href=\"{SITE}#new\">לסימון כן/לא</a>"
        try:
            if s.get("img"):
                api("sendPhoto", {"chat_id": CHAT_ID, "photo": s["img"],
                                  "caption": caption, "parse_mode": "HTML"})
            else:
                api("sendMessage", {"chat_id": CHAT_ID, "text": caption,
                                    "parse_mode": "HTML"})
        except Exception as exc:
            print(f"failed to notify for {s['num']}: {exc}", file=sys.stderr)

    if len(fresh) > 20:
        api("sendMessage", {"chat_id": CHAT_ID,
                            "text": f"ועוד {len(fresh) - 20} סטים חדשים ברשימה."})
    print(f"notified about {len(fresh)} sets")


if __name__ == "__main__":
    main()
