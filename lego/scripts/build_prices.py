#!/usr/bin/env python3
"""Build an Israeli price index for LEGO sets.

Reads the public Shopify product feeds of Israeli shops, ties each listing to
a catalog set number, and writes data/prices.json keyed by set number with the
offers sorted cheapest first.

Matching is the delicate part. A shop SKU is often the set number, but not
always: one shop's SKU field held "200", which matches a real 1985 catalog
entry and would price a 2026 set as a 2-piece 1985 booklet. So every candidate
number is scored, and a listing with no confident match is dropped rather than
guessed.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

UA = "lego-tracker/1.0 (personal wishlist tool; contact via GitHub)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

THIS_YEAR = datetime.now(timezone.utc).year

SHOPS = [
    {"id": "legoil", "name": "לגו ישראל (רשמי)",
     "base": "https://lego.certifiedstore.co.il", "vendors": ("legoisrael", "lego store israel")},
    {"id": "brickland", "name": "Brickland",
     "base": "https://www.brickland.co.il", "vendors": ("lego",)},
    {"id": "toysrus", "name": "ToysRUs ישראל",
     "base": "https://www.toysrus.co.il", "vendors": ("lego",)},
    # Shilav does not put LEGO in the vendor field, so the whole record is
    # searched instead; the scored match still decides what is really a set.
    {"id": "shilav", "name": "שילב",
     "base": "https://www.shilav.com", "vendors": ("lego", "לגו"), "match": "any"},
]

# Shops that cannot be indexed, and why. Shown in the app so a price is never
# presented as the cheapest anywhere when whole retailers are missing from it.
NOT_COVERED = [
    {"name": "KSP", "reason": "חוסמת קריאה אוטומטית (403)",
     "search": "https://ksp.co.il/web/cat/?search=lego+{num}"},
    {"name": "אייבורי", "reason": "robots.txt אוסר סריקה",
     "search": "https://www.ivory.co.il/catalog?search=lego+{num}"},
    {"name": "לאסט פרייס", "reason": "חוסמת קריאה אוטומטית (403)",
     "search": "https://www.lastprice.co.il/search?q=lego+{num}"},
    {"name": "זאפ", "reason": "אין פיד מוצרים ציבורי",
     "search": "https://www.zap.co.il/search.aspx?keyword=lego+{num}"},
]

# Modern LEGO set numbers are 4-7 digits. Three-digit numbers exist only in the
# 1950s-80s catalog and collide with SKUs, piece counts and ages, so they are
# never trusted from a shop feed.
NUM_RE = re.compile(r"(?<!\d)(\d{4,7})(?!\d)")

MIN_SCORE = 5


def fetch_page(base, n):
    req = urllib.request.Request(f"{base}/products.json?limit=250&page={n}",
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.load(resp).get("products", [])


def fetch_shop(shop, max_pages=40):
    """Some shops start erroring past a certain page; keep whatever arrived."""
    products, n = [], 1
    while n <= max_pages:
        try:
            batch = fetch_page(shop["base"], n)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            print(f"    stopped at page {n}: {exc}")
            break
        if not batch:
            break
        products += batch
        n += 1
    return products


def load_catalog():
    with open(os.path.join(DATA, "catalog.json"), encoding="utf-8") as fh:
        cat = json.load(fh)
    by_base = {}
    for r in cat["sets"]:
        by_base.setdefault(r[0].split("-")[0], r)
    return cat, by_base


def score(num, row, in_sku, in_title):
    """How much to trust `num` as this listing's set number."""
    s = 0
    if in_sku and in_title:
        s += 10                      # both fields agree — near certain
    elif in_title:
        s += 4                       # titles carry the real number more reliably
    elif in_sku:
        s += 3
    if len(num) >= 5:
        s += 3                       # 5+ digits is unambiguous in practice
    year = row[2]
    if year >= THIS_YEAR - 12:
        s += 4                       # a shop stocks current sets
    elif year >= 2000:
        s += 1
    else:
        s -= 6                       # a 1980s match on a shop shelf is a collision
    if row[4] == 0:
        s -= 3                       # 0-piece catalog rows are books and gear
    return s


def best_match(product, catalog):
    skus = " ".join((v.get("sku") or "") for v in product.get("variants", []))
    title = product.get("title", "")
    sku_nums = set(NUM_RE.findall(skus))
    title_nums = set(NUM_RE.findall(title))

    best, best_s = None, 0
    for num in sku_nums | title_nums:
        row = catalog.get(num)
        if not row:
            continue
        s = score(num, row, num in sku_nums, num in title_nums)
        if s > best_s:
            best, best_s = num, s
    return (best, best_s) if best_s >= MIN_SCORE else (None, best_s)


def offers_from(shop, products, catalog):
    out, matched, skipped = {}, 0, 0
    for p in products:
        if shop.get("match") == "any":
            haystack = " ".join([p.get("vendor") or "", p.get("title") or "",
                                 p.get("product_type") or ""]).lower()
        else:
            haystack = (p.get("vendor") or "").lower()
        if not any(k in haystack for k in shop["vendors"]):
            continue
        num, _ = best_match(p, catalog)
        if not num:
            skipped += 1
            continue
        variants = p.get("variants") or [{}]
        prices = [(float(v["price"]), bool(v.get("available")))
                  for v in variants if v.get("price") not in (None, "")]
        if not prices:
            continue
        prices.sort()
        price, available = prices[0]
        if price <= 0:
            continue
        matched += 1
        offer = {
            "shop": shop["id"],
            "shop_name": shop["name"],
            "title": p.get("title", "")[:120],
            "price": round(price, 2),
            "in_stock": available,
            "url": f"{shop['base']}/products/{p.get('handle','')}",
        }
        # Keep the cheaper listing when a shop lists the same set twice.
        prev = out.get(num)
        if not prev or offer["price"] < prev["price"]:
            out[num] = offer
    print(f"    matched {matched}, unmatched {skipped}")
    return out


def main():
    cat, catalog = load_catalog()
    print(f"catalog: {len(catalog):,} set numbers\n")

    prices = {}
    shops_meta = []
    for shop in SHOPS:
        print(f"=== {shop['name']}")
        products = fetch_shop(shop)
        print(f"    products: {len(products):,}")
        found = offers_from(shop, products, catalog)
        for num, offer in found.items():
            prices.setdefault(num, []).append(offer)
        if found:
            shops_meta.append({"id": shop["id"], "name": shop["name"],
                               "base": shop["base"], "sets": len(found)})
        else:
            print("    no sets matched — left out of the covered list")
        print()

    for num in prices:
        prices[num].sort(key=lambda o: (not o["in_stock"], o["price"]))

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "currency": "ILS",
        "note": "מחיר המוצר בחנות, כולל מע\"מ, לפני דמי משלוח",
        "shops": shops_meta,
        "not_covered": NOT_COVERED,
        "prices": prices,
    }
    path = os.path.join(DATA, "prices.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    total = sum(len(v) for v in prices.values())
    print(f"wrote {path}: {len(prices):,} sets, {total:,} offers "
          f"({os.path.getsize(path)/1e6:.2f} MB)")

    print("\nspot check — five sets with more than one shop:")
    multi = [(k, v) for k, v in prices.items() if len(v) > 1][:5]
    for num, offers in multi:
        row = catalog[num]
        print(f"  {num} {row[1][:38]!r} ({row[2]}, {row[4]}p)")
        for o in offers:
            print(f"     ₪{o['price']:>8.2f}  {o['shop_name']}  "
                  f"{'במלאי' if o['in_stock'] else 'אזל'}")
    if not multi:
        print("  none — worth investigating before trusting the index")


if __name__ == "__main__":
    main()
