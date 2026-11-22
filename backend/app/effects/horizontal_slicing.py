from __future__ import annotations

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class HorizontalSlicingParams(StrictParams):
    slice_height: int = Field(12, ge=1, le=256, title="Высота полосы")
    max_offset: int = Field(60, ge=1, le=1000, title="Максимальный сдвиг")
    probability: float = Field(0.7, ge=0, le=1, title="Вероятность")


class HorizontalSlicingEffect(BaseEffect):
    effect_id = "horizontal_slicing"
    display_name = "Горизонтальные разрывы"
    description = "Сдвигает случайные горизонтальные полосы изображения."
    category = "distortion"
    uses_seed = True
    params_model = HorizontalSlicingParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = HorizontalSlicingParams.model_validate(params)
        rng = np.random.default_rng(seed)
        output = image.copy()
        for start in range(0, image.shape[0], validated.slice_height):
            if rng.random() <= validated.probability:
                offset = int(rng.integers(-validated.max_offset, validated.max_offset + 1))
                end = min(image.shape[0], start + validated.slice_height)
                output[start:end] = np.roll(
                    image[start:end],
                    shift=offset,
                    axis=1,
                )
        return output
