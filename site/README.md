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

Build all available minutes:

```bash
.venv/bin/python site/build.py
```

Artist portfolio links live in `site/artists.json`. Artist slugs should match output
folder names without `_output`, for example `olkuolku_output` maps to `olkuolku`.
