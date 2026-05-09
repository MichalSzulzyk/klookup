from __future__ import annotations

from pathlib import Path

import replicate
from replicate.exceptions import ReplicateError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    from generator.backends.base import GenResult
    from generator.cost import estimate_cost
except ModuleNotFoundError:
    from backends.base import GenResult
    from cost import estimate_cost


class ReplicateBackend:
    key = "replicate"
    default_model_id = "black-forest-labs/flux-1.1-pro-ultra"

    def __init__(self, api_token: str, model_id: str | None = None):
        self.client = replicate.Client(api_token=api_token)
        self.model_id = model_id or self.default_model_id

    def estimate_cost_usd(self, n_images: int, quality: str) -> float:
        return estimate_cost(self.key, quality, n_images)

    @retry(
        retry=retry_if_exception_type(ReplicateError),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=20),
    )
    def generate(self, prompt: str, refs: list[Path], quality: str) -> GenResult:
        guidance = {"low": 2.5, "medium": 3.5, "high": 5.0}[quality]
        payload = {
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "output_format": "jpg",
            "guidance": guidance,
            "safety_tolerance": 2,
        }
        if refs:
            uploaded = self.client.files.create(file=refs[0])
            payload["image_prompt"] = uploaded.urls["get"]

        out = self.client.run(self.model_id, input=payload)
        if isinstance(out, list) and out:
            image_data = out[0].read() if hasattr(out[0], "read") else bytes(out[0])
        elif hasattr(out, "read"):
            image_data = out.read()
        elif isinstance(out, (bytes, bytearray)):
            image_data = bytes(out)
        else:
            raise ValueError("Replicate output format unsupported")

        return GenResult(
            image_bytes=image_data,
            original_size=(1920, 1080),
            cost_usd=estimate_cost(self.key, quality, 1),
            request_id=None,
            model_id=self.model_id,
        )
