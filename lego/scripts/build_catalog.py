#!/usr/bin/env python3
"""Build the full LEGO catalog from Rebrickable's public CSV dumps.

Produces lego/data/catalog.json (compact, array-of-arrays) and
lego/data/new_sets.json (sets that appeared since the previous run).

Runs on GitHub Actions, which has unrestricted outbound network access.
No API key is required: the CSV dumps below are public downloads.
"""

import csv
import gzip
import io
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timezone

CDN = "https://cdn.rebrickable.com/media/downloads/"
SETS_URL = CDN + "sets.csv.gz"
THEMES_URL = CDN + "themes.csv.gz"
RATE_URL = "https://api.frankfurter.app/latest?from=USD&to=ILS"

IMG_BASE = "https://cdn.rebrickable.com/media/sets/"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CATALOG_PATH = os.path.join(DATA, "catalog.json")
NEW_SETS_PATH = os.path.join(DATA, "new_sets.json")

# How many days a newly-discovered set stays in new_sets.json.
NEW_SET_RETENTION_DAYS = 60


def fetch_csv(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lego-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = gzip.decompress(resp.read())
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))


def fetch_usd_ils():
    """Rate is used only for the tax estimator in the UI; a failure is not fatal."""
    try:
        req = urllib.request.Request(RATE_URL, headers={"User-Agent": "lego-tracker/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return round(float(json.load(resp)["rates"]["ILS"]), 4)
    except Exception as exc:
        print(f"warning: could not fetch USD/ILS rate ({exc})", file=sys.stderr)
        return None


def theme_paths(theme_rows):
    """Resolve each theme id to its full path, e.g. 'Star Wars > Ultimate Collector Series'."""
    by_id = {r["id"]: r for r in theme_rows}
    paths = {}

    def resolve(tid, seen):
        if tid in paths:
            return paths[tid]
        row = by_id.get(tid)
        if row is None or tid in seen:
            return ""
        parent = row.get("parent_id") or ""
        if parent and parent in by_id:
            prefix = resolve(parent, seen | {tid})
            path = f"{prefix} > {row['name']}" if prefix else row["name"]
        else:
            path = row["name"]
        paths[tid] = path
        return path

    for tid in by_id:
        resolve(tid, set())
    return paths


def shorten_img(url):
    """Store only the filename when the image sits on the known CDN path."""
    if url and url.startswith(IMG_BASE):
        return url[len(IMG_BASE):]
    return url or ""


def load_previous():
    if not os.path.exists(CATALOG_PATH):
        return set()
    with open(CATALOG_PATH, encoding="utf-8") as fh:
        return {row[0] for row in json.load(fh).get("sets", [])}


def load_new_sets():
    if not os.path.exists(NEW_SETS_PATH):
        return []
    with open(NEW_SETS_PATH, encoding="utf-8") as fh:
        return json.load(fh).get("sets", [])


def main():
    os.makedirs(DATA, exist_ok=True)

    print("downloading themes...")
    themes = theme_paths(fetch_csv(THEMES_URL))
    print(f"  {len(themes)} themes")

    print("downloading sets...")
    set_rows = fetch_csv(SETS_URL)
    print(f"  {len(set_rows)} sets")

    previous = load_previous()
    first_run = not previous

    rows = []
    for r in set_rows:
        rows.append([
            r["set_num"],
            r["name"],
            int(r["year"]) if r["year"] else 0,
            r["theme_id"],
            int(r["num_parts"]) if r["num_parts"] else 0,
            shorten_img(r.get("img_url", "")),
        ])

    # Newest first, then largest first: the sets worth deciding on come up early.
    rows.sort(key=lambda x: (-x[2], -x[4], x[0]))

    catalog = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Rebrickable public CSV downloads",
        "usd_ils": fetch_usd_ils(),
        "img_base": IMG_BASE,
        "cols": ["num", "name", "year", "theme_id", "parts", "img"],
        "themes": {tid: path for tid, path in themes.items()},
        "sets": rows,
    }

    with open(CATALOG_PATH, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {CATALOG_PATH} ({os.path.getsize(CATALOG_PATH) / 1e6:.1f} MB)")

    # Anything not in the previous catalog is a new arrival. On the very first
    # run every set is "new", which is meaningless, so we skip detection then.
    today = date.today().isoformat()
    added = [] if first_run else [r for r in rows if r[0] not in previous]
    print(f"{len(added)} newly discovered sets")

    kept = [s for s in load_new_sets()
            if (date.today() - date.fromisoformat(s["found"])).days <= NEW_SET_RETENTION_DAYS]
    known = {s["num"] for s in kept}
    for r in added:
        if r[0] in known:
            continue
        kept.append({
            "found": today,
            "num": r[0],
            "name": r[1],
            "year": r[2],
            "theme": themes.get(r[3], "Unknown"),
            "parts": r[4],
            "img": (IMG_BASE + r[5]) if r[5] and not r[5].startswith("http") else r[5],
        })

    kept.sort(key=lambda s: (s["found"], s["num"]), reverse=True)
    with open(NEW_SETS_PATH, "w", encoding="utf-8") as fh:
        json.dump({"generated": catalog["generated"], "sets": kept}, fh,
                  ensure_ascii=False, indent=1)
    print(f"wrote {NEW_SETS_PATH} ({len(kept)} entries)")

    # Consumed by the workflow to decide whether to send a notification.
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"new_count={len(added)}\n")


if __name__ == "__main__":
    main()
