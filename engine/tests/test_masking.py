import numpy as np

from pipeline.masking import equalize_lighting, filter_tissue_patches, tissue_fraction, tissue_mask
from pipeline.tiling import tile_image

WHITE = (245, 245, 245)
BLACK = (5, 5, 5)
TISSUE = (200, 120, 180)        # H&E-like pink/purple
LIGHT_TISSUE = (230, 170, 210)  # paler stain


def solid(height, width, color):
    return np.full((height, width, 3), color, dtype=np.uint8)


def noisy(image, seed=0):
    noise = np.random.default_rng(seed).integers(-4, 5, image.shape)
    return np.clip(image.astype(int) + noise, 0, 255).astype(np.uint8)


def test_blank_background_has_no_tissue():
    image = noisy(solid(448, 448, WHITE))

    assert not tissue_mask(image).any()
    assert len(filter_tissue_patches(tile_image(image), image).patches) == 0


def test_black_vignette_is_not_tissue():
    image = noisy(solid(448, 448, WHITE))
    image[:, :224] = noisy(solid(448, 224, BLACK))

    assert len(filter_tissue_patches(tile_image(image), image).patches) == 0


def test_tissue_region_is_kept():
    image = noisy(solid(448, 448, WHITE))
    image[:, :224] = noisy(solid(448, 224, TISSUE))  # left column of tiles is tissue

    kept = filter_tissue_patches(tile_image(image), image)

    assert kept.coords.tolist() == [[0, 0], [1, 0]]
    assert kept.grid_shape == (2, 2)  # grid is unchanged so the heatmap can be rebuilt


def test_all_tissue_image_keeps_both_stain_shades():
    image = noisy(solid(448, 448, TISSUE))
    image[:, 224:] = noisy(solid(448, 224, LIGHT_TISSUE))

    assert len(filter_tissue_patches(tile_image(image), image).patches) == 4


def test_tissue_fraction_counts_padding_as_background():
    image = solid(300, 300, TISSUE)  # 2x2 grid; only 76x76 of the last tile is real
    tiles = tile_image(image)

    fractions = tissue_fraction(tissue_mask(image), tiles)

    np.testing.assert_allclose(fractions, [1.0, 76 / 224, 76 / 224, (76 / 224) ** 2])


def test_min_fraction_threshold():
    image = solid(448, 224, WHITE)
    image[:100] = TISSUE  # top tile is 100/224 ≈ 45% tissue

    tiles = tile_image(image)
    assert len(filter_tissue_patches(tiles, image).patches) == 0
    assert len(filter_tissue_patches(tiles, image, min_fraction=0.4).patches) == 1


def test_equalize_lighting_boosts_contrast():
    gradient = np.tile(np.linspace(100, 140, 256, dtype=np.uint8), (256, 1))
    image = np.stack([gradient] * 3, axis=-1)

    result = equalize_lighting(image)

    assert result.shape == image.shape and result.dtype == np.uint8
    assert result.std() > image.std()


YELLOW_GLASS = (235, 232, 200)   # white background through a phone with a yellow cast
GREEN_GLASS = (220, 238, 222)    # ... with a green cast
PALE_EOSIN = (238, 214, 226)     # faint pink tissue, low saturation
CAST_PINK = (230, 228, 215)      # pale tissue seen through the same yellow cast


def test_tinted_phone_background_is_not_tissue():
    for glass in (YELLOW_GLASS, GREEN_GLASS):
        image = noisy(solid(448, 448, glass))
        image[:, :224] = noisy(solid(448, 224, TISSUE))

        kept = filter_tissue_patches(tile_image(image), image)
        assert kept.coords.tolist() == [[0, 0], [1, 0]], glass


def test_pale_tissue_is_kept_next_to_strong_stain():
    # The old saturation threshold followed the strong stain up and dropped pale tissue.
    image = noisy(solid(448, 672, WHITE))
    image[:, :224] = noisy(solid(448, 224, (150, 60, 160)))   # dense haematoxylin
    image[:, 224:448] = noisy(solid(448, 224, PALE_EOSIN))

    kept = filter_tissue_patches(tile_image(image), image)
    assert sorted(c for _, c in kept.coords.tolist()) == [0, 0, 1, 1]


def test_cast_correction_keeps_tissue_seen_through_a_yellow_cast():
    image = noisy(solid(448, 448, YELLOW_GLASS))
    image[:, :224] = noisy(solid(448, 224, CAST_PINK))  # green is not below blue here

    kept = filter_tissue_patches(tile_image(image), image)
    assert kept.coords.tolist() == [[0, 0], [1, 0]]


def test_all_pink_photo_without_background_is_kept():
    # No glass to estimate a cast from: the pale pink must not be taken for background.
    image = noisy(solid(448, 448, PALE_EOSIN))

    assert len(filter_tissue_patches(tile_image(image), image).patches) == 4


def test_dark_grey_vignette_of_a_tinted_photo_is_not_tissue():
    image = noisy(solid(448, 448, YELLOW_GLASS))
    image[:, 224:] = noisy(solid(448, 224, (80, 79, 68)))  # dim edge of the eyepiece, same cast

    assert len(filter_tissue_patches(tile_image(image), image).patches) == 0
