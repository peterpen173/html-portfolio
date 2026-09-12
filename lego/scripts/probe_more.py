#!/usr/bin/env python3
"""Can more Israeli shops be added to the price index?

KSP refused the first probe, and a price index that silently omits a big
retailer is worse than no index. This checks a wider list: what robots.txt
allows, whether a public product feed exists, and whether the shop answers a
normal browser request at all.

robots.txt is authoritative here. A path it disallows is not requested, and a
shop that blocks automated reads is reported as unavailable rather than worked
around.
"""

import json
import urllib.error
import urllib.request
import urllib.robotparser as robotparser

# Identifies the tool. Some WAFs reject any non-browser agent; where that
# happens the shop is reported as blocked, not retried under a disguise.
UA = ("Mozilla/5.0 (compatible; lego-tracker/1.0; personal wishlist tool; "
      "+https://github.com/peterpen173/html-portfolio)")

SHOPS = [
    "https://ksp.co.il",
    "https://www.ivory.co.il",
    "https://www.bug.co.il",
    "https://www.lastprice.co.il",
    "https://www.zap.co.il",
    "https://www.hamashbir365.com",
    "https://www.shilav.com",
    "https://www.mega-toys.co.il",
]

PROBES = [
    ("/products.json?limit=3", "Shopify feed"),
    ("/wp-json/wc/store/v1/products?per_page=3&search=lego", "WooCommerce Store API"),
    ("/sitemap.xml", "sitemap"),
]


def get(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/json,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read(200_000)


def main():
    for base in SHOPS:
        print(f"\n=== {base}")

        rp = robotparser.RobotFileParser()
        rp.set_url(base + "/robots.txt")
        try:
            rp.read()
            robots_ok = True
        except Exception as exc:
            print(f"    robots.txt unreadable ({exc}) — treating as disallowed, skipping")
            continue

        try:
            status, ctype, _ = get(base + "/")
            print(f"    homepage: HTTP {status} ({ctype.split(';')[0]})")
        except urllib.error.HTTPError as exc:
            print(f"    homepage: HTTP {exc.code} — blocks automated reads, cannot include")
            continue
        except Exception as exc:
            print(f"    homepage: {type(exc).__name__}: {exc}")
            continue

        for path, label in PROBES:
            url = base + path
            if robots_ok and not rp.can_fetch(UA, url):
                print(f"    [skip] {label}: disallowed by robots.txt")
                continue
            try:
                status, ctype, body = get(url)
                if "json" in ctype:
                    try:
                        data = json.loads(body)
                        n = len(data.get("products", [])) if isinstance(data, dict) else len(data)
                        print(f"    [YES]  {label}: HTTP {status}, {n} items")
                        continue
                    except Exception:
                        pass
                print(f"    [no]   {label}: HTTP {status} ({ctype.split(';')[0]}, {len(body)}b)")
            except urllib.error.HTTPError as exc:
                print(f"    [no]   {label}: HTTP {exc.code}")
            except Exception as exc:
                print(f"    [no]   {label}: {type(exc).__name__}")


if __name__ == "__main__":
    main()
