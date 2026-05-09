# klookup

CLI generator for artistic clock minutes.

See `MODEL_REFERENCE_GUIDE.md` for how each backend uses reference images.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r generator/requirements.txt
cp .env.example .env
```

Fill `.env` with your API keys / Vertex settings.

For Google Vertex:

```bash
gcloud auth application-default login
```

Required `.env` values:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=your-region
GOOGLE_GENAI_USE_VERTEXAI=true
```

## Generate (example)

```bash
python -m generator.cli \
  --input graphics_IO_minutes/agaswietek_input \
  --range 1200 1259 \
  --prompt generator/prompts/general.txt \
  --template graphics_template/klookup_template.jpg \
  --model openai \
  --refs-mode all \
  --quality medium \
  --max-cost-usd 5 \
  --dry-run
```

Replicate model override example:

```bash
python -m generator.cli \
  --input graphics_IO_minutes/oykuakarca_input \
  --range 1925 1925 \
  --prompt generator/prompts/general_04_detailed.txt \
  --template graphics_template/klookup_template.jpg \
  --model replicate \
  --replicate-model-id black-forest-labs/flux-2-pro \
  --refs-mode mosaic \
  --quality high \
  --max-cost-usd 1 \
  --dry-run
```

Remove `--dry-run` to call APIs and write files.

## Reference Image Rules

- `--input` is the artist reference folder.
- `--template` is a separate clock layout reference.
- `--refs-mode` applies only to artist references, not to the template.
- `mosaic` is built only from artist references.
- The CLI prints `Final refs sent to API` before generation, so you can verify what each model will actually receive.

Backend summary:

- `openai`: selected artist refs + optional template.
- `replicate`: max 8 refs; template + up to 7 artist refs.
- `google`: max 4 refs; template + up to 3 artist refs.

## Google Vertex Test Example

```bash
python -m generator.cli \
  --input graphics_IO_minutes/oykuakarca_input \
  --range 1017 1017 \
  --prompt generator/prompts/general_04_detailed.txt \
  --template graphics_template/klookup_template.jpg \
  --model google \
  --refs-mode all \
  --quality high \
  --max-cost-usd 1 \
  --dry-run
```

Remove `--dry-run` after checking the printed refs.

Output files:

`<HHMM>_<artist>_<YYYYMMDDHHMM>.jpg`

Example:

`1200_agaswietek_202605081842.jpg`
