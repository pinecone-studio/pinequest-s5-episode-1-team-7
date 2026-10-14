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

export interface CaptureStatus {
  active: boolean
  source: string | null
}
