from __future__ import annotations

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class DisplacementParams(StrictParams):
    amplitude: int = Field(24, ge=0, le=300, title="Амплитуда")
    period: float = Field(90, ge=4, le=1000, title="Период")
    phase: float = Field(0, ge=0, le=1, title="Фаза")


class DisplacementEffect(BaseEffect):
    effect_id = "displacement"
    display_name = "Волновое смещение"
    description = "Сдвигает строки по синусоиде и создаёт плавную цифровую деформацию."
    category = "distortion"
    params_model = DisplacementParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = DisplacementParams.model_validate(params)
        output = image.copy()
        rows = np.arange(image.shape[0], dtype=np.float64)
        offsets = np.rint(
            validated.amplitude
            * np.sin(2 * np.pi * rows / validated.period + validated.phase * 2 * np.pi)
        ).astype(int)
        for row, offset in enumerate(offsets):
            output[row] = np.roll(image[row], shift=offset, axis=0)
        return output
