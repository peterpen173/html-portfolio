#!/usr/bin/env python3
"""Probe candidate price sources for a public, read-only product API.

Research tool, not part of the app. For each candidate shop it asks whether a
documented public endpoint exists — Shopify's products.json, the WooCommerce
Store API, the WordPress REST API — so the price engine can be built on
published interfaces rather than on scraping rendered HTML.

robots.txt is fetched first and honoured: a path the site disallows is not
requested at all.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser as robotparser

UA = "lego-tracker-research/1.0 (personal wishlist tool; contact via GitHub)"
TIMEOUT = 20

CANDIDATES = [
    # Israeli shops
    "https://lego.certifiedstore.co.il",   # official LEGO Israel online store
    "https://www.brickland.co.il",
    "https://www.steimatzky.co.il",
    "https://ksp.co.il",
    "https://www.toysrus.co.il",
    "https://www.bug.co.il",
    "https://www.lastprice.co.il",
    # International, ship to Israel
    "https://www.lego.com",
    "https://www.brickowl.com",
]

# Path, what a hit would mean.
PROBES = [
    ("/products.json?limit=3", "Shopify public product feed"),
    ("/wp-json/wc/store/v1/products?per_page=3&search=lego", "WooCommerce Store API"),
    ("/wp-json/wp/v2/product?per_page=3&search=lego", "WordPress REST API"),
]


def fetch(url, want_json=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read(400_000)
        ctype = resp.headers.get("Content-Type", "")
        if want_json:
            return resp.status, ctype, json.loads(body.decode("utf-8", "replace"))
        return resp.status, ctype, body.decode("utf-8", "replace")


def robots_for(base):
    rp = robotparser.RobotFileParser()
    rp.set_url(base + "/robots.txt")
    try:
        rp.read()
        return rp
    except Exception as exc:
        print(f"    robots.txt unreadable ({exc}); treating every path as disallowed")
        return None


def describe(payload):
    """Summarise a JSON payload without dumping someone's catalog into the log."""
    if isinstance(payload, dict):
        for key in ("products", "items", "data"):
            if isinstance(payload.get(key), list):
                return f"{len(payload[key])} items under '{key}'"
        return f"object with keys {list(payload)[:6]}"
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict):
            return f"{len(payload)} items, first keys {list(payload[0])[:8]}"
        return f"list of {len(payload)}"
    return type(payload).__name__


def probe(base):
    print(f"\n=== {base}")
    rp = robots_for(base)
    if rp is None:
        return

    try:
        status, ctype, _ = fetch(base + "/", want_json=False)
        print(f"    reachable: HTTP {status} ({ctype.split(';')[0]})")
    except Exception as exc:
        print(f"    unreachable: {exc}")
        return

    for path, label in PROBES:
        url = base + path
        if not rp.can_fetch(UA, url):
            print(f"    [skip] {label}: disallowed by robots.txt")
            continue
        try:
            status, ctype, payload = fetch(url)
            if "json" not in ctype:
                print(f"    [no]   {label}: HTTP {status} but {ctype.split(';')[0]}")
                continue
            print(f"    [YES]  {label}: HTTP {status} — {describe(payload)}")
        except urllib.error.HTTPError as exc:
            print(f"    [no]   {label}: HTTP {exc.code}")
        except Exception as exc:
            print(f"    [no]   {label}: {type(exc).__name__}: {exc}")


def main():
    print("Probing candidate price sources. Read-only, robots.txt honoured.\n")
    for base in CANDIDATES:
        try:
            probe(base)
        except Exception as exc:
            print(f"    probe crashed: {exc}", file=sys.stderr)
    print("\nDone.")


if __name__ == "__main__":
    main()
