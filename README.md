# klookup

CLI generator for artistic clock minutes.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r generator/requirements.txt
cp .env.example .env
```

Fill `.env` with your API keys.

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
  --replicate-model-id black-forest-labs/flux-schnell \
  --refs-mode mosaic \
  --quality high \
  --max-cost-usd 1 \
  --dry-run
```

Remove `--dry-run` to call APIs and write files.

Output files:

`<HHMM>_<artist>_<YYYYMMDDHHMM>.jpg`

Example:

`1200_agaswietek_202605081842.jpg`
