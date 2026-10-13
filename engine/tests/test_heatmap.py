from dataclasses import replace

import cv2
import numpy as np

from pipeline.heatmap import GREEN, HOTSPOT_COLOR, HOTSPOT_PROB, RED, YELLOW, probability_colors, render_heatmap, save_heatmap
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


def grid_tiles(rows, cols, size=224):
    return tile_image(np.zeros((rows * size, cols * size, 3), dtype=np.uint8))


def is_hotspot(pixel):
    return tuple(pixel) == (*HOTSPOT_COLOR, 255)


def test_probabilities_are_interpolated_between_scored_tiles():
    tiles = grid_tiles(1, 2)

    layer = render_heatmap(tiles, np.array([0.0, 0.6]))

    middle = layer[112, 224]  # boundary between the two tile centres: P ~ 0.3
    assert GREEN[0] < middle[0] < YELLOW[0]
    np.testing.assert_array_equal(layer[112, 112, :3], GREEN.astype(np.uint8))


def test_unscored_tiles_do_not_pull_probability_down():
    tiles = grid_tiles(1, 2)
    one = replace(tiles, coords=np.array([[0, 0]]))

    layer = render_heatmap(one, np.array([0.6]))

    np.testing.assert_array_equal(layer[112, 200, :3], probability_colors(np.array([0.6]))[0])
    assert layer[112, 300, 3] == 0


def test_tissue_mask_limits_the_coloured_area():
    tiles = grid_tiles(1, 1)
    tissue = np.zeros((224, 224), dtype=bool)
    tissue[:, :100] = True

    layer = render_heatmap(tiles, np.array([0.2]), tissue)

    assert layer[112, 50, 3] == 255
    assert layer[112, 200, 3] == 0


def test_confident_regions_get_a_bright_outline():
    tiles = grid_tiles(3, 3)
    probs = np.full(9, 0.1)
    probs[4] = 0.99  # centre tile

    layer = render_heatmap(tiles, probs)

    hot = np.array([is_hotspot(px) for px in layer[336, :]])  # middle row
    assert hot.any()
    assert not hot[:150].any() and not hot[-150:].any()  # outline only around the centre
    assert not is_hotspot(layer[336, 336])  # inside the region stays colour-coded


def test_no_outline_below_hotspot_probability():
    tiles = grid_tiles(3, 3)
    layer = render_heatmap(tiles, np.full(9, HOTSPOT_PROB - 0.05))

    assert not (layer[..., :3] == HOTSPOT_COLOR).all(axis=-1).any()
