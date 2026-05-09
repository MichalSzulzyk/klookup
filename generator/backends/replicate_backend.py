from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

import replicate
from replicate.exceptions import ReplicateError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    from generator.backends.base import GenResult
    from generator.cost import estimate_cost
except ModuleNotFoundError:
    from backends.base import GenResult
    from cost import estimate_cost


def _read_replicate_output(value) -> bytes:
    if hasattr(value, "read"):
        return value.read()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        with urlopen(value) as response:
            return response.read()
    raise ValueError("Replicate output format unsupported")


class ReplicateBackend:
    key = "replicate"
    default_model_id = "black-forest-labs/flux-2-pro"

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
        output_quality = {"low": 70, "medium": 82, "high": 92}[quality]
        resolution = {"low": "1 MP", "medium": "1 MP", "high": "2 MP"}[quality]
        payload = {
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "resolution": resolution,
            "output_format": "jpg",
            "output_quality": output_quality,
            "safety_tolerance": 2,
        }
        if refs:
            payload["input_images"] = [self.client.files.create(file=ref).urls["get"] for ref in refs]

        out = self.client.run(self.model_id, input=payload)
        if isinstance(out, list) and out:
            image_data = _read_replicate_output(out[0])
        else:
            image_data = _read_replicate_output(out)

        return GenResult(
            image_bytes=image_data,
            original_size=(1920, 1080),
            cost_usd=estimate_cost(self.key, quality, 1),
            request_id=None,
            model_id=self.model_id,
        )
