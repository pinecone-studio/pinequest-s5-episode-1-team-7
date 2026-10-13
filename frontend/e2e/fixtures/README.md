# Browser-test fixtures

- `slide.jpg`: a demo eyepiece-style photo composed from H&E patches of the
  [NCT-CRC-HE / CRC-VAL-HE-7K](https://zenodo.org/records/1214456) dataset (Kather et al., 2018, CC BY 4.0),
  scaled to 896 × 672.
- `heatmap.png`: the heatmap our engine (`engine.pipeline.analyze_slide`) produced for `slide.jpg`.

The mocked API in `../mockBackend.ts` serves them for every slide. The full-stack test uploads `slide.jpg` to the real backend.
