#!/usr/bin/env python3
"""Second research pass: can the Israeli Shopify feeds be matched to set numbers?

Pulls a few pages from each shop's public products.json and reports how many
titles carry an extractable LEGO set number, what the price fields look like,
and how big each catalog is. Read-only; nothing is committed.
"""

import json
import re
import urllib.request
from collections import Counter

UA = "lego-tracker-research/1.0 (personal wishlist tool; contact via GitHub)"
SHOPS = [
    ("LEGO Israel (official)", "https://lego.certifiedstore.co.il"),
    ("Brickland", "https://www.brickland.co.il"),
    ("ToysRUs IL", "https://www.toysrus.co.il"),
]

# LEGO set numbers are 3-7 digits. Anything shorter collides with piece counts
# and ages, so require a 4+ digit run that is not part of a longer number.
SET_RE = re.compile(r"(?<!\d)(\d{4,7})(?!\d)")


def page(base, n):
    url = f"{base}/products.json?limit=250&page={n}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("products", [])


def main():
    for name, base in SHOPS:
        print(f"\n=== {name}  ({base})")
        products, n = [], 1
        try:
            while n <= 12:                      # cap the crawl at 3,000 products
                batch = page(base, n)
                if not batch:
                    break
                products += batch
                n += 1
        except Exception as exc:
            print(f"    failed after {len(products)} products: {exc}")

        print(f"    products pulled: {len(products)}")
        if not products:
            continue

        with_num, available, prices = 0, 0, []
        vendors = Counter()
        for p in products:
            vendors[(p.get("vendor") or "?")] += 1
            if SET_RE.search(p.get("title", "")):
                with_num += 1
            for v in p.get("variants", []):
                if v.get("available"):
                    available += 1
                try:
                    prices.append(float(v.get("price")))
                except (TypeError, ValueError):
                    pass

        print(f"    titles with a 4-7 digit set number: {with_num} ({with_num*100//len(products)}%)")
        print(f"    variants in stock: {available}")
        if prices:
            prices.sort()
            print(f"    price range: {prices[0]:.0f} - {prices[-1]:.0f} "
                  f"(median {prices[len(prices)//2]:.0f})")
        print(f"    top vendors: {vendors.most_common(4)}")
        print("    sample titles:")
        for p in products[:4]:
            v = (p.get("variants") or [{}])[0]
            print(f"      - {p.get('title','')[:70]!r} | {v.get('price')} | "
                  f"available={v.get('available')} | sku={v.get('sku')!r}")
        print(f"    product keys: {list(products[0])[:12]}")


if __name__ == "__main__":
    main()
