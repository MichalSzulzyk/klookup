from __future__ import annotations

COST_PER_IMAGE_USD: dict[str, dict[str, float]] = {
    "openai": {
        "low": 0.011,
        "medium": 0.042,
        "high": 0.167,
    },
    "replicate": {
        "low": 0.03,
        "medium": 0.06,
        "high": 0.08,
    },
    "google": {
        "low": 0.02,
        "medium": 0.04,
        "high": 0.08,
    },
}


def estimate_cost(backend: str, quality: str, n_images: int) -> float:
    try:
        return COST_PER_IMAGE_USD[backend][quality] * n_images
    except KeyError as exc:
        raise ValueError(f"Unsupported cost lookup: backend={backend}, quality={quality}") from exc
