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
        "rgb_split",
        "channel_shift",
        "scanlines",
        "noise",
        "horizontal_slicing",
        "block_displacement",
        "jpeg_recompression",
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
    ["noise", "horizontal_slicing", "block_displacement"],
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
