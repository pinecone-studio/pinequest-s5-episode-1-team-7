# Demo photos

Test photos for demoing the app: real lymph-node tissue from the PCam test set, arranged as phone-through-eyepiece photos.

| File | What it shows | Calibrated result* | Uncalibrated result |
|---|---|---|---|
| `00-stage-micrometer.jpg` | Stage micrometer, 0–1000 µm scale, for the calibration screen | – | – |
| `01-normal-lymph-node.jpg` | Normal lymph node only | **38.7, green** | 32.7, green |
| `02-micro-metastasis.jpg` | 2 tumour patches (a micro-metastasis) | **78.4, yellow** | 48.4, green |
| `03-small-metastasis.jpg` | A small tumour region (16 of 192 patches) | **87.6, red** | 50.9, green |
| `04-large-metastasis.jpg` | A large tumour region (44 of 192 patches) | **89.9, red** | 73.8, yellow |

\*Measured with the shipped model (`engine/model/model_fp32.onnx`) and the colour-based tissue mask (15 Oct), at 0.972 µm/px, through `analyze_slide`, the function the backend calls. The flag cut-offs are red ≥ 81 and yellow ≥ 70.

## How to use them in a demo
1. **Calibrate:** in the upload panel, click **Тохиргоо калибровк хийх / Calibrate a setup**.
   - Name the setup, e.g. "Demo scope", and choose objective **10x**.
   - Choose `00-stage-micrometer.jpg`, click the **0** and **1000** ticks, and enter **1000** µm. The app should show about **0.97 µm/px**. Save the setup.
2. **Upload:** upload the four slide photos with that setup and objective **10x**.
   - Mark `01-normal-lymph-node` as **Urgent** and the others as **Routine**.
   - The worklist sorts by AI risk: large → small → micro → normal. The "Urgent" normal slide drops to the bottom, behind three "Routine" metastases.
3. **Open a red slide:** the heatmap's hotspot sits on the tumour region.
4. **Optional: why calibration matters.** Upload `03-small-metastasis` **without** choosing a setup. It is scored green (missed) and the slide shows the uncalibrated warning. With calibration it is red.

## How they were made
`engine/training/make_demo_photos.py` downloads one PCam test shard (~376 MB, checksum-verified) and builds the photos:

```bash
cd engine && python -m training.make_demo_photos
```

- PCam has no whole slides, so each photo is a 12 × 16 grid of 96 px test patches (~0.97 µm/px), placed in a round eyepiece-style field. Tumour patches form one contiguous region, so the heatmap shows a clear hotspot.
- Patches were picked where the model agrees confidently with the PCam label (P ≤ 0.05 for normal, P ≥ 0.95 for tumour). The tumour region sizes and random seeds were chosen so that each photo's flag is clear of the cut-offs after the backend re-saves the JPEG.
- **These photos show the workflow. They are not an accuracy test.** For accuracy, see `engine/README.md` and the model card.
- If the model or the flag thresholds change, run the script again and update the results table above.

PCam (PatchCamelyon, Veeling et al. 2018) is licensed CC0.
