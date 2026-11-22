from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class PixelSortParams(StrictParams):
    threshold_low: int = Field(35, ge=0, le=255, title="Нижний порог")
    threshold_high: int = Field(230, ge=0, le=255, title="Верхний порог")
    direction: Literal["horizontal", "vertical"] = Field(
        "horizontal",
        title="Направление",
    )
    reverse: bool = Field(False, title="Обратная сортировка")
    criterion: Literal["brightness", "red", "green", "blue"] = Field(
        "brightness",
        title="Критерий",
    )


class PixelSortEffect(BaseEffect):
    effect_id = "pixel_sort"
    display_name = "Сортировка пикселей"
    description = "Упорядочивает связные интервалы пикселей и создаёт эффект растекания."
    category = "digital"
    params_model = PixelSortParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = PixelSortParams.model_validate(params)
        working = image if validated.direction == "horizontal" else np.swapaxes(image, 0, 1)
        output = working.copy()
        rgb = working[:, :, :3].astype(np.int16)
        luminance = (
            rgb[:, :, 0] * 77 + rgb[:, :, 1] * 150 + rgb[:, :, 2] * 29
        ) >> 8
        mask = (luminance >= validated.threshold_low) & (
            luminance <= validated.threshold_high
        )
        criterion = {
            "brightness": luminance,
            "red": rgb[:, :, 0],
            "green": rgb[:, :, 1],
            "blue": rgb[:, :, 2],
        }[validated.criterion]

        for line_index in range(working.shape[0]):
            active = mask[line_index]
            if not active.any():
                continue
            starts = np.flatnonzero(active & ~np.r_[False, active[:-1]])
            ends = np.flatnonzero(active & ~np.r_[active[1:], False]) + 1
            for start, end in zip(starts, ends, strict=True):
                if end - start < 2:
                    continue
                order = np.argsort(criterion[line_index, start:end], kind="stable")
                if validated.reverse:
                    order = order[::-1]
                output[line_index, start:end, :3] = working[
                    line_index,
                    start:end,
                    :3,
                ][order]
        return output if validated.direction == "horizontal" else np.swapaxes(output, 0, 1)
