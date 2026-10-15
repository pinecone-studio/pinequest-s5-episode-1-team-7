/** Shapes of the team FastAPI backend (backend/app/schemas.py, backend/README.md). */

/** Slide state machine, TDD 3.2 (backend/app/states.py). */
export type SlideState =
  | 'new'
  | 'image_processing'
  | 'ai_running'
  | 'scored'
  | 'queued'
  | 'under_review'
  | 'archived'
  | 'failed'

/** Pipeline states before a slide reaches the worklist. */
export const PROCESSING_STATES: SlideState[] = ['new', 'image_processing', 'ai_running', 'scored']

/** AI risk flag (TDD 6.1): red = high probability, yellow = moderate, green = low. */
export type RiskFlag = 'red' | 'yellow' | 'green'
export type Indication = 'Routine' | 'Urgent'
export type Decision = 'confirm_malignancy' | 'mark_benign' | 'request_biopsy'
export type SlideAction = Decision | 'reassign_priority'
export type QueueSort = 'risk' | 'time'

/** Microscope objectives the µm/px picker offers (backend accepts any `Nx` label). */
export const OBJECTIVES = ['10x', '20x', '40x'] as const
export type Objective = (typeof OBJECTIVES)[number]

/** A calibrated microscope + phone + adapter setup (backend/app/setups.py, issue #35). */
export interface SetupProfile {
  id: number
  /** Technician's name for the setup, unique. */
  name: string
  /** µm per pixel at the calibration objective. */
  um_per_px: number
  calibration_objective: string
  phone_resolution: string | null
  created_at: string
}

export interface Slide {
  id: number
  /** Salted hash of the patient ID; the raw ID is never stored (TDD 7.1). */
  local_hash: string
  indication: Indication
  state: SlideState
  /** S_slide, 0–1. */
  risk_score: number | null
  risk_flag: RiskFlag | null
  /** Manual priority (0–1) set by a pathologist; outranks every AI score in the queue. */
  priority_override: number | null
  has_heatmap: boolean
  num_patches: number | null
  inference_ms: number | null
  decision: Decision | null
  error: string | null
  /** Magnification calibration, issue #35 (all null when the slide predates it or no setup was picked). */
  setup_id: number | null
  objective: string | null
  /** µm/px the photo was analysed at; null means captured resolution (model may misread scale). */
  um_per_px: number | null
  /** Engine scale report, e.g. "no_scale_info" (shown as a warning, not an error). */
  scale_warning: string | null
  /** Which model scored the slide (About the AI): file name, or "stub" for the demo scorer. */
  model_name: string | null
  /** SHA-256 of the model file that scored the slide; null for the stub. */
  model_sha256: string | null
  /** Which organ's model scored the slide (issue #53); null on slides from before organs existed. */
  organ: string | null
  created_at: string
  updated_at: string
}

/** One state change in a slide's audit log. */
export interface SlideEvent {
  from_state: SlideState | null
  to_state: SlideState
  /** e.g. an action code, "priority reassigned", "retry", "interrupted by restart". */
  note: string | null
  at: string
}

export interface IngestResult {
  id: number
  state: SlideState
}

/** The engine's model card (engine/model/model_card.json) with live file/provider status. */
export interface ModelCard {
  name: string
  version: string
  file: { name: string; sha256: string; size_bytes: number; size_mb: number; committed: string | null }
  architecture: { name: string; params: number; input_px: number; input_scale_um_per_px: number }
  provenance: {
    dataset: string
    backbone: string
    training: string
    distilled_from: string
    date_trained: string | null
    export_metadata: Record<string, string>
  }
  runtime: {
    offline: boolean
    runs_on: string
    providers_preference: string[]
    measured_per_slide_s: { value: number; context: string }
  }
  patch_metrics: {
    split: string
    threshold: number
    auc: number
    accuracy: number
    sensitivity: number
    specificity: number
    at_90_sensitivity: { threshold: number; sensitivity: number; specificity: number }
  }
  slide_metrics: {
    formula: string
    thresholds: { red: number; yellow: number }
    tuned: string | null
    tuned_commit: string | null
    normal_slides: { red: number; yellow_or_red: number }
    tumour_fractions: Record<string, { auc: number | null; red: number; yellow_or_red: number }>
  }
  plism: {
    at: string
    source: string
    metric: string
    scanners: Record<string, number>
    phones: Record<string, number>
    other_tissues_false_alarm: { min: number; max: number; note: string }
  }
  /**
   * The shipped model first, then alternatives. test_auc is on the card's own test set; older cards
   * (before 15 Oct) used pcam_auc instead.
   */
  comparison: {
    model: string
    test_auc?: number | null
    pcam_auc?: number | null
    size_mb: number | null
    per_slide_s: number | null
    /** For estimated speeds (published models): the low and high ends of the estimate. */
    per_slide_range_s?: [number, number] | null
    speed_estimated?: boolean
    /** Runs on this PC: yes (within the TDD's 1.5 s per slide), slow (runs, but slower), no. */
    local?: 'yes' | 'slow' | 'no' | null
    /** Older cards only; replaced by local. */
    clinic_pc?: boolean | null
    note: string
  }[]
  literature: { note: string; source?: string; url?: string; baselines: unknown[] }
  limitations: string[]
  generated: { at: string; repo_commit: string | null; generator: string }
}

export interface ModelInfo {
  organ: string | null
  card: ModelCard | null
  file: { path: string | null; name: string | null; exists: boolean; sha256: string | null; matches_card: boolean }
  provider: string | null
}
