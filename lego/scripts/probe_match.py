#!/usr/bin/env python3
"""Decisive test: can shop products be matched to real catalog set numbers?

A price engine is only worth building if a shop listing can be tied to the
right set. This cross-matches each shop's LEGO products against the 28k set
numbers in data/catalog.json and reports the hit rate, plus examples of what
fails, so the matching rules are chosen from evidence.
"""

import json
import os
import re
import urllib.request

UA = "lego-tracker-research/1.0 (personal wishlist tool; contact via GitHub)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHOPS = [
    ("LEGO Israel (official)", "https://lego.certifiedstore.co.il", ("legoisrael", "lego store israel")),
    ("Brickland", "https://www.brickland.co.il", ("lego",)),
    ("ToysRUs IL", "https://www.toysrus.co.il", ("lego",)),
]

NUM_RE = re.compile(r"(?<!\d)(\d{3,7})(?!\d)")


def load_catalog():
    with open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8") as fh:
        cat = json.load(fh)
    # Catalog ids look like "10497-1"; shops quote the bare number.
    by_base = {}
    for r in cat["sets"]:
        by_base.setdefault(r[0].split("-")[0], r)
    return by_base


def pages(base, cap=16):
    out, n = [], 1
    while n <= cap:
        req = urllib.request.Request(f"{base}/products.json?limit=250&page={n}",
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.load(resp).get("products", [])
        if not batch:
            break
        out += batch
        n += 1
    return out


def candidates(product):
    """Numbers worth testing, best guess first: SKU, then numbers in the title."""
    seen = []
    for v in product.get("variants", []):
        sku = (v.get("sku") or "").strip()
        for m in NUM_RE.findall(sku):
            if m not in seen:
                seen.append(m)
    for m in NUM_RE.findall(product.get("title", "")):
        if m not in seen:
            seen.append(m)
    return seen


def main():
    catalog = load_catalog()
    print(f"catalog set numbers: {len(catalog):,}\n")

    for name, base, vendor_keys in SHOPS:
        print(f"=== {name}")
        try:
            products = pages(base)
        except Exception as exc:
            print(f"    failed: {exc}\n")
            continue

        lego = [p for p in products
                if any(k in (p.get("vendor") or "").lower() for k in vendor_keys)]
        print(f"    products: {len(products):,} | LEGO-vendor: {len(lego):,}")

        hits, by_sku, misses = 0, 0, []
        for p in lego:
            cands = candidates(p)
            hit = next((c for c in cands if c in catalog), None)
            if hit:
                hits += 1
                skus = [v.get("sku") or "" for v in p.get("variants", [])]
                if any(hit in s for s in skus):
                    by_sku += 1
            elif len(misses) < 6:
                misses.append((p.get("title", "")[:58], cands[:3]))

        pct = hits * 100 // max(len(lego), 1)
        print(f"    matched to a real set: {hits:,} / {len(lego):,}  ({pct}%)")
        print(f"    of those, SKU was the match: {by_sku:,}")
        if misses:
            print("    unmatched examples:")
            for title, cands in misses:
                print(f"      - {title!r} -> tried {cands}")

        matched = [p for p in lego if any(c in catalog for c in candidates(p))]
        print("    matched examples:")
        for p in matched[:4]:
            num = next(c for c in candidates(p) if c in catalog)
            row = catalog[num]
            v = (p.get("variants") or [{}])[0]
            print(f"      - {num}: shop {p.get('title','')[:34]!r} ₪{v.get('price')} "
                  f"| catalog {row[1][:34]!r} {row[2]} {row[4]}p")
        print()


if __name__ == "__main__":
    main()
