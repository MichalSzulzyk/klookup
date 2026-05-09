from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv
from PIL import Image
from tqdm import tqdm

try:
    from generator.backends import GoogleBackend, OpenAIBackend, ReplicateBackend
    from generator.cost import estimate_cost
    from generator.naming import build_filename, build_sidecar_filename, find_latest
    from generator.validate import validate_to_jpeg_1920x1080
except ModuleNotFoundError:
    from backends import GoogleBackend, OpenAIBackend, ReplicateBackend
    from cost import estimate_cost
    from naming import build_filename, build_sidecar_filename, find_latest
    from validate import validate_to_jpeg_1920x1080


def parse_hhmm(value: str) -> tuple[int, int]:
    if len(value) != 4 or not value.isdigit():
        raise click.BadParameter(f"Invalid HHMM value: {value}")
    hh = int(value[:2])
    mm = int(value[2:])
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        raise click.BadParameter(f"Invalid HHMM value: {value}")
    return hh, mm


def hhmm_to_minutes(value: str) -> int:
    hh, mm = parse_hhmm(value)
    return hh * 60 + mm


def minutes_to_hhmm(value: int) -> str:
    hh = value // 60
    mm = value % 60
    return f"{hh:02d}{mm:02d}"


def expand_range(start_hhmm: str, end_hhmm: str) -> list[str]:
    start = hhmm_to_minutes(start_hhmm)
    end = hhmm_to_minutes(end_hhmm)
    if start > end:
        raise click.BadParameter("Start range must be <= end range")
    return [minutes_to_hhmm(m) for m in range(start, end + 1)]


def load_backend(model: str, replicate_model_id: str | None = None):
    if model == "openai":
        import os

        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise click.ClickException("OPENAI_API_KEY missing in environment/.env")
        return OpenAIBackend(key)
    if model == "replicate":
        import os

        key = os.getenv("REPLICATE_API_TOKEN")
        if not key:
            raise click.ClickException("REPLICATE_API_TOKEN missing in environment/.env")
        return ReplicateBackend(key, model_id=replicate_model_id)
    if model == "google":
        import os

        key = os.getenv("GOOGLE_API_KEY")
        project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_VERTEX_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("GOOGLE_VERTEX_LOCATION")
        if not key and not (project and location):
            raise click.ClickException(
                "For --model google: set GOOGLE_API_KEY, or set GOOGLE_CLOUD_PROJECT and "
                "GOOGLE_CLOUD_LOCATION (Vertex AI; needed for reference images / template)."
            )
        return GoogleBackend(api_key=key)
    raise click.ClickException(f"Unsupported model backend: {model}")


def read_prompt(path: Path) -> str:
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise click.ClickException("Prompt file is empty")
    return content


def list_refs(path: Path) -> list[Path]:
    refs = sorted(path.glob("*.png")) + sorted(path.glob("*.jpg")) + sorted(path.glob("*.jpeg"))
    if not refs:
        raise click.ClickException(f"No image refs found in {path}")
    return refs


def build_mosaic_ref(refs: list[Path], out_dir: Path, artist_name: str) -> Path:
    thumbs: list[Image.Image] = []
    for ref in refs:
        with Image.open(ref) as img:
            thumbs.append(img.convert("RGB").copy())

    cols = 2
    rows = (len(thumbs) + cols - 1) // cols
    tile_w, tile_h = 640, 360
    canvas = Image.new("RGB", (cols * tile_w, rows * tile_h), color=(245, 245, 245))

    for i, img in enumerate(thumbs):
        fitted = img.resize((tile_w, tile_h), Image.Resampling.LANCZOS)
        x = (i % cols) * tile_w
        y = (i // cols) * tile_h
        canvas.paste(fitted, (x, y))

    refs_dir = out_dir / ".refs_cache"
    refs_dir.mkdir(parents=True, exist_ok=True)
    mosaic_path = refs_dir / f"{artist_name}_mosaic.jpg"
    canvas.save(mosaic_path, format="JPEG", quality=92)
    return mosaic_path


def apply_refs_mode(refs: list[Path], refs_mode: str, out_dir: Path, artist_name: str) -> list[Path]:
    if refs_mode == "all":
        return refs
    if refs_mode == "first":
        return refs[:1]
    if refs_mode == "mosaic":
        return [build_mosaic_ref(refs, out_dir=out_dir, artist_name=artist_name)]
    raise click.ClickException(f"Unsupported refs mode: {refs_mode}")


def refs_count_for_mode(refs_count: int, refs_mode: str) -> int:
    if refs_mode == "all":
        return refs_count
    if refs_mode in {"first", "mosaic"}:
        return 1
    raise click.ClickException(f"Unsupported refs mode: {refs_mode}")


@click.command()
@click.option("--input", "input_dir", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--range", "time_range", required=True, nargs=2, type=str)
@click.option("--prompt", "prompt_file", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--template",
    "template_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional template image used as composition guidance.",
)
@click.option("--model", required=True, type=click.Choice(["openai", "replicate", "google"]))
@click.option(
    "--replicate-model-id",
    default=None,
    type=str,
    help="Override replicate model slug, e.g. black-forest-labs/flux-schnell.",
)
@click.option(
    "--refs-mode",
    default="all",
    type=click.Choice(["all", "first", "mosaic"]),
    help="How to pass reference images into backends.",
)
@click.option("--artist", default=None, type=str)
@click.option("--output", "output_dir", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--quality", default="medium", type=click.Choice(["low", "medium", "high"]))
@click.option("--max-cost-usd", default=10.0, type=float)
@click.option("--minutes-limit", default=1500, type=int)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--force", is_flag=True, default=False)
def main(
    input_dir: Path,
    time_range: tuple[str, str],
    prompt_file: Path,
    template_file: Path | None,
    model: str,
    replicate_model_id: str | None,
    refs_mode: str,
    artist: str | None,
    output_dir: Path | None,
    quality: str,
    max_cost_usd: float,
    minutes_limit: int,
    dry_run: bool,
    force: bool,
) -> None:
    load_dotenv()

    artist_name = artist or input_dir.name.removesuffix("_input")
    if not artist_name:
        raise click.ClickException("Could not determine artist name from input directory")

    out_dir = output_dir or (input_dir.parent / f"{artist_name}_output")
    out_dir.mkdir(parents=True, exist_ok=True)

    minutes = expand_range(time_range[0], time_range[1])
    if len(minutes) > minutes_limit:
        raise click.ClickException(f"Range has {len(minutes)} minutes, exceeds --minutes-limit={minutes_limit}")

    base_refs = list_refs(input_dir)
    if template_file is not None:
        base_refs = [template_file] + base_refs
    prompt_template = read_prompt(prompt_file)
    est_cost = estimate_cost(model, quality, len(minutes))
    click.echo(f"Artist: {artist_name}")
    click.echo(f"Output: {out_dir}")
    click.echo(f"Model backend: {model}")
    if model == "replicate" and replicate_model_id:
        click.echo(f"Replicate model override: {replicate_model_id}")
    click.echo(f"Refs mode: {refs_mode}")
    click.echo(f"Template: {template_file if template_file else 'none'}")
    click.echo(f"Base refs count: {len(base_refs)}")
    click.echo(f"Selected refs count: {refs_count_for_mode(len(base_refs), refs_mode)}")
    click.echo(f"Minutes: {minutes[0]}..{minutes[-1]} ({len(minutes)} images)")
    click.echo(f"Estimated cost: ${est_cost:.2f}")
    if est_cost > max_cost_usd:
        raise click.ClickException(f"Estimated cost ${est_cost:.2f} exceeds --max-cost-usd={max_cost_usd:.2f}")

    if dry_run:
        if model == "replicate" and replicate_model_id:
            click.echo(f"Replicate model override: {replicate_model_id}")
        click.echo("Dry run complete: no API calls were made.")
        return

    refs = apply_refs_mode(base_refs, refs_mode=refs_mode, out_dir=out_dir, artist_name=artist_name)
    backend = load_backend(model, replicate_model_id=replicate_model_id)
    click.echo(f"Resolved model id: {backend.model_id}")

    generated = 0
    skipped = 0
    for hhmm in tqdm(minutes, desc="Generating"):
        if find_latest(out_dir, hhmm, artist_name) is not None and not force:
            skipped += 1
            continue

        hh, mm = hhmm[:2], hhmm[2:]
        prompt = prompt_template.replace("{HH}", hh).replace("{MM}", mm)
        result = backend.generate(prompt=prompt, refs=refs, quality=quality)
        jpeg_bytes, original_size = validate_to_jpeg_1920x1080(result.image_bytes)

        now = datetime.now()
        filename = build_filename(hhmm, artist_name, now)
        sidecar_name = build_sidecar_filename(hhmm, artist_name, now)
        output_path = out_dir / filename
        sidecar_path = out_dir / sidecar_name
        output_path.write_bytes(jpeg_bytes)

        metadata = {
            "hhmm": hhmm,
            "artist": artist_name,
            "model_backend": model,
            "model_id": result.model_id,
            "refs_mode": refs_mode,
            "quality": quality,
            "prompt_file": str(prompt_file),
            "prompt": prompt,
            "refs": [str(r) for r in refs],
            "template_file": str(template_file) if template_file else None,
            "cost_usd": result.cost_usd,
            "request_id": result.request_id,
            "original_size_px": list(original_size),
            "output_size_px": [1920, 1080],
            "output_format": "JPEG",
            "created_iso": now.isoformat(),
            "output_file": str(output_path),
        }
        sidecar_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        generated += 1

    click.echo(f"Done. Generated: {generated}, skipped: {skipped}, output: {out_dir}")


if __name__ == "__main__":
    main()
