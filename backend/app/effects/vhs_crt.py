from __future__ import annotations

import numpy as np
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class VHSCRTParams(StrictParams):
    intensity: float = Field(0.55, ge=0, le=1, title="Интенсивность")
    chroma_shift: int = Field(4, ge=0, le=40, title="Сдвиг каналов")
    noise_strength: float = Field(10, ge=0, le=60, title="Шум")
    scanline_opacity: float = Field(0.25, ge=0, le=0.9, title="Сканлайны")
    vignette: float = Field(0.35, ge=0, le=1, title="Виньетка")


class VHSCRTEffect(BaseEffect):
    effect_id = "vhs_crt"
    display_name = "VHS / CRT"
    description = "Смешивает хроматические ореолы, шум, сканлайны и виньетку."
    category = "analog"
    uses_seed = True
    params_model = VHSCRTParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = VHSCRTParams.model_validate(params)
        rng = np.random.default_rng(seed)
        output = np.empty_like(image[:, :, :3])
        height, width = image.shape[:2]
        rows = np.arange(image.shape[0])
        jitter = np.rint(
            validated.intensity
            * 2
            * np.sin(rows / 7.0)
        ).astype(int)
        x_weights = np.ones(width, dtype=np.float32)
        if validated.vignette:
            normalized_x = ((np.arange(width) - width / 2) / (width / 2)) ** 2
            x_weights = normalized_x.astype(np.float32)

        for row in range(height):
            current = image[row, :, :3].astype(np.float32)
            if validated.chroma_shift:
                current[:, 0] = np.roll(
                    current[:, 0],
                    validated.chroma_shift,
                    axis=0,
                )
                current[:, 2] = np.roll(
                    current[:, 2],
                    -validated.chroma_shift,
                    axis=0,
                )
            current += rng.normal(
                0,
                validated.noise_strength * validated.intensity,
                current.shape,
            )
            shift = jitter[row]
            if shift:
                current = np.roll(current, shift, axis=0)
            if validated.scanline_opacity and row % 3 == 0:
                current *= 1 - validated.scanline_opacity
            if validated.vignette:
                normalized_y = ((row - height / 2) / (height / 2)) ** 2
                radial = np.sqrt(x_weights + normalized_y)
                current *= np.clip(
                    1 - validated.vignette * radial / 1.414,
                    0,
                    1,
                )[:, None]
            output[row] = np.clip(current, 0, 255).astype(np.uint8)

        rgb = output
        if image.shape[2] == 4:
            return np.dstack((rgb, image[:, :, 3]))
        return rgb
