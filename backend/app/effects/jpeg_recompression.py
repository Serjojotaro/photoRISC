from __future__ import annotations

import io

import numpy as np
from PIL import Image
from pydantic import Field

from app.effects.base import BaseEffect, StrictParams


class JPEGRecompressionParams(StrictParams):
    quality: int = Field(12, ge=1, le=100, title="Качество JPEG")
    passes: int = Field(1, ge=1, le=5, title="Количество проходов")
    subsampling: int = Field(2, ge=0, le=2, title="Субдискретизация")


class JPEGRecompressionEffect(BaseEffect):
    effect_id = "jpeg_recompression"
    display_name = "JPEG-рекомпрессия"
    description = "Повторно кодирует изображение в JPEG с выбранным качеством."
    category = "compression"
    params_model = JPEGRecompressionParams

    def apply(
        self,
        image: np.ndarray,
        params: dict,
        seed: int | None = None,
    ) -> np.ndarray:
        validated = JPEGRecompressionParams.model_validate(params)
        current = image
        has_alpha = image.shape[2] == 4
        alpha = image[:, :, 3].copy() if has_alpha else None
        for _ in range(validated.passes):
            buffer = io.BytesIO()
            Image.fromarray(current[:, :, :3]).save(
                buffer,
                format="JPEG",
                quality=validated.quality,
                subsampling=validated.subsampling,
            )
            buffer.seek(0)
            with Image.open(buffer) as compressed:
                current = np.array(compressed.convert("RGB"))
        if alpha is not None:
            return np.dstack((current, alpha))
        return current
