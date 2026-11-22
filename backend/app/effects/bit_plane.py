from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class BitPlaneParams(StrictParams):
    bit: int = Field(4, ge=0, le=7, title="Бит")
    operation: Literal["extract", "invert", "zero"] = Field(
        "extract",
        title="Операция",
    )


class BitPlaneEffect(BaseEffect):
    effect_id = "bit_plane"
    display_name = "Битовая плоскость"
    description = "Извлекает, инвертирует или обнуляет выбранный бит изображения."
    category = "digital"
    params_model = BitPlaneParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = BitPlaneParams.model_validate(params)
        rgb = image[:, :, :3]
        if validated.operation == "extract":
            luminance = (
                rgb[:, :, 0].astype(np.uint16) * 77
                + rgb[:, :, 1].astype(np.uint16) * 150
                + rgb[:, :, 2].astype(np.uint16) * 29
            ) >> 8
            plane = (((luminance >> validated.bit) & 1) * 255).astype(np.uint8)
            extracted = np.repeat(plane[:, :, None], 3, axis=2)
            if image.shape[2] == 4:
                return np.dstack((extracted, image[:, :, 3]))
            return extracted

        output = image.copy()
        bit_mask = np.uint8(1 << validated.bit)
        if validated.operation == "invert":
            output[:, :, :3] ^= bit_mask
        else:
            output[:, :, :3] &= ~bit_mask
        return output
