from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class ScanlinesParams(StrictParams):
    spacing: int = Field(4, ge=2, le=64, title="Период")
    thickness: int = Field(1, ge=1, le=32, title="Толщина")
    intensity: float = Field(0.35, ge=0, le=1, title="Сила")
    orientation: Literal["horizontal", "vertical"] = Field(
        "horizontal",
        title="Направление",
    )


class ScanlinesEffect(BaseEffect):
    effect_id = "scanlines"
    display_name = "Сканлайны"
    description = "Добавляет регулярные затемнённые строки экранной развёртки."
    category = "digital"
    params_model = ScanlinesParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = ScanlinesParams.model_validate(params)
        height, width = image.shape[:2]
        length = height if validated.orientation == "horizontal" else width
        pattern = np.zeros(length, dtype=np.float32)
        for start in range(0, length, validated.spacing):
            pattern[start : start + validated.thickness] = validated.intensity
        if validated.orientation == "horizontal":
            mask = pattern[:, None, None]
        else:
            mask = pattern[None, :, None]
        output = image[:, :, :3].astype(np.float32) * (1 - mask)
        rgb = np.clip(output, 0, 255).astype(np.uint8)
        if image.shape[2] == 4:
            return np.dstack((rgb, image[:, :, 3]))
        return rgb
