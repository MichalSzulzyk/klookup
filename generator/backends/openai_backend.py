from __future__ import annotations

import base64
from pathlib import Path

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from generator.backends.base import GenResult
    from generator.cost import estimate_cost
except ModuleNotFoundError:
    from backends.base import GenResult
    from cost import estimate_cost


class OpenAIBackend:
    key = "openai"
    model_id = "gpt-image-1"

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def estimate_cost_usd(self, n_images: int, quality: str) -> float:
        return estimate_cost(self.key, quality, n_images)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def generate(self, prompt: str, refs: list[Path], quality: str) -> GenResult:
        handles = [ref.open("rb") for ref in refs]
        try:
            result = self.client.images.edit(
                model=self.model_id,
                image=handles,
                prompt=prompt,
                size="1536x1024",
                quality=quality,
            )
        finally:
            for handle in handles:
                handle.close()
        b64 = result.data[0].b64_json
        if not b64:
            raise ValueError("OpenAI response does not contain image data")
        image_bytes = base64.b64decode(b64)
        return GenResult(
            image_bytes=image_bytes,
            original_size=(1536, 1024),
            cost_usd=estimate_cost(self.key, quality, 1),
            request_id=getattr(result, "_request_id", None),
            model_id=self.model_id,
        )
