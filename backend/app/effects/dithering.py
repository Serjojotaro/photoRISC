from __future__ import annotations

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


BAYER_2 = np.array([[0, 2], [3, 1]], dtype=np.float32) / 4
BAYER_4 = np.array(
    [
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5],
    ],
    dtype=np.float32,
) / 16
BAYER_8 = np.array(
    [
        [0, 32, 8, 40, 2, 34, 10, 42],
        [48, 16, 56, 24, 50, 18, 58, 26],
        [12, 44, 4, 36, 14, 46, 6, 38],
        [60, 28, 52, 20, 62, 30, 54, 22],
        [3, 35, 11, 43, 1, 33, 9, 41],
        [51, 19, 59, 27, 49, 17, 57, 25],
        [15, 47, 7, 39, 13, 45, 5, 37],
        [63, 31, 55, 23, 61, 29, 53, 21],
    ],
    dtype=np.float32,
) / 64


class DitheringParams(StrictParams):
    matrix: int = Field(4, ge=2, le=8, title="Матрица")
    bias: int = Field(0, ge=-128, le=128, title="Смещение яркости")
    invert: bool = Field(False, title="Инверсия")


class DitheringEffect(BaseEffect):
    effect_id = "dithering"
    display_name = "Дизеринг"
    description = "Превращает яркость в упорядоченный чёрно-белый точечный паттерн."
    category = "color"
    params_model = DitheringParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = DitheringParams.model_validate(params)
        bayer = BAYER_2 if validated.matrix <= 2 else BAYER_4 if validated.matrix <= 4 else BAYER_8
        height, width = image.shape[:2]
        output = np.empty((height, width, 3), dtype=np.uint8)
        for row in range(height):
            rgb = image[row, :, :3].astype(np.uint16)
            luminance = (
                rgb[:, 0] * 77 + rgb[:, 1] * 150 + rgb[:, 2] * 29
            ) >> 8
            tile_row = np.tile(
                bayer[row % bayer.shape[0]],
                width // bayer.shape[1] + 1,
            )[:width]
            threshold = (tile_row + validated.bias / 255) * 255
            binary = luminance.astype(np.float32) >= threshold
            if validated.invert:
                binary = ~binary
            output[row] = (binary[:, None] * 255).astype(np.uint8)
        if image.shape[2] == 4:
            return np.dstack((output, image[:, :, 3]))
        return output
