from dataclasses import replace

import cv2
import numpy as np

from pipeline.heatmap import GREEN, RED, YELLOW, probability_colors, render_heatmap, save_heatmap
from pipeline.tiling import tile_image


def test_probability_colors_endpoints():
    colors = probability_colors(np.array([0.0, 0.5, 1.0]))

    np.testing.assert_array_equal(colors, np.stack([GREEN, YELLOW, RED]).astype(np.uint8))


def test_render_heatmap_colours_scored_tiles_and_hides_background():
    tiles = tile_image(np.zeros((300, 500, 3), dtype=np.uint8))  # 2x3 grid
    scored = replace(tiles, coords=np.array([[0, 0], [1, 2]]))  # as if masking kept 2 tiles

    layer = render_heatmap(scored, np.array([0.0, 1.0]))

    assert layer.shape == (300, 500, 4)
    np.testing.assert_array_equal(layer[10, 10], [*GREEN.astype(np.uint8), 255])
    np.testing.assert_array_equal(layer[290, 490], [*RED.astype(np.uint8), 255])
    assert layer[10, 300, 3] == 0  # tile (0, 1) was not scored -> transparent


def test_render_heatmap_with_no_tissue_is_fully_transparent():
    tiles = tile_image(np.zeros((224, 224, 3), dtype=np.uint8))
    empty = replace(tiles, coords=np.zeros((0, 2), dtype=int))

    assert (render_heatmap(empty, np.zeros(0))[..., 3] == 0).all()


def test_save_heatmap_round_trip(tmp_path):
    layer = np.zeros((20, 30, 4), dtype=np.uint8)
    layer[..., 0] = 230
    layer[..., 3] = 255
    path = tmp_path / "heatmap.png"

    save_heatmap(layer, path)

    saved = cv2.cvtColor(cv2.imread(str(path), cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA)
    np.testing.assert_array_equal(saved, layer)
