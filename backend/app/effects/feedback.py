from __future__ import annotations

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class FeedbackParams(StrictParams):
    iterations: int = Field(3, ge=1, le=8, title="Повторы")
    offset_x: int = Field(8, ge=0, le=100, title="Смещение X")
    offset_y: int = Field(1, ge=0, le=100, title="Смещение Y")
    decay: float = Field(0.45, ge=0, le=0.95, title="Затухание")


class FeedbackEffect(BaseEffect):
    effect_id = "feedback"
    display_name = "Обратная связь"
    description = "Накладывает затухающие смещённые копии изображения."
    category = "digital"
    params_model = FeedbackParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = FeedbackParams.model_validate(params)
        output = np.empty_like(image[:, :, :3])
        decay = round(validated.decay * 255)
        for channel in range(3):
            source = image[:, :, channel]
            current = source.copy()
            accumulated = source.astype(np.uint16)
            for iteration in range(validated.iterations):
                current = np.roll(
                    current,
                    shift=(
                        validated.offset_y * (iteration + 1),
                        validated.offset_x * (iteration + 1),
                    ),
                    axis=(0, 1),
                )
                accumulated = (
                    accumulated * decay
                    + current.astype(np.uint16) * (255 - decay)
                    + 127
                ) // 255
            output[:, :, channel] = accumulated.astype(np.uint8)
        if image.shape[2] == 4:
            return np.dstack((output, image[:, :, 3]))
        return output
