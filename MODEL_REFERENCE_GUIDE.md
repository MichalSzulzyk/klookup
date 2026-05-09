# Model Reference Guide

Quick reference for how image references ("wsady") are handled in this project.

## Key Terms

- **Artist refs**: images from `--input`, used for visual style.
- **Template**: image from `--template`, used only as clock layout/composition guidance.
- **Final refs sent to API**: the actual list printed by CLI and sent to the selected backend.

## Current Behavior

### OpenAI

- Model: `gpt-image-1`
- Prompt: yes
- Artist refs: selected by `--refs-mode`
- Template: sent after artist refs, as layout only
- API receives: selected artist refs + optional template
- Meaning: OpenAI can use multiple reference images in one request, but artist refs drive style.

### Replicate

- Default model: `black-forest-labs/flux-2-pro`
- Additional image model: `google/nano-banana-2`
- Prompt: yes
- Artist refs: selected by `--refs-mode`
- Template: sent as layout/composition ref when provided
- API receives: model-specific image field (`input_images` or `image_input`)
- Meaning: Replicate is the easiest backend for swapping image models with refs.

Replicate image model limits:

- `black-forest-labs/flux-2-pro`: max 8 refs via `input_images`
- `google/nano-banana-2`: max 14 refs via `image_input`

## Important Notes

- `--input` points to artist reference images (the "input refs").
- `--template` is separate from artist refs.
- `--refs-mode` applies only to artist refs.
- Mosaic is built only from artist refs, never from template.
- The CLI prints the final refs that are actually sent to the API.
- Sidecar JSON stores `artist_refs`, `selected_artist_refs`, final `refs`, and truncation notes.

## Safe Command Patterns (right now)

### OpenAI (`gpt-image-1`)
- Works with multiple refs.
- `first` sends one artist ref plus optional template.
- `mosaic` sends one artist mosaic plus optional template.

### Replicate
- Treat as a multi-reference test backend.
- Use:
  - `--refs-mode first` for template + one artist ref,
  - `--refs-mode mosaic` for template + one artist mosaic,
  - or `--refs-mode all`; the CLI automatically applies the selected model's ref limit.

## Expected CLI Printout

Before generation, check this block:

```text
Artist refs count: 9
Selected artist refs count: 9
Final refs sent to API count: 8
  [1] graphics_template/klookup_template.jpg
  [2] graphics_IO_minutes/oykuakarca_input/example-1.jpg
  [3] graphics_IO_minutes/oykuakarca_input/example-2.jpg
  ...
  [8] graphics_IO_minutes/oykuakarca_input/example-7.jpg
Warning: refs were truncated for this model/backend limit.
```

If that list looks wrong, stop and change `--refs-mode` before running without `--dry-run`.

## Test Commands

### OpenAI dry-run

```bash
python -m generator.cli \
  --input graphics_IO_minutes/oykuakarca_input \
  --range 1017 1017 \
  --prompt generator/prompts/general_04_detailed.txt \
  --template graphics_template/klookup_template.jpg \
  --model openai \
  --refs-mode first \
  --quality high \
  --max-cost-usd 1 \
  --dry-run
```

### Replicate dry-run

```bash
python -m generator.cli \
  --input graphics_IO_minutes/oykuakarca_input \
  --range 1017 1017 \
  --prompt generator/prompts/general_04_detailed.txt \
  --template graphics_template/klookup_template.jpg \
  --model replicate \
  --refs-mode all \
  --quality high \
  --max-cost-usd 1 \
  --dry-run
```

### Replicate Nano Banana 2 dry-run

```bash
python -m generator.cli \
  --input graphics_IO_minutes/oykuakarca_input \
  --range 1017 1017 \
  --prompt generator/prompts/general_04_detailed.txt \
  --template graphics_template/klookup_template.jpg \
  --model replicate \
  --replicate-model-id google/nano-banana-2 \
  --refs-mode all \
  --quality medium \
  --max-cost-usd 1 \
  --dry-run
```

## Recommended Operating Rules

1. For stable results across models, think in terms of:
   - **single ref mode** (`first` or `mosaic`) vs
   - **multi-ref mode** (`all`, useful for OpenAI and Replicate).
2. For Replicate, check each model profile and the printed `Final refs sent to API`.
3. Always check the CLI printout: `Final refs sent to API`.

