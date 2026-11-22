from __future__ import annotations

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class NoiseParams(StrictParams):
    sigma: float = Field(18, ge=0, le=120, title="Сила шума")
    monochrome: bool = Field(False, title="Монохромный")


class NoiseEffect(BaseEffect):
    effect_id = "noise"
    display_name = "Шум"
    description = "Добавляет воспроизводимый гауссов шум."
    category = "digital"
    uses_seed = True
    params_model = NoiseParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = NoiseParams.model_validate(params)
        rng = np.random.default_rng(seed)
        color_channels = image[:, :, :3].astype(np.int16)
        if validated.monochrome:
            noise = rng.normal(0, validated.sigma, image.shape[:2])[:, :, None]
        else:
            noise = rng.normal(0, validated.sigma, color_channels.shape)
        noisy = np.clip(color_channels + noise, 0, 255).astype(np.uint8)
        if image.shape[2] == 4:
            return np.dstack((noisy, image[:, :, 3]))
        return noisy
