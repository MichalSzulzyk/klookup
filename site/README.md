# Klookup Static Site

This is the static web layer for Klookup. The site is built locally into `dist`
and then deployed to Cloudflare Pages.

## Daily Workflow

1. Generate new minute images locally into artist output folders, for example:

   ```text
   graphics_IO_minutes/olkuolku_output/
   graphics_IO_minutes/agaswietek_output/
   ```

2. Keep artist links in `site/artists.json`.

3. Build the static site:

   ```bash
   .venv/bin/python site/build.py
   ```

4. Test locally:

   ```bash
   python3 -m http.server 8000 --directory dist
   ```

5. Deploy:

   ```bash
   npx wrangler pages deploy dist --project-name klookup --commit-dirty=true
   ```

## Local Preview

Build a small local test version:

```bash
.venv/bin/python site/build.py --limit 12
python3 -m http.server 8000 --directory dist
```

Open:

```text
http://localhost:8000/?minute=0000
```

The `?minute=0000` parameter is only for previewing a specific minute. Open
`http://localhost:8000/` without that parameter to show the viewer's local
browser time.

## Build Commands

Build all available minutes:

```bash
.venv/bin/python site/build.py
```

Refresh links and metadata without regenerating images:

```bash
.venv/bin/python site/build.py --index-only
```

By default the build writes WebP images only. Add `--jpg-fallback` if a JPEG
fallback is needed for a specific deployment target.

The MVP build writes one 1920 px WebP per minute. Later, responsive variants can
be generated with `--widths 768,1280,1920`.

## Naming Rules

Artist portfolio links live in `site/artists.json`. Artist slugs must match
output folder names without `_output`, for example:

```text
graphics_IO_minutes/olkuolku_output/0000_olkuolku.png
```

maps to:

```json
"olkuolku": {
  "name": "olkuolku",
  "portfolio_url": "https://www.behance.net/olkuolku"
}
```

Keep files in the matching artist folder. A file named `0000_olkuolku...` should
live in `olkuolku_output`, not in another artist's output folder.

If multiple generated files exist for the same `HHMM`, the build uses the newest
timestamp. Files without a timestamp use their filesystem modification time. A
blank minute is used only when no generated image exists for that minute.
