from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "site"
DIST_DIR = ROOT / "dist"
GENERATED_DIR = ROOT / "graphics_IO_minutes"
BLANK_DIR = ROOT / "graphics_blank_minutes"
TARGET_SIZE = (1920, 1080)
DEFAULT_WIDTHS = (1920,)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
TIMESTAMP_RE = re.compile(r"_(\d{12})(?=\.[^.]+$)")


@dataclass(frozen=True)
class MinuteSource:
    hhmm: str
    image_path: Path
    artist: str | None
    timestamp: str
    credit_type: str | None
    is_generated: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the static Klookup minute site.")
    parser.add_argument("--dist", type=Path, default=DIST_DIR, help="Output directory.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Build only the first N discovered minute images for quick local tests.",
    )
    parser.add_argument(
        "--fit",
        choices=("contain", "cover"),
        default="contain",
        help="Use contain to preserve the full image or cover to crop to 16:9.",
    )
    parser.add_argument(
        "--jpg-fallback",
        action="store_true",
        help="Also write JPG fallbacks. This roughly doubles build size.",
    )
    parser.add_argument(
        "--webp-quality",
        type=int,
        default=78,
        help="WebP quality from 1 to 100.",
    )
    parser.add_argument(
        "--widths",
        default=",".join(str(width) for width in DEFAULT_WIDTHS),
        help="Comma-separated WebP widths. Keep the default 1920 for the simple MVP.",
    )
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="Only refresh minutes.json and static files; keep existing image assets.",
    )
    return parser.parse_args()


def parse_widths(value: str) -> tuple[int, ...]:
    widths = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    if not widths:
        raise ValueError("At least one width is required.")
    for width in widths:
        if width <= 0:
            raise ValueError("Widths must be positive integers.")
    return tuple(widths)


def load_artists() -> dict[str, dict[str, str]]:
    artists_path = SOURCE_DIR / "artists.json"
    with artists_path.open(encoding="utf-8") as file:
        data = json.load(file)
    return {slug: values for slug, values in data.items() if isinstance(values, dict)}


def parse_hhmm(path: Path) -> str | None:
    prefix = path.stem[:4]
    if not prefix.isdigit():
        return None
    hour = int(prefix[:2])
    minute = int(prefix[2:])
    if hour > 23 or minute > 59:
        return None
    return prefix


def source_timestamp(path: Path) -> str:
    match = TIMESTAMP_RE.search(path.name)
    if match:
        return match.group(1)
    return f"{int(path.stat().st_mtime):012d}"


def infer_credit_type(path: Path) -> str:
    if TIMESTAMP_RE.search(path.name):
        return "ai_inspired"
    return "artist_made"


def prefer_newer(current: MinuteSource | None, candidate: MinuteSource) -> MinuteSource:
    if current is None:
        return candidate
    if candidate.timestamp >= current.timestamp:
        return candidate
    return current


def discover_generated() -> dict[str, MinuteSource]:
    chosen: dict[str, MinuteSource] = {}
    if not GENERATED_DIR.exists():
        return chosen

    for output_dir in sorted(GENERATED_DIR.glob("*_output")):
        artist = output_dir.name.removesuffix("_output")
        for image_path in sorted(output_dir.iterdir()):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            hhmm = parse_hhmm(image_path)
            if hhmm is None:
                continue
            source = MinuteSource(
                hhmm=hhmm,
                image_path=image_path,
                artist=artist,
                timestamp=source_timestamp(image_path),
                credit_type=infer_credit_type(image_path),
                is_generated=TIMESTAMP_RE.search(image_path.name) is not None,
            )
            chosen[hhmm] = prefer_newer(chosen.get(hhmm), source)

    return chosen


def discover_blanks(existing: dict[str, MinuteSource]) -> dict[str, MinuteSource]:
    if not BLANK_DIR.exists():
        return existing

    for image_path in sorted(BLANK_DIR.iterdir()):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        hhmm = parse_hhmm(image_path)
        if hhmm is None or hhmm in existing:
            continue
        existing[hhmm] = MinuteSource(
            hhmm=hhmm,
            image_path=image_path,
            artist=None,
            timestamp=source_timestamp(image_path),
            credit_type=None,
            is_generated=False,
        )

    return existing


def all_minutes() -> list[str]:
    return [f"{hour:02d}{minute:02d}" for hour in range(24) for minute in range(60)]


def time_label(hhmm: str) -> str:
    return f"{hhmm[:2]}:{hhmm[2:]}"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def prepare_image(
    image_path: Path,
    output_path: Path,
    output_format: str,
    fit: str,
    webp_quality: int,
    size: tuple[int, int],
) -> None:
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        if fit == "cover":
            image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
        else:
            image = ImageOps.pad(
                image,
                size,
                method=Image.Resampling.LANCZOS,
                color=(0, 0, 0),
                centering=(0.5, 0.5),
            )
        if output_format == "WEBP":
            image.save(output_path, "WEBP", quality=webp_quality, method=4)
        else:
            image.save(output_path, "JPEG", quality=84, optimize=True, progressive=True)


def copy_static_files(dist_dir: Path) -> None:
    for name in ("index.html", "styles.css", "app.js"):
        shutil.copy2(SOURCE_DIR / name, dist_dir / name)


def build_index(
    sources: dict[str, MinuteSource],
    artists: dict[str, dict[str, str]],
    dist_dir: Path,
    limit: int | None,
    fit: str,
    jpg_fallback: bool,
    webp_quality: int,
    widths: tuple[int, ...],
    write_images: bool,
) -> dict[str, Any]:
    assets_dir = dist_dir / "assets" / "minutes"
    if write_images:
        assets_dir.mkdir(parents=True, exist_ok=True)

    selected_minutes = all_minutes()
    if limit is not None:
        available = [hhmm for hhmm in selected_minutes if hhmm in sources]
        selected_minutes = available[:limit]

    records = []
    for hhmm in selected_minutes:
        source = sources.get(hhmm)
        if source is None:
            records.append(
                {
                    "hhmm": hhmm,
                    "label": time_label(hhmm),
                    "image": None,
                    "fallbackImage": None,
                    "artist": None,
                    "artistName": None,
                    "portfolioUrl": "",
                    "creditType": None,
                    "isGenerated": False,
                }
            )
            continue

        variants = []
        for width in widths:
            height = round(width * TARGET_SIZE[1] / TARGET_SIZE[0])
            webp_path = assets_dir / f"{hhmm}-{width}.webp"
            if write_images:
                prepare_image(
                    source.image_path,
                    webp_path,
                    "WEBP",
                    fit,
                    webp_quality,
                    (width, height),
                )
            variants.append(
                {
                    "width": width,
                    "height": height,
                    "src": f"assets/minutes/{hhmm}-{width}.webp",
                }
            )

        largest_variant = variants[-1]
        jpg_path = assets_dir / f"{hhmm}.jpg" if jpg_fallback else None
        if write_images and jpg_path is not None:
            prepare_image(source.image_path, jpg_path, "JPEG", fit, webp_quality, TARGET_SIZE)

        artist_data = artists.get(source.artist or "", {})
        artist_name = artist_data.get("name") or source.artist
        portfolio_url = artist_data.get("portfolio_url", "")
        records.append(
            {
                "hhmm": hhmm,
                "label": time_label(hhmm),
                "image": largest_variant["src"],
                "srcset": ", ".join(f"{variant['src']} {variant['width']}w" for variant in variants),
                "sizes": "100vw",
                "variants": variants,
                "fallbackImage": f"assets/minutes/{hhmm}.jpg" if jpg_fallback else None,
                "artist": source.artist,
                "artistName": artist_name,
                "portfolioUrl": portfolio_url,
                "creditType": source.credit_type,
                "isGenerated": source.is_generated,
            }
        )

    return {
        "generatedAt": None,
        "targetSize": list(TARGET_SIZE),
        "totalRecords": len(records),
        "availableImages": sum(1 for record in records if record["image"]),
        "minutes": records,
    }


def main() -> None:
    args = parse_args()
    widths = parse_widths(args.widths)
    dist_dir = args.dist.resolve()
    if dist_dir.exists() and not args.index_only:
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)

    artists = load_artists()
    sources = discover_blanks(discover_generated())
    missing_artists = sorted(
        {source.artist for source in sources.values() if source.artist and source.artist not in artists}
    )
    for artist in missing_artists:
        print(f"Warning: artist '{artist}' has no matching entry in site/artists.json.")
    index = build_index(
        sources,
        artists,
        dist_dir,
        args.limit,
        args.fit,
        args.jpg_fallback,
        args.webp_quality,
        widths,
        not args.index_only,
    )

    (dist_dir / "minutes.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    copy_static_files(dist_dir)

    print(
        f"Built {index['availableImages']} images across {index['totalRecords']} minute records "
        f"into {display_path(dist_dir)}."
    )


if __name__ == "__main__":
    main()
