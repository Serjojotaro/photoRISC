from __future__ import annotations

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class DatamoshImitationParams(StrictParams):
    block_size: int = Field(16, ge=8, le=128, title="Размер блока")
    probability: float = Field(0.65, ge=0, le=1, title="Вероятность")
    max_block_shift: int = Field(3, ge=0, le=32, title="Сдвиг блоков")
    blend: float = Field(0.35, ge=0, le=1, title="Смешивание")


class DatamoshImitationEffect(BaseEffect):
    effect_id = "datamosh_imitation"
    display_name = "Datamosh (имитация)"
    description = "Имитирует межблочное размазывание статичного кадра; это не видео-datamosh."
    category = "datamosh"
    uses_seed = True
    params_model = DatamoshImitationParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = DatamoshImitationParams.model_validate(params)
        rng = np.random.default_rng(seed)
        output = image.copy()
        for y in range(0, image.shape[0], validated.block_size):
            for x in range(0, image.shape[1], validated.block_size):
                if rng.random() > validated.probability:
                    continue
                dy = int(
                    rng.integers(
                        -validated.max_block_shift,
                        validated.max_block_shift + 1,
                    )
                )
                dx = int(
                    rng.integers(
                        -validated.max_block_shift,
                        validated.max_block_shift + 1,
                    )
                )
                src_y = int(np.clip(y + dy * validated.block_size, 0, image.shape[0] - 1))
                src_x = int(np.clip(x + dx * validated.block_size, 0, image.shape[1] - 1))
                y_end = min(image.shape[0], y + validated.block_size)
                x_end = min(image.shape[1], x + validated.block_size)
                src_y_end = min(image.shape[0], src_y + (y_end - y))
                src_x_end = min(image.shape[1], src_x + (x_end - x))
                block = image[src_y:src_y_end, src_x:src_x_end]
                target = image[y:y_end, x:x_end]
                if block.shape != target.shape:
                    continue
                output[y:y_end, x:x_end] = (
                    target.astype(np.float32) * (1 - validated.blend)
                    + block.astype(np.float32) * validated.blend
                ).astype(np.uint8)
        return output
