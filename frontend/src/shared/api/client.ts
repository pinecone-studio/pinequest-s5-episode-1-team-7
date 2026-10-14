import type {
  CaptureStatus,
  Decision,
  Indication,
  IngestResult,
  ModelInfo,
  Objective,
  QueueSort,
  SetupProfile,
  Slide,
  SlideEvent,
  SlideState,
} from './types.ts'

/**
 * Backend origin, in order of precedence:
 * - the desktop app's backend, passed in by Electron (electron/preload.cts), on a free local port;
 * - VITE_API_BASE at build time, e.g. http://127.0.0.1:8000 for a static build (the backend's CORS allows it);
 * - /api in development, which Vite proxies to the backend (see vite.config.ts).
 */
export const API_BASE = (window.triageDesktop?.apiBase ?? import.meta.env.VITE_API_BASE ?? '/api').replace(/\/+$/, '')

/** A failed request. `status` is the HTTP status, or 0 when the backend could not be reached. */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** FastAPI's `detail`: a message string, or a list of validation errors. */
function detailMessage(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d?.msg).filter(Boolean).join('; ') || undefined
  return undefined
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(API_BASE + path, init)
  } catch (err) {
    throw new ApiError(err instanceof Error ? err.message : String(err), 0)
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(detailMessage(body.detail) ?? `${res.status} ${res.statusText}`, res.status)
  }
  return res.json() as Promise<T>
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: 'POST',
    ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  })

export const api = {
  health: () => request<{ status: string }>('/health'),
  /** Worklist: queued slides, by risk (manual priority first) or oldest first. */
  queue: (sort: QueueSort = 'risk') => request<Slide[]>(`/queue?sort=${sort}`),
  /** Every slide, newest first; `state` narrows to one state. */
  slides: (state?: SlideState) => request<Slide[]>(`/slides${state ? `?state=${state}` : ''}`),
  slide: (id: number | string) => request<Slide>(`/slides/${id}`),
  events: (id: number | string) => request<SlideEvent[]>(`/slides/${id}/events`),
  imageUrl: (id: number | string) => `${API_BASE}/slides/${id}/image`,
  heatmapUrl: (id: number | string) => `${API_BASE}/slides/${id}/heatmap`,
  /** Multipart: `file`, optional `patient_id`, `indication`. */
  ingest: (form: FormData) => request<IngestResult>('/ingest', { method: 'POST', body: form }),
  /** Pathologist selects the slide: queued -> under_review. */
  open: (id: number) => post<Slide>(`/slides/${id}/open`),
  /** Archives an under-review slide with the pathologist's decision. */
  decide: (id: number, decision: Decision) => post<Slide>(`/slides/${id}/action`, { action: decision }),
  /** Manual priority 0–1; an under-review slide goes back to the worklist. */
  reassignPriority: (id: number, priority: number) =>
    post<Slide>(`/slides/${id}/action`, { action: 'reassign_priority', priority }),
  retry: (id: number) => post<Slide>(`/slides/${id}/retry`),
  /** Live MJPEG stream of the connected camera, for an <img src> (backend: GET /capture/preview). */
  capturePreviewUrl: () => `${API_BASE}/capture/preview`,
  captureStatus: () => request<CaptureStatus>('/capture/status'),
  captureStart: (source: string) => post<CaptureStatus>('/capture/start', { source }),
  captureStop: () => post<CaptureStatus>('/capture/stop'),
  captureSnapshot: (body: { patient_id?: string; indication: Indication; setup_id?: number; objective?: Objective }) =>
    post<IngestResult>('/capture/snapshot', body),
  /** Model card + live model file/provider status (About the AI). */
  model: () => request<ModelInfo>('/model'),
  /** Magnification-calibration setups (issue #35). */
  setups: () => request<SetupProfile[]>('/setups'),
  setup: (id: number) => request<SetupProfile>(`/setups/${id}`),
  createSetup: (body: { name: string; um_per_px: number; calibration_objective: string; phone_resolution?: string }) =>
    request<SetupProfile>('/setups', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  deleteSetup: (id: number) => request<void>(`/setups/${id}`, { method: 'DELETE' }),
}
