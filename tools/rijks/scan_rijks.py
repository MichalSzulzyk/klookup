#!/usr/bin/env python3
import argparse
import csv
import re
import time
import warnings
from collections import defaultdict
from pathlib import Path

import requests

warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

BASE_URL = "https://data.rijksmuseum.nl"

# SEARCHES = [
#     {"name": "posters", "params": {"type": "poster", "imageAvailable": "true"}},
#     {"name": "lithografie", "params": {"type": "print", "technique": "lithografie", "imageAvailable": "true"}},
#     {"name": "zeefdruk", "params": {"type": "print", "technique": "zeefdruk", "imageAvailable": "true"}},
#     {"name": "compositie", "params": {"title": "compositie", "imageAvailable": "true"}},
#     {"name": "kleur", "params": {"description": "kleur", "imageAvailable": "true"}},
# ]

SEARCHES = [
    # Grafika / projektowanie — najlepsze tropy pod zegar
    {"name": "posters", "params": {"type": "poster", "imageAvailable": "true"}},
    {"name": "lithografie", "params": {"type": "print", "technique": "lithografie", "imageAvailable": "true"}},
    {"name": "zeefdruk", "params": {"type": "print", "technique": "zeefdruk", "imageAvailable": "true"}},
    {"name": "compositie", "params": {"title": "compositie", "imageAvailable": "true"}},
    {"name": "kleur", "params": {"description": "kleur", "imageAvailable": "true"}},

    # Dodatkowe duże kategorie do testów
    {"name": "paintings", "params": {"type": "painting", "imageAvailable": "true"}},
    {"name": "prints_all", "params": {"type": "print", "imageAvailable": "true"}},
    {"name": "pastels", "params": {"type": "pastel", "imageAvailable": "true"}},
]

PERIODS = {
    # XXI wiek / najnowsze rzeczy
    "2000s": ["200?", "201?", "202?"],

    # W miarę współcześni artyści, ale jeszcze nie za szeroko
    "recent": ["199?", "200?", "201?", "202?"],

    # Bardziej współczesny zakres: lata 80. do dziś
    "contemporary": ["198?", "199?", "200?", "201?", "202?"],

    # Powojenny modernizm + współczesność
    "postwar": ["195?", "196?", "197?", "198?", "199?", "200?", "201?", "202?"],

    # Cały XX wiek
    "modern": ["190?", "191?", "192?", "193?", "194?", "195?", "196?", "197?", "198?", "199?"],
}

BAD_NAMES = ["anonymous", "anoniem", "unknown", "onbekend", "maker onbekend"]
ROLE_WORDS = [
    "designer", "ontwerper",
    "printmaker", "prentmaker",
    "artist", "kunstenaar",
    "painter", "schilder",
    "draughtsman", "tekenaar"
]


def fetch_json(url, params=None):
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def is_open_license(obj):
    text = str(obj).lower()
    return (
        "creativecommons.org/publicdomain/zero/1.0" in text
        or "public domain" in text
    )


def clean_name(text):
    if not text:
        return ""

    text = text.strip()

    if ":" in text:
        text = text.split(":", 1)[1].strip()

    text = re.sub(r"\s*\(.*?\)", "", text).strip()
    text = re.sub(r",\s*(Amsterdam|Rotterdam|Den Haag|Utrecht).*", "", text).strip()

    return text


def is_bad_name(name):
    n = clean_name(name).lower()
    return not n or any(bad in n for bad in BAD_NAMES)


def get_title(obj):
    for item in obj.get("identified_by", []):
        if item.get("type") == "Name" and item.get("content"):
            return item["content"]
    return ""


def get_year(obj):
    produced_by = obj.get("produced_by", {})
    timespan = produced_by.get("timespan", {})

    # Rijksmuseum czasem zwraca timespan jako dict, a czasem jako listę.
    if isinstance(timespan, list):
        timespans = timespan
    else:
        timespans = [timespan]

    for ts in timespans:
        if not isinstance(ts, dict):
            continue

        for item in ts.get("identified_by", []):
            if isinstance(item, dict) and item.get("content"):
                return item["content"]

        begin = ts.get("begin_of_the_begin", "")
        if begin:
            return begin[:4]

    return ""


def get_visual_item_id(obj):
    shows = obj.get("shows", [])
    if shows and shows[0].get("id"):
        return shows[0]["id"]
    return ""


def get_notation_values(entity):
    values = []

    notation = entity.get("notation", [])

    if isinstance(notation, str):
        values.append(notation)
    elif isinstance(notation, list):
        for item in notation:
            if isinstance(item, dict):
                val = item.get("@value")
                if val:
                    values.append(val)
            elif isinstance(item, str):
                values.append(item)

    return values


def extract_names_from_production(prod):
    names = []

    for person in prod.get("carried_out_by", []):
        if isinstance(person, dict):
            names.extend(get_notation_values(person))

    for assignment in prod.get("assigned_by", []):
        if not isinstance(assignment, dict):
            continue

        for assigned in assignment.get("assigned", []):
            if isinstance(assigned, dict):
                names.extend(get_notation_values(assigned))

    for ref in prod.get("referred_to_by", []):
        if not isinstance(ref, dict):
            continue

        content = ref.get("content", "")
        low = content.lower()

        if any(role in low for role in ROLE_WORDS):
            names.append(content)

    return names


def extract_artist(obj):
    produced_by = obj.get("produced_by", {})
    candidates = []

    candidates.extend(extract_names_from_production(produced_by))

    for part in produced_by.get("part", []):
        role_text = str(part.get("technique", [])).lower()
        ref_text = str(part.get("referred_to_by", [])).lower()

        if any(role in role_text or role in ref_text for role in ROLE_WORDS):
            candidates.extend(extract_names_from_production(part))

    cleaned = []

    for c in candidates:
        name = clean_name(c)
        if name and not is_bad_name(name):
            cleaned.append(name)

    unique = []

    for name in cleaned:
        if name not in unique:
            unique.append(name)

    if unique:
        return unique[0]

    return ""

def should_continue_scanning(page, max_pages):
    if str(max_pages).lower() == "all":
        return True

    return page <= int(max_pages)

def search_object_ids(search, decade, max_pages):
    params = dict(search["params"])
    params["creationDate"] = decade
    initial_params = dict(params)

    url = f"{BASE_URL}/search/collection"
    page = 1
    ids = []
    pages_scanned = 0
    total_items = 0

    print(f"\n=== {search['name']} | creationDate={decade} ===", flush=True)

    while should_continue_scanning(page, max_pages):
        data = fetch_json(url, params=params if page == 1 else None)
        ordered = data.get("orderedItems", [])
        total = data.get("partOf", {}).get("totalItems", 0)

        if isinstance(total, int):
            total_items = total

        pages_scanned += 1

        print(f"page {page}: {len(ordered)} items, totalItems={total}", flush=True)

        for item in ordered:
            object_id = item.get("id")
            if object_id:
                ids.append(object_id)

        next_url = data.get("next", {}).get("id")
        if not next_url:
            break

        url = next_url
        params = None
        page += 1
        time.sleep(0.2)

    summary = {
        "search_name": search["name"],
        "creation_date": decade,
        "query": "&".join([f"{k}={v}" for k, v in initial_params.items()]),
        "total_items": total_items,
        "pages_scanned": pages_scanned,
        "objects_seen": len(ids),
    }

    return ids, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="2000s", choices=PERIODS.keys())
    parser.add_argument(
    "--max-pages",
    default="1",
    help="Number of result pages to scan per query, or 'all' to scan every available page."
)
    parser.add_argument("--min-artist-items", type=int, default=3)
    args = parser.parse_args()

    export_dir = Path("data/rijks/export")
    export_dir.mkdir(parents=True, exist_ok=True)

    print("Rijksmuseum artist scanner", flush=True)
    print(f"period: {args.period}", flush=True)
    print(f"max pages per query: {args.max_pages}", flush=True)
    print(f"min artist items: {args.min_artist_items}", flush=True)

    seen = set()
    rows = []
    search_summaries = []
    valid_by_search = defaultdict(int)
    artists_by_search = defaultdict(set)

    for decade in PERIODS[args.period]:
        for search in SEARCHES:
            object_ids, search_summary = search_object_ids(search, decade, args.max_pages)
            search_summaries.append(search_summary)

            for object_id in object_ids:
                if object_id in seen:
                    continue

                seen.add(object_id)

                try:
                    obj = fetch_json(object_id)
                except Exception as e:
                    print(f"  ! error: {object_id} | {e}", flush=True)
                    continue

                if not is_open_license(obj):
                    continue

                artist = extract_artist(obj)

                if not artist or is_bad_name(artist):
                    continue

                title = get_title(obj)
                year = get_year(obj)
                visual_item_id = get_visual_item_id(obj)

                row = {
                    "artist": artist,
                    "title": title,
                    "year": year,
                    "object_id": object_id,
                    "visual_item_id": visual_item_id,
                    "source_query": search["name"],
                    "decade_query": decade,
                }

                rows.append(row)

                valid_by_search[search["name"]] += 1
                artists_by_search[search["name"]].add(artist)

                print(f"  + {artist} | {year} | {title}", flush=True)
                time.sleep(0.1)

    by_artist = defaultdict(list)

    for row in rows:
        by_artist[row["artist"]].append(row)

    candidates_path = export_dir / "candidates.csv"
    artists_path = export_dir / "artists_summary.csv"
    category_summary_path = export_dir / "category_summary.csv"

    with candidates_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["artist", "title", "year", "object_id", "visual_item_id", "source_query", "decade_query"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with artists_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["artist", "count"])
        writer.writeheader()

        for artist, items in sorted(by_artist.items(), key=lambda x: len(x[1]), reverse=True):
            writer.writerow({"artist": artist, "count": len(items)})

    category_totals = {}

    for item in search_summaries:
        name = item["search_name"]

        if name not in category_totals:
            category_totals[name] = {
                "search_name": name,
                "creation_dates": set(),
                "total_items_sum": 0,
                "pages_scanned": 0,
                "objects_seen": 0,
            }

        category_totals[name]["creation_dates"].add(item["creation_date"])
        category_totals[name]["total_items_sum"] += int(item.get("total_items") or 0)
        category_totals[name]["pages_scanned"] += int(item.get("pages_scanned") or 0)
        category_totals[name]["objects_seen"] += int(item.get("objects_seen") or 0)

    with category_summary_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "search_name",
            "creation_dates",
            "total_items_sum",
            "pages_scanned",
            "objects_seen",
            "valid_objects",
            "artists_found",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for name, item in sorted(category_totals.items(), key=lambda x: x[0]):
            writer.writerow({
                "search_name": name,
                "creation_dates": " ".join(sorted(item["creation_dates"])),
                "total_items_sum": item["total_items_sum"],
                "pages_scanned": item["pages_scanned"],
                "objects_seen": item["objects_seen"],
                "valid_objects": valid_by_search.get(name, 0),
                "artists_found": len(artists_by_search.get(name, set())),
            })

    print("\n=== SUMMARY ===", flush=True)
    print(f"objects scanned: {len(seen)}", flush=True)
    print(f"valid objects: {len(rows)}", flush=True)
    print(f"artists found: {len(by_artist)}", flush=True)

    strong = {a: i for a, i in by_artist.items() if len(i) >= args.min_artist_items}
    print(f"artists with >= {args.min_artist_items} items: {len(strong)}", flush=True)

    print("\nTop artists:", flush=True)

    for artist, items in sorted(by_artist.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
        mark = "✅" if len(items) >= args.min_artist_items else "  "
        print(f"{mark} {artist}: {len(items)}", flush=True)

    print("\nSaved:", flush=True)
    print(f"  {candidates_path}", flush=True)
    print(f"  {artists_path}", flush=True)
    print(f"  {category_summary_path}", flush=True)


if __name__ == "__main__":
    main()