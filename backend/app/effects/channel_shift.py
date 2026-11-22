from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class ChannelShiftParams(StrictParams):
    channel: Literal["red", "green", "blue"] = Field(
        "blue",
        title="Канал",
    )
    offset_x: int = Field(12, ge=-500, le=500, title="Сдвиг X")
    offset_y: int = Field(0, ge=-500, le=500, title="Сдвиг Y")


class ChannelShiftEffect(BaseEffect):
    effect_id = "channel_shift"
    display_name = "Сдвиг канала"
    description = "Смещает один цветовой канал с зацикливанием."
    category = "color"
    params_model = ChannelShiftParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = ChannelShiftParams.model_validate(params)
        index = {"red": 0, "green": 1, "blue": 2}[validated.channel]
        output = image.copy()
        output[:, :, index] = np.roll(
            image[:, :, index],
            shift=(validated.offset_y, validated.offset_x),
            axis=(0, 1),
        )
        return output
