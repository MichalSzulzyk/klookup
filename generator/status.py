from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import click


@click.command()
@click.option(
    "--io-root",
    default="../graphics_IO_minutes",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to graphics_IO_minutes",
)
def main(io_root: Path) -> None:
    coverage: dict[str, set[str]] = defaultdict(set)
    for out_dir in sorted(io_root.glob("*_output")):
        artist = out_dir.name.removesuffix("_output")
        for file in out_dir.glob("*.jpg"):
            parts = file.stem.split("_")
            if len(parts) >= 3 and len(parts[0]) == 4 and parts[0].isdigit():
                coverage[artist].add(parts[0])

    if not coverage:
        click.echo("No generated jpg files found.")
        return

    click.echo("Coverage report:")
    for artist, minutes in sorted(coverage.items()):
        click.echo(f"- {artist}: {len(minutes)} unique minutes")


if __name__ == "__main__":
    main()
