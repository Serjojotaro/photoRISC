from __future__ import annotations

import numpy as np
from PIL import Image
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class ColorQuantizationParams(StrictParams):
    colors: int = Field(16, ge=2, le=256, title="Количество цветов")
    dither: bool = Field(False, title="Дизеринг палитры")


class ColorQuantizationEffect(BaseEffect):
    effect_id = "color_quantization"
    display_name = "Квантование цвета"
    description = "Приводит изображение к ограниченной адаптивной палитре."
    category = "color"
    params_model = ColorQuantizationParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = ColorQuantizationParams.model_validate(params)
        source = Image.fromarray(image[:, :, :3])
        quantized = source.quantize(
            colors=validated.colors,
            method=Image.Quantize.MEDIANCUT,
            dither=Image.Dither.FLOYDSTEINBERG if validated.dither else Image.Dither.NONE,
        ).convert("RGB")
        rgb = np.array(quantized)
        if image.shape[2] == 4:
            return np.dstack((rgb, image[:, :, 3]))
        return rgb
