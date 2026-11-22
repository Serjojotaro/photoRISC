from __future__ import annotations

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class BlockDisplacementParams(StrictParams):
    block_size: int = Field(24, ge=4, le=256, title="Размер блока")
    probability: float = Field(0.35, ge=0, le=1, title="Вероятность")
    max_offset_x: int = Field(18, ge=0, le=256, title="Сдвиг X")
    max_offset_y: int = Field(8, ge=0, le=256, title="Сдвиг Y")


class BlockDisplacementEffect(BaseEffect):
    effect_id = "block_displacement"
    display_name = "Смещение блоков"
    description = "Перемещает случайные прямоугольные блоки пикселей."
    category = "distortion"
    uses_seed = True
    params_model = BlockDisplacementParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = BlockDisplacementParams.model_validate(params)
        rng = np.random.default_rng(seed)
        output = image.copy()
        for y in range(0, image.shape[0], validated.block_size):
            for x in range(0, image.shape[1], validated.block_size):
                if rng.random() > validated.probability:
                    continue
                dy = int(rng.integers(-validated.max_offset_y, validated.max_offset_y + 1))
                dx = int(rng.integers(-validated.max_offset_x, validated.max_offset_x + 1))
                y_end = min(image.shape[0], y + validated.block_size)
                x_end = min(image.shape[1], x + validated.block_size)
                output[y:y_end, x:x_end] = np.roll(
                    image[y:y_end, x:x_end],
                    shift=(dy, dx),
                    axis=(0, 1),
                )
        return output
