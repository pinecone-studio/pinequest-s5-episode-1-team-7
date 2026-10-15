/**
 * Heatmap overlay colours, shared source for the viewer legend.
 *
 * These MUST match the engine exactly (engine/pipeline/heatmap.py:
 * GREEN, YELLOW, RED, HOTSPOT_COLOR). The overlay PNG arrives with these
 * saturated colours, so the legend explains what's actually on screen.
 *
 * Engine follow-up (Member 1): publish this palette next to heatmap.py
 * (e.g. a small JSON or the model card) and have the backend serve it;
 * the legend should then read those values instead of these constants.
 */
export const HEATMAP_LOW = '#00c800' // engine GREEN  (0, 200, 0)
export const HEATMAP_MID = '#ffd200' // engine YELLOW (255, 210, 0)
export const HEATMAP_HIGH = '#e60000' // engine RED    (230, 0, 0)
export const HEATMAP_HOTSPOT = '#00e6ff' // engine HOTSPOT_COLOR (0, 230, 255)
