from __future__ import annotations

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class RGBSplitParams(StrictParams):
    red_offset_x: int = Field(8, ge=-500, le=500, title="Красный X")
    red_offset_y: int = Field(0, ge=-500, le=500, title="Красный Y")
    green_offset_x: int = Field(0, ge=-500, le=500, title="Зелёный X")
    green_offset_y: int = Field(0, ge=-500, le=500, title="Зелёный Y")
    blue_offset_x: int = Field(-8, ge=-500, le=500, title="Синий X")
    blue_offset_y: int = Field(0, ge=-500, le=500, title="Синий Y")


class RGBSplitEffect(BaseEffect):
    effect_id = "rgb_split"
    display_name = "Сдвиг RGB"
    description = "Смещает красный, зелёный и синий каналы независимо."
    category = "color"
    params_model = RGBSplitParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = RGBSplitParams.model_validate(params)
        output = image.copy()
        offsets = (
            (0, validated.red_offset_y, validated.red_offset_x),
            (1, validated.green_offset_y, validated.green_offset_x),
            (2, validated.blue_offset_y, validated.blue_offset_x),
        )
        for channel, offset_y, offset_x in offsets:
            output[:, :, channel] = np.roll(
                image[:, :, channel],
                shift=(offset_y, offset_x),
                axis=(0, 1),
            )
        return output
