from __future__ import annotations

import os
from pathlib import Path

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from generator.backends.base import GenResult
    from generator.cost import estimate_cost
except ModuleNotFoundError:
    from backends.base import GenResult
    from cost import estimate_cost


def _vertex_project_and_location() -> tuple[str | None, str | None]:
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_VERTEX_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("GOOGLE_VERTEX_LOCATION")
    return project, location


def _make_genai_client(api_key: str | None) -> tuple[genai.Client, bool]:
    """Vertex client enables ``edit_image`` (reference images). API-key client is text-only for Imagen."""
    project, location = _vertex_project_and_location()
    if project and location:
        return genai.Client(vertexai=True, project=project, location=location), True
    if not api_key:
        raise ValueError(
            "Set GOOGLE_API_KEY for the Gemini API, or set GOOGLE_CLOUD_PROJECT and "
            "GOOGLE_CLOUD_LOCATION (with Application Default Credentials) for Vertex AI."
        )
    return genai.Client(api_key=api_key), False


def _prompt_with_reference_indices(prompt: str, n_refs: int) -> str:
    slots = ", ".join(f"[{i}]" for i in range(1, n_refs + 1))
    return (
        f"Generate an image consistent with references {slots}: match palette, line quality, "
        f"and graphic tone from those images. Treat [1] as the primary composition/layout "
        f"guide when it looks like a template or clock face. Instructions: {prompt}"
    )


def _style_reference_images(refs: list[Path]) -> list[types.StyleReferenceImage]:
    out: list[types.StyleReferenceImage] = []
    for i, path in enumerate(refs):
        out.append(
            types.StyleReferenceImage(
                reference_id=i + 1,
                reference_image=types.Image.from_file(location=str(path)),
                config=types.StyleReferenceConfig(
                    style_description=f"reference {i + 1} ({path.name})",
                ),
            )
        )
    return out


class GoogleBackend:
    key = "google"
    model_id = "imagen-4.0-generate-001"

    def __init__(self, api_key: str | None = None):
        self.client, self._vertex = _make_genai_client(api_key)
        self._edit_model_id = os.getenv("GOOGLE_IMAGEN_EDIT_MODEL", self.model_id)

    def estimate_cost_usd(self, n_images: int, quality: str) -> float:
        return estimate_cost(self.key, quality, n_images)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def generate(self, prompt: str, refs: list[Path], quality: str) -> GenResult:
        if refs:
            if not self._vertex:
                raise ValueError(
                    "Reference images for Google Imagen need Vertex AI: set "
                    "GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION and authenticate "
                    "with Application Default Credentials. The Gemini Developer API "
                    "(GOOGLE_API_KEY only) does not expose edit/reference paths for Imagen."
                )
            augmented = _prompt_with_reference_indices(prompt, len(refs))
            response = self.client.models.edit_image(
                model=self._edit_model_id,
                prompt=augmented,
                reference_images=_style_reference_images(refs),
                config=types.EditImageConfig(
                    number_of_images=1,
                    aspect_ratio="16:9",
                    output_mime_type="image/jpeg",
                    output_compression_quality=92,
                ),
            )
            generated = response.generated_images[0]
            image_bytes = generated.image.image_bytes
            return GenResult(
                image_bytes=image_bytes,
                original_size=(1536, 1024),
                cost_usd=estimate_cost(self.key, quality, 1),
                request_id=None,
                model_id=self._edit_model_id,
            )

        response = self.client.models.generate_images(
            model=self.model_id,
            prompt=prompt,
            config={"number_of_images": 1},
        )
        generated = response.generated_images[0]
        image_bytes = generated.image.image_bytes
        return GenResult(
            image_bytes=image_bytes,
            original_size=(1536, 1024),
            cost_usd=estimate_cost(self.key, quality, 1),
            request_id=None,
            model_id=self.model_id,
        )
