#!/usr/bin/env python3

import argparse
import csv
import html
import time
import warnings
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import requests

warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

DEFAULT_CANDIDATES = Path("data/rijks/export/candidates.csv")
DEFAULT_GALLERY_DIR = Path("data/rijks/gallery")
DEFAULT_EXCLUDE_ARTISTS = Path("data/rijks/export/exclude_artists.txt")
DEFAULT_EXCLUDE_OBJECTS = Path("data/rijks/export/exclude_objects.txt")


def fetch_json(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def read_exclude_file(path):
    if not path.exists():
        return set()

    values = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        values.add(line.lower())

    return values


def artist_slug(name):
    safe = "".join(
        c.lower() if c.isalnum() else "-"
        for c in name.strip()
    )
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-") or "unknown"


def get_digital_object_id(visual_item_id):
    if not visual_item_id:
        return ""

    try:
        data = fetch_json(visual_item_id)
    except Exception as error:
        print(f"  ! visual item error: {visual_item_id} | {error}", flush=True)
        return ""

    shown_by = data.get("digitally_shown_by", [])

    if shown_by and shown_by[0].get("id"):
        return shown_by[0]["id"]

    return ""


def get_iiif_id_from_digital_object(digital_object_id):
    if not digital_object_id:
        return ""

    try:
        data = fetch_json(digital_object_id)
    except Exception as error:
        print(f"  ! digital object error: {digital_object_id} | {error}", flush=True)
        return ""

    access_points = data.get("access_point", [])

    for access_point in access_points:
        url = access_point.get("id", "")
        marker = "iiif.micr.io/"

        if marker in url:
            after = url.split(marker, 1)[1]
            iiif_id = after.split("/", 1)[0]
            return iiif_id

    return ""


def build_preview_urls(iiif_id, preview_width):
    if not iiif_id:
        return "", ""

    preview_url = f"https://iiif.micr.io/{iiif_id}/full/{preview_width},/0/default.jpg"
    full_url = f"https://iiif.micr.io/{iiif_id}/full/max/0/default.jpg"

    return preview_url, full_url


def load_candidates(path, exclude_artists, exclude_objects, min_artist_items):
    rows = []

    with path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            artist = row.get("artist", "").strip()
            object_id = row.get("object_id", "").strip()

            if not artist or not object_id:
                continue

            if artist.lower() in exclude_artists:
                continue

            if object_id.lower() in exclude_objects:
                continue

            rows.append(row)

    grouped = defaultdict(list)

    for row in rows:
        grouped[row["artist"]].append(row)

    if min_artist_items > 1:
        grouped = {
            artist: items
            for artist, items in grouped.items()
            if len(items) >= min_artist_items
        }

    return dict(sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True))


def enrich_with_images(grouped, preview_width, max_per_artist=None):
    enriched = {}

    for artist, items in grouped.items():
        print(f"\n=== {artist} ({len(items)} works) ===", flush=True)

        enriched_items = []

        for index, row in enumerate(items, start=1):
            if max_per_artist and index > max_per_artist:
                break

            visual_item_id = row.get("visual_item_id", "")

            print(f"  [{index}/{len(items)}] {row.get('title', '')}", flush=True)

            digital_object_id = get_digital_object_id(visual_item_id)
            iiif_id = get_iiif_id_from_digital_object(digital_object_id)
            preview_url, full_url = build_preview_urls(iiif_id, preview_width)

            new_row = dict(row)
            new_row["digital_object_id"] = digital_object_id
            new_row["iiif_id"] = iiif_id
            new_row["preview_url"] = preview_url
            new_row["full_url"] = full_url

            enriched_items.append(new_row)

            time.sleep(0.12)

        enriched[artist] = enriched_items

    return enriched


def write_enriched_csv(enriched, output_path):
    rows = []

    for artist, items in enriched.items():
        rows.extend(items)

    fieldnames = [
        "artist",
        "title",
        "year",
        "object_id",
        "visual_item_id",
        "digital_object_id",
        "iiif_id",
        "preview_url",
        "full_url",
        "source_query",
        "decade_query",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def make_html(enriched, output_path, min_artist_items):
    artist_nav = []

    for artist, items in enriched.items():
        slug = artist_slug(artist)
        artist_nav.append(
            f'<a href="#{html.escape(slug)}">{html.escape(artist)} <span>{len(items)}</span></a>'
        )

    sections = []

    for artist, items in enriched.items():
        slug = artist_slug(artist)
        cards = []

        for row in items:
            artist_text = html.escape(row.get("artist", ""))
            title = html.escape(row.get("title", ""))
            year = html.escape(row.get("year", ""))
            object_id = row.get("object_id", "")
            visual_item_id = row.get("visual_item_id", "")
            preview_url = row.get("preview_url", "")
            full_url = row.get("full_url", "")

            object_link = html.escape(object_id)
            api_link = html.escape(object_id)
            image_link = html.escape(full_url or preview_url)

            if preview_url:
                image_html = f'<a href="{image_link}" target="_blank"><img loading="lazy" src="{html.escape(preview_url)}" alt="{title}"></a>'
            else:
                image_html = '<div class="missing">No preview</div>'

            cards.append(
                f"""
                <article class="card">
                    <div class="thumb">
                        {image_html}
                    </div>
                    <div class="meta">
                        <h3>{title}</h3>
                        <p class="year">{year}</p>
                        <p class="artist">{artist_text}</p>
                        <div class="links">
                            <a href="{object_link}" target="_blank">Object JSON</a>
                            <a href="{html.escape(visual_item_id)}" target="_blank">VisualItem</a>
                            <a href="{image_link}" target="_blank">Image</a>
                        </div>
                        <code>{html.escape(object_id)}</code>
                    </div>
                </article>
                """
            )

        sections.append(
            f"""
            <section id="{html.escape(slug)}" class="artist-section">
                <h2>{html.escape(artist)} <span>{len(items)} works</span></h2>
                <div class="grid">
                    {''.join(cards)}
                </div>
            </section>
            """
        )

    html_text = f"""<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <title>Rijksmuseum candidates gallery</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {{
            --bg: #111;
            --panel: #1b1b1b;
            --panel2: #242424;
            --text: #f0f0f0;
            --muted: #aaa;
            --line: #333;
            --accent: #d6b46a;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            line-height: 1.45;
        }}

        header {{
            padding: 28px 32px;
            border-bottom: 1px solid var(--line);
            background: #151515;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        h1 {{
            margin: 0 0 8px 0;
            font-size: 28px;
        }}

        .sub {{
            color: var(--muted);
            margin: 0;
        }}

        nav {{
            padding: 16px 32px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            border-bottom: 1px solid var(--line);
            background: #131313;
        }}

        nav a {{
            color: var(--text);
            text-decoration: none;
            background: var(--panel);
            border: 1px solid var(--line);
            padding: 8px 10px;
            border-radius: 999px;
            font-size: 13px;
        }}

        nav a span {{
            color: var(--accent);
        }}

        main {{
            padding: 24px 32px 80px;
        }}

        .artist-section {{
            margin-bottom: 52px;
        }}

        h2 {{
            margin: 0 0 18px 0;
            font-size: 24px;
            border-bottom: 1px solid var(--line);
            padding-bottom: 10px;
        }}

        h2 span {{
            color: var(--muted);
            font-weight: normal;
            font-size: 15px;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 16px;
        }}

        .card {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 14px;
            overflow: hidden;
        }}

        .thumb {{
            background: #0b0b0b;
            min-height: 220px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .thumb img {{
            max-width: 100%;
            width: 100%;
            height: 260px;
            object-fit: contain;
            display: block;
            background: #0b0b0b;
        }}

        .missing {{
            color: var(--muted);
            padding: 40px;
        }}

        .meta {{
            padding: 12px;
        }}

        .meta h3 {{
            margin: 0 0 6px 0;
            font-size: 15px;
        }}

        .year, .artist {{
            margin: 0 0 4px 0;
            color: var(--muted);
            font-size: 13px;
        }}

        .links {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }}

        .links a {{
            color: var(--accent);
            text-decoration: none;
            font-size: 12px;
        }}

        code {{
            display: block;
            margin-top: 10px;
            color: #888;
            font-size: 10px;
            overflow-wrap: anywhere;
        }}

        .note {{
            margin-top: 14px;
            color: var(--muted);
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <header>
        <h1>Rijksmuseum candidates gallery</h1>
        <p class="sub">Grouped by artist. Minimum {min_artist_items} works per artist. Preview images loaded through IIIF/Micrio.</p>
        <p class="note">To hide artists or works, add names to <code>data/rijks/export/exclude_artists.txt</code> or object IDs to <code>data/rijks/export/exclude_objects.txt</code>, then regenerate.</p>
    </header>

    <nav>
        {''.join(artist_nav)}
    </nav>

    <main>
        {''.join(sections)}
    </main>
</body>
</html>
"""

    output_path.write_text(html_text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--output-dir", default=str(DEFAULT_GALLERY_DIR))
    parser.add_argument("--preview-width", type=int, default=700)
    parser.add_argument("--min-artist-items", type=int, default=3)
    parser.add_argument("--max-per-artist", type=int, default=0)
    args = parser.parse_args()

    candidates_path = Path(args.candidates)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    exclude_artists = read_exclude_file(DEFAULT_EXCLUDE_ARTISTS)
    exclude_objects = read_exclude_file(DEFAULT_EXCLUDE_OBJECTS)

    max_per_artist = args.max_per_artist or None

    print("Rijksmuseum gallery builder", flush=True)
    print(f"candidates: {candidates_path}", flush=True)
    print(f"output dir: {output_dir}", flush=True)
    print(f"preview width: {args.preview_width}", flush=True)
    print(f"min artist items: {args.min_artist_items}", flush=True)
    print(f"max per artist: {max_per_artist or 'all'}", flush=True)

    grouped = load_candidates(
        candidates_path,
        exclude_artists=exclude_artists,
        exclude_objects=exclude_objects,
        min_artist_items=args.min_artist_items,
    )

    print(f"artists to render: {len(grouped)}", flush=True)

    enriched = enrich_with_images(
        grouped,
        preview_width=args.preview_width,
        max_per_artist=max_per_artist,
    )

    enriched_csv = output_dir / "gallery_items.csv"
    html_path = output_dir / "index.html"

    write_enriched_csv(enriched, enriched_csv)
    make_html(enriched, html_path, min_artist_items=args.min_artist_items)

    print("\nSaved:", flush=True)
    print(f"  {enriched_csv}", flush=True)
    print(f"  {html_path}", flush=True)
    print("\nOpen gallery:", flush=True)
    print(f"  open {html_path}", flush=True)


if __name__ == "__main__":
    main()
