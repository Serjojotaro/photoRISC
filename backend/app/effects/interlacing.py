from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class InterlacingParams(StrictParams):
    offset: int = Field(4, ge=0, le=80, title="Смещение")
    spacing: int = Field(2, ge=2, le=16, title="Шаг строк")
    lines: Literal["odd", "even"] = Field("odd", title="Линии")


class InterlacingEffect(BaseEffect):
    effect_id = "interlacing"
    display_name = "Интерлейсинг"
    description = "Смещает чётные или нечётные строки, имитируя чересстрочную развёртку."
    category = "analog"
    params_model = InterlacingParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = InterlacingParams.model_validate(params)
        output = image.copy()
        remainder = 1 if validated.lines == "odd" else 0
        for row in range(image.shape[0]):
            if row % validated.spacing == remainder:
                output[row] = np.roll(
                    image[row],
                    shift=validated.offset,
                    axis=0,
                )
        return output
