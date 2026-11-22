from __future__ import annotations

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class PosterizeParams(StrictParams):
    levels: int = Field(6, ge=2, le=64, title="Уровней на канал")
    blend: float = Field(1, ge=0, le=1, title="Смешивание")


class PosterizeEffect(BaseEffect):
    effect_id = "posterize"
    display_name = "Постеризация"
    description = "Сокращает количество уровней цвета и создаёт плакатные области."
    category = "color"
    params_model = PosterizeParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = PosterizeParams.model_validate(params)
        rgb = image[:, :, :3].astype(np.uint16)
        step = 256 / validated.levels
        reduced = (
            np.floor(rgb / step) * (255 / (validated.levels - 1))
        ).clip(0, 255)
        mixed = (
            rgb * (1 - validated.blend) + reduced * validated.blend
        ).clip(0, 255).astype(np.uint8)
        if image.shape[2] == 4:
            return np.dstack((mixed, image[:, :, 3]))
        return mixed
