# Klookup Static Site

Build a local test version:

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

Artist portfolio links live in `site/artists.json`. Artist slugs should match output
folder names without `_output`, for example `olkuolku_output` maps to `olkuolku`.
