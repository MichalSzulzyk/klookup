from __future__ import annotations

import mimetypes
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


def _make_vertex_client() -> genai.Client:
    """Create a Vertex AI client for Imagen generation/editing."""
    project, location = _vertex_project_and_location()
    if not project or not location:
        raise ValueError(
            "Google backend requires Vertex AI. Set GOOGLE_CLOUD_PROJECT and "
            "GOOGLE_CLOUD_LOCATION (or GOOGLE_VERTEX_PROJECT / GOOGLE_VERTEX_LOCATION) "
            "and authenticate via Application Default Credentials."
        )
    return genai.Client(vertexai=True, project=project, location=location)


def _prompt_with_reference_indices(prompt: str, n_refs: int) -> str:
    slots = ", ".join(f"[{i}]" for i in range(1, n_refs + 1))
    return (
        f"Generate an image consistent with references {slots}. Follow any role instructions "
        f"for individual references in the prompt, and match the artist references' palette, "
        f"line quality, and graphic tone. Instructions: {prompt}"
    )


def _image_from_path(path: Path) -> types.Image:
    mime_type = mimetypes.guess_type(path.name)[0]
    if mime_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        mime_type = "image/jpeg"
    return types.Image(image_bytes=path.read_bytes(), mime_type=mime_type)


def _style_reference_images(refs: list[Path]) -> list[types.StyleReferenceImage]:
    out: list[types.StyleReferenceImage] = []
    for i, path in enumerate(refs):
        out.append(
            types.StyleReferenceImage(
                reference_id=i + 1,
                reference_image=_image_from_path(path),
                config=types.StyleReferenceConfig(
                    style_description=f"reference {i + 1} ({path.name})",
                ),
            )
        )
    return out


class GoogleBackend:
    key = "google"
    model_id = "imagen-4.0-generate-001"

    def __init__(self):
        self.client = _make_vertex_client()
        self._edit_model_id = os.getenv("GOOGLE_IMAGEN_EDIT_MODEL", self.model_id)

    def estimate_cost_usd(self, n_images: int, quality: str) -> float:
        return estimate_cost(self.key, quality, n_images)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def generate(self, prompt: str, refs: list[Path], quality: str) -> GenResult:
        if refs:
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
