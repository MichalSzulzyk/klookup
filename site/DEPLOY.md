# Manual Deploy

The current MVP is a static site. There is no server, database, or backend to
deploy. Upload the contents of `dist` to a static host.

## Recommended Host

Start with Cloudflare Pages:

1. Build the site locally:

   ```bash
   .venv/bin/python site/build.py
   ```

2. Open the Cloudflare dashboard and create a Pages project.
3. Choose a direct/manual upload flow.
4. Upload the contents of `dist`.
5. After the preview URL works, attach the final domain in the Pages project
   settings.

Upload the files inside `dist`, not the source folders such as
`graphics_IO_minutes` or `site`.

## Updating Artist Links

When only `site/artists.json` changes, refresh the index without converting all
images again:

```bash
.venv/bin/python site/build.py --index-only
```

Then upload the updated `dist/minutes.json` and, if changed, `dist/index.html`,
`dist/styles.css`, or `dist/app.js`.

## Current Build Shape

- `dist/index.html` is the page.
- `dist/app.js` controls the local-time minute switching and crossfade.
- `dist/styles.css` handles the full-screen responsive layout.
- `dist/minutes.json` maps each `HHMM` minute to an image and artist link.
- `dist/assets/minutes` contains the optimized WebP minute images.

## Notes

- `dist` is generated and ignored by git.
- The asset source folders are also ignored by git, so this is currently a
  local/manual publishing workflow.
- If manual uploads become inconvenient, the next step is to move image hosting
  to object storage such as Cloudflare R2 or automate uploads with a deploy
  script.
