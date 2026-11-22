from __future__ import annotations

from app.effects.base import BaseEffect
from app.effects.bit_plane import BitPlaneEffect
from app.effects.block_displacement import BlockDisplacementEffect
from app.effects.channel_shift import ChannelShiftEffect
from app.effects.color_quantization import ColorQuantizationEffect
from app.effects.datamosh_imitation import DatamoshImitationEffect
from app.effects.displacement import DisplacementEffect
from app.effects.dithering import DitheringEffect
from app.effects.feedback import FeedbackEffect
from app.effects.horizontal_slicing import HorizontalSlicingEffect
from app.effects.interlacing import InterlacingEffect
from app.effects.jpeg_recompression import JPEGRecompressionEffect
from app.effects.noise import NoiseEffect
from app.effects.pixel_sort import PixelSortEffect
from app.effects.posterize import PosterizeEffect
from app.effects.rgb_split import RGBSplitEffect
from app.effects.scanlines import ScanlinesEffect
from app.effects.vhs_crt import VHSCRTEffect


_EFFECTS: tuple[BaseEffect, ...] = (
    RGBSplitEffect(),
    ChannelShiftEffect(),
    ScanlinesEffect(),
    NoiseEffect(),
    HorizontalSlicingEffect(),
    BlockDisplacementEffect(),
    JPEGRecompressionEffect(),
    PixelSortEffect(),
    DisplacementEffect(),
    BitPlaneEffect(),
    PosterizeEffect(),
    ColorQuantizationEffect(),
    VHSCRTEffect(),
    InterlacingEffect(),
    FeedbackEffect(),
    DitheringEffect(),
    DatamoshImitationEffect(),
)

EFFECT_REGISTRY = {effect.effect_id: effect for effect in _EFFECTS}


def get_effect(effect_id: str) -> BaseEffect | None:
    return EFFECT_REGISTRY.get(effect_id)


def list_effects() -> tuple[BaseEffect, ...]:
    return _EFFECTS
