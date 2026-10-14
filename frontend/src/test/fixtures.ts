import type { Slide } from '../shared/api/types.ts'

/** A scored, queued slide; override what the test cares about. */
export function slide(overrides: Partial<Slide> & Pick<Slide, 'id'>): Slide {
  return {
    local_hash: 'a1b2c3d4e5f60718',
    indication: 'Routine',
    state: 'queued',
    risk_score: 0.5,
    risk_flag: 'yellow',
    priority_override: null,
    has_heatmap: true,
    num_patches: 120,
    inference_ms: 290,
    decision: null,
    error: null,
    setup_id: null,
    objective: null,
    um_per_px: null,
    scale_warning: null,
    model_name: null,
    model_sha256: null,
    created_at: '2026-10-13T08:00:00.000Z',
    updated_at: '2026-10-13T08:01:00.000Z',
    ...overrides,
  }
}
