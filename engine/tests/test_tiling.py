import cv2
import numpy as np
import pytest

from pipeline.tiling import PAD_VALUE, load_image, tile_image


def random_image(height, width, seed=0):
    return np.random.default_rng(seed).integers(0, 255, (height, width, 3), dtype=np.uint8)


def test_exact_multiple_gives_full_grid():
    tiles = tile_image(random_image(448, 672))

    assert tiles.grid_shape == (2, 3)
    assert tiles.patches.shape == (6, 224, 224, 3)
    assert tiles.coords.tolist() == [[0, 0], [0, 1], [0, 2], [1, 0], [1, 1], [1, 2]]
    assert tiles.image_shape == (448, 672)


def test_patch_matches_source_region():
    image = random_image(448, 672)
    tiles = tile_image(image)

    for patch, (row, col) in zip(tiles.patches, tiles.coords):
        expected = image[row * 224:(row + 1) * 224, col * 224:(col + 1) * 224]
        np.testing.assert_array_equal(patch, expected)


def test_partial_edges_are_padded_white():
    image = random_image(300, 500)
    tiles = tile_image(image)

    assert tiles.grid_shape == (2, 3)
    last = tiles.patches[-1]  # bottom-right tile: rows 224..300, cols 448..500 are real
    np.testing.assert_array_equal(last[:76, :52], image[224:300, 448:500])
    assert (last[76:] == PAD_VALUE).all()
    assert (last[:, 52:] == PAD_VALUE).all()


def test_image_smaller_than_patch_gives_one_tile():
    tiles = tile_image(random_image(100, 150))

    assert tiles.grid_shape == (1, 1)
    assert tiles.patches.shape == (1, 224, 224, 3)


def test_custom_patch_size():
    tiles = tile_image(random_image(256, 256), patch_size=128)

    assert tiles.grid_shape == (2, 2)
    assert tiles.patches.shape == (4, 128, 128, 3)


@pytest.mark.parametrize("shape", [(224, 224), (224, 224, 4)])
def test_rejects_non_rgb(shape):
    with pytest.raises(ValueError):
        tile_image(np.zeros(shape, dtype=np.uint8))


def test_load_image_returns_rgb(tmp_path):
    rgb = np.zeros((10, 20, 3), dtype=np.uint8)
    rgb[..., 0] = 200  # red channel
    path = tmp_path / "slide.png"
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))

    np.testing.assert_array_equal(load_image(path), rgb)


def test_load_image_rejects_unreadable_file(tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"not an image")

    with pytest.raises(ValueError):
        load_image(path)
