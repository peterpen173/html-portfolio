#!/usr/bin/env python3
"""Can Amazon or KSP be read automatically at all?

The user asked for live Amazon US/UK/DE/FR and KSP prices. Before answering
with numbers, establish whether those sites can be read from a server at all,
so any figure quoted is one that was actually fetched.
"""

import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (compatible; lego-tracker/1.0; personal wishlist tool; "
      "+https://github.com/peterpen173/html-portfolio)")

TARGETS = [
    ("Amazon US", "https://www.amazon.com/s?k=lego+76354"),
    ("Amazon UK", "https://www.amazon.co.uk/s?k=lego+76354"),
    ("Amazon DE", "https://www.amazon.de/s?k=lego+76354"),
    ("Amazon FR", "https://www.amazon.fr/s?k=lego+76354"),
    ("KSP", "https://ksp.co.il/web/cat/?search=lego+76354"),
    ("Facebook Marketplace", "https://www.facebook.com/marketplace/search/?query=lego%2076354"),
]


def main():
    for name, url in TARGETS:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = resp.read(300_000).decode("utf-8", "replace")
            robot = any(s in body.lower() for s in
                        ("captcha", "are you a robot", "automated access",
                         "enable javascript", "log in to continue"))
            print(f"{name:<22} HTTP {resp.status}  {len(body):>7}b  "
                  f"{'blocked by a bot/login wall' if robot else 'readable HTML'}")
        except urllib.error.HTTPError as exc:
            print(f"{name:<22} HTTP {exc.code}  refused")
        except Exception as exc:
            print(f"{name:<22} {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
