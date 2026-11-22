from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from app.effects import EFFECT_REGISTRY, get_effect


def sample_image(channels: int = 3) -> np.ndarray:
    y, x = np.mgrid[0:48, 0:64]
    rgb = np.dstack(
        (
            (x * 3 + y) % 256,
            (x + y * 4) % 256,
            (x * 2 + y * 2) % 256,
        )
    ).astype(np.uint8)
    if channels == 4:
        alpha = np.full((48, 64, 1), 180, dtype=np.uint8)
        return np.concatenate((rgb, alpha), axis=2)
    return rgb


def test_registry_contains_release_effects() -> None:
    assert set(EFFECT_REGISTRY) == {
        "bit_plane",
        "color_quantization",
        "datamosh_imitation",
        "displacement",
        "dithering",
        "feedback",
        "rgb_split",
        "channel_shift",
        "scanlines",
        "noise",
        "horizontal_slicing",
        "block_displacement",
        "interlacing",
        "jpeg_recompression",
        "pixel_sort",
        "posterize",
        "vhs_crt",
    }
    assert get_effect("missing") is None


@pytest.mark.parametrize("channels", [3, 4])
@pytest.mark.parametrize("effect_id", sorted(EFFECT_REGISTRY))
def test_every_effect_preserves_shape_and_input(effect_id: str, channels: int) -> None:
    effect = EFFECT_REGISTRY[effect_id]
    image = sample_image(channels)
    original = image.copy()
    result = effect.apply(image, effect.default_params(), seed=12345)

    assert result.shape == image.shape
    assert result.dtype == np.uint8
    assert np.array_equal(image, original)
    assert np.array_equal(result[:, :, 3], original[:, :, 3]) if channels == 4 else True


@pytest.mark.parametrize(
    "effect_id",
    [
        "noise",
        "horizontal_slicing",
        "block_displacement",
        "vhs_crt",
        "datamosh_imitation",
    ],
)
def test_random_effects_are_deterministic_for_seed(effect_id: str) -> None:
    effect = EFFECT_REGISTRY[effect_id]
    image = sample_image()
    params = effect.default_params()
    first = effect.apply(image, params, seed=9876)
    second = effect.apply(image, params, seed=9876)
    third = effect.apply(image, params, seed=9877)

    assert np.array_equal(first, second)
    assert not np.array_equal(first, third)


def test_rgb_split_shifts_channels_independently() -> None:
    effect = EFFECT_REGISTRY["rgb_split"]
    image = sample_image()
    params = {
        **effect.default_params(),
        "red_offset_x": 2,
        "blue_offset_x": -2,
        "green_offset_x": 0,
    }
    result = effect.apply(image, params)
    assert np.array_equal(result[:, 2:, 0], image[:, :-2, 0])
    assert np.array_equal(result[:, :-2, 2], image[:, 2:, 2])


def test_scanlines_darken_selected_rows() -> None:
    effect = EFFECT_REGISTRY["scanlines"]
    image = np.full((40, 40, 3), 200, dtype=np.uint8)
    result = effect.apply(
        image,
        {
            "spacing": 4,
            "thickness": 1,
            "intensity": 0.5,
            "orientation": "horizontal",
        },
    )
    assert int(result[0, 0, 0]) == 100
    assert int(result[1, 0, 0]) == 200


def test_invalid_effect_params_are_rejected() -> None:
    effect = EFFECT_REGISTRY["scanlines"]
    with pytest.raises(ValidationError):
        effect.validate_params({"spacing": 0, "intensity": 2})


def test_pixel_sort_orders_interval_by_selected_channel() -> None:
    effect = EFFECT_REGISTRY["pixel_sort"]
    image = np.zeros((4, 64, 3), dtype=np.uint8)
    image[:, :, 0] = np.tile(np.array([200, 30, 120, 70], dtype=np.uint8), 16)
    result = effect.apply(
        image,
        {
            "threshold_low": 0,
            "threshold_high": 255,
            "direction": "horizontal",
            "reverse": False,
            "criterion": "red",
        },
    )
    assert np.all(np.diff(result[0, :, 0].astype(int)) >= 0)


def test_posterize_and_dithering_limit_output_values() -> None:
    image = sample_image()
    posterized = EFFECT_REGISTRY["posterize"].apply(
        image,
        {"levels": 4, "blend": 1},
    )
    assert len(np.unique(posterized[:, :, :3])) <= 4

    dithered = EFFECT_REGISTRY["dithering"].apply(
        image,
        {"matrix": 4, "bias": 0, "invert": False},
    )
    assert set(np.unique(dithered[:, :, :3])).issubset({0, 255})
