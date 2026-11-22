from __future__ import annotations

from app.effects.base import BaseEffect
from app.effects.block_displacement import BlockDisplacementEffect
from app.effects.channel_shift import ChannelShiftEffect
from app.effects.horizontal_slicing import HorizontalSlicingEffect
from app.effects.jpeg_recompression import JPEGRecompressionEffect
from app.effects.noise import NoiseEffect
from app.effects.rgb_split import RGBSplitEffect
from app.effects.scanlines import ScanlinesEffect


_EFFECTS: tuple[BaseEffect, ...] = (
    RGBSplitEffect(),
    ChannelShiftEffect(),
    ScanlinesEffect(),
    NoiseEffect(),
    HorizontalSlicingEffect(),
    BlockDisplacementEffect(),
    JPEGRecompressionEffect(),
)

EFFECT_REGISTRY = {effect.effect_id: effect for effect in _EFFECTS}


def get_effect(effect_id: str) -> BaseEffect | None:
    return EFFECT_REGISTRY.get(effect_id)


def list_effects() -> tuple[BaseEffect, ...]:
    return _EFFECTS
