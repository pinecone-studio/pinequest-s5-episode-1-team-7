import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { test as base, type Page, type Route } from '@playwright/test'

import type { Slide, SlideState } from '../src/shared/api/types.ts'

const fixture = (name: string) => readFileSync(fileURLToPath(new URL(`fixtures/${name}`, import.meta.url)))
/** A tissue photo and a matching RGBA heatmap, served for every slide. */
const PHOTO = fixture('slide.jpg')
const HEATMAP = fixture('heatmap.png')

/** Allowed transitions, mirroring backend/app/states.py. */
const ALLOWED: Record<SlideState, SlideState[]> = {
  new: ['image_processing', 'failed'],
  image_processing: ['ai_running', 'failed'],
  ai_running: ['scored', 'failed'],
  scored: ['queued', 'failed'],
  queued: ['under_review'],
  under_review: ['archived', 'queued'],
  archived: [],
  failed: ['new'],
}

export function makeSlide(id: number, overrides: Partial<Slide> = {}): Slide {
  return {
    id,
    local_hash: `${id}f3a9c0de41b7726`.slice(0, 16),
    indication: 'Routine',
    state: 'queued',
    risk_score: 0.1,
    risk_flag: 'green',
    priority_override: null,
    has_heatmap: true,
    num_patches: 128,
    inference_ms: 290,
    decision: null,
    error: null,
    setup_id: null,
    objective: null,
    um_per_px: null,
    scale_warning: null,
    model_name: null,
    model_sha256: null,
    organ: null,
    created_at: '2026-10-09T08:00:00.000Z',
    updated_at: '2026-10-09T08:01:00.000Z',
    ...overrides,
  }
}

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

/** In-memory stand-in for the team FastAPI backend (backend/README.md), installed with page.route. */
export interface MockSetup {
  id: number
  name: string
  um_per_px: number
  calibration_objective: string
  phone_resolution: string | null
  created_at: string
}

/** Minimal model card for GET /model (backend/app/routers/model.py); the page renders labels from it. */
export const mockModelInfo = {
  card: {
    name: 'PCam MobileNetV3-Small, Hibou-B-distilled',
    version: 'model_fp32.onnx',
    file: { name: 'model_fp32.onnx', sha256: 'abc123', size_bytes: 6421804, size_mb: 6.42, committed: null },
    architecture: { name: 'MobileNetV3-Small', params: 1512836, input_px: 224, input_scale_um_per_px: 0.42 },
    provenance: {
      dataset: 'PatchCamelyon (PCam)',
      backbone: 'ImageNet-pretrained MobileNetV3-Small',
      training: 'fine-tuned on PCam',
      distilled_from: 'hibou-b',
      date_trained: null,
      export_metadata: {},
    },
    runtime: {
      offline: true,
      runs_on: 'this clinic PC only',
      providers_preference: ['CPUExecutionProvider'],
      measured_per_slide_s: { value: 0.1, context: 'reference PC' },
    },
    patch_metrics: {
      split: 'PCam test',
      threshold: 0.5,
      auc: 0.9687,
      accuracy: 0.8777,
      sensitivity: 0.773,
      specificity: 0.9822,
      at_90_sensitivity: { threshold: 0.1816, sensitivity: 0.8707, specificity: 0.9481 },
    },
    slide_metrics: {
      formula: 'sigmoid(mean(top-3 patch log-odds) / 4)',
      thresholds: { red: 0.81, yellow: 0.7 },
      tuned: null,
      tuned_commit: null,
      normal_slides: { red: 0.004, yellow_or_red: 0.058 },
      tumour_fractions: { tumour_5pct: { auc: 0.9759, red: 0.665, yellow_or_red: 0.9185 } },
    },
    plism: {
      at: '0.6x',
      source: 'plism results',
      metric: 'share flagged',
      scanners: { GT450: 0.019 },
      phones: { redmi: 0.0 },
      other_tissues_false_alarm: { min: 0.217, max: 0.354, note: 'not valid' },
    },
    comparison: [{ model: 'Direct model', pcam_auc: 0.9604, size_mb: 6.42, per_slide_s: 0.1, note: 'previous' }],
    literature: { note: 'none recorded', baselines: [] },
    limitations: ['Prioritisation aid only.'],
    generated: { at: '2026-10-14T00:00:00+00:00', repo_commit: null, generator: 'make_model_card.py' },
  },
  file: { path: '/models/model_fp32.onnx', name: 'model_fp32.onnx', exists: true, sha256: 'abc123', matches_card: true },
  provider: 'CPUExecutionProvider',
}

export class MockBackend {
  slides: Slide[]
  setups: MockSetup[] = []
  /** Every POST the dashboard sent: path and JSON or form body. */
  readonly posts: { path: string; body: Record<string, unknown> }[] = []

  constructor(slides: Slide[]) {
    this.slides = slides
  }

  get(id: number) {
    return this.slides.find((s) => s.id === id)!
  }

  private move(s: Slide, to: SlideState) {
    if (!ALLOWED[s.state].includes(to)) throw new Error(`${s.state} -> ${to} is not allowed`)
    s.state = to
    s.updated_at = new Date().toISOString()
  }

  /** GET /queue?sort=risk: by priority (a manual priority replaces the score; it wins ties); time: oldest first. `organ` narrows; null-organ slides count as lymph_node. */
  private queue(sort: string | null, organ: string | null) {
    const queued = this.slides.filter(
      (s) => s.state === 'queued' && (organ == null || s.organ === organ || (s.organ == null && organ === 'lymph_node')),
    )
    if (sort === 'time') return queued.sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id)
    return queued.sort(
      (a, b) =>
        (b.priority_override ?? b.risk_score ?? 0) - (a.priority_override ?? a.risk_score ?? 0) ||
        Number(b.priority_override != null) - Number(a.priority_override != null) ||
        a.created_at.localeCompare(b.created_at),
    )
  }

  private ingest(fields: Record<string, string>) {
    const setupId = fields.setup_id === undefined || fields.setup_id === '' ? null : Number(fields.setup_id)
    const objective = fields.objective || null
    const organ = fields.organ || 'lymph_node'
    if (!['lymph_node', 'colon'].includes(organ)) throw new Error(`no AI model for organ '${organ}'`)
    let umPerPx: number | null = null
    if (objective && setupId == null) throw new Error('objective needs a setup_id (calibrate a setup first)')
    if (setupId != null) {
      const setup = this.setups.find((s) => s.id === setupId)
      if (!setup) throw new Error(`unknown setup_id: ${setupId}`)
      umPerPx = objective ? (setup.um_per_px * parseMag(setup.calibration_objective)) / parseMag(objective) : setup.um_per_px
    }
    const slide = makeSlide(Math.max(0, ...this.slides.map((s) => s.id)) + 1, {
      local_hash: 'feedc0ffee123456',
      indication: fields.indication === 'Urgent' ? 'Urgent' : 'Routine',
      state: 'ai_running',
      risk_score: null,
      risk_flag: null,
      has_heatmap: false,
      num_patches: null,
      inference_ms: null,
      setup_id: setupId,
      objective,
      um_per_px: umPerPx,
      organ,
      created_at: new Date().toISOString(),
    })
    this.slides.push(slide)
    return { id: slide.id, state: 'new' }
  }

  async install(page: Page) {
    // Only /api/...: a broad '**/slides/**' glob would also catch the dashboard's own /slides/:id pages.
    await page.route(
      (url) => url.pathname.startsWith('/api/'),
      async (route) => {
        const request = route.request()
        const url = new URL(request.url())
        const path = url.pathname.replace(/^\/api/, '')
        const method = request.method()
        const [, , idText, sub] = path.split('/') // /slides/{id}/{sub}
        const slide = path.startsWith('/slides/') ? this.slides.find((s) => s.id === Number(idText)) : undefined

        if (method === 'POST') {
          const isForm = (request.headers()['content-type'] ?? '').startsWith('multipart/')
          const body = isForm ? multipartFields(request.postDataBuffer()) : ((request.postDataJSON() as Record<string, unknown>) ?? {})
          this.posts.push({ path, body })
        }

        if (path === '/health') return json(route, { status: 'ok' })
        if (path === '/organs') return json(route, ['lymph_node', 'colon'])
        if (path === '/model') {
          const organ = url.searchParams.get('organ')
          if (organ && !['lymph_node', 'colon'].includes(organ)) {
            return json(route, { detail: `no AI model for organ '${organ}'` }, 404)
          }
          const name = organ === 'colon' ? 'CRC MobileNetV3-Small, Hibou-B-distilled' : mockModelInfo.card.name
          return json(route, { ...mockModelInfo, organ: organ ?? 'lymph_node', card: { ...mockModelInfo.card, name } })
        }
        if (path === '/queue') {
          return json(route, this.queue(url.searchParams.get('sort'), url.searchParams.get('organ')))
        }
        if (path === '/slides') {
          const state = url.searchParams.get('state')
          const organ = url.searchParams.get('organ')
          const list = this.slides.filter(
            (s) =>
              (!state || s.state === state) &&
              (organ == null || s.organ === organ || (s.organ == null && organ === 'lymph_node')),
          )
          return json(route, [...list].sort((a, b) => b.created_at.localeCompare(a.created_at)))
        }
        if (path === '/ingest' && method === 'POST') {
          try {
            return json(route, this.ingest(this.posts.at(-1)!.body as Record<string, string>), 202)
          } catch (err) {
            return json(route, { detail: (err as Error).message }, 422)
          }
        }
        if (path === '/setups' && method === 'GET') return json(route, this.setups)
        if (path === '/setups' && method === 'POST') {
          const body = this.posts.at(-1)!.body as { name?: string; um_per_px?: number; calibration_objective?: string; phone_resolution?: string }
          if (!body.name?.trim() || !(body.um_per_px! > 0) || !parseMag(body.calibration_objective ?? '')) {
            return json(route, { detail: 'invalid setup' }, 422)
          }
          if (this.setups.some((s) => s.name === body.name!.trim())) {
            return json(route, { detail: `a setup named '${body.name!.trim()}' already exists` }, 422)
          }
          const setup: MockSetup = {
            id: Math.max(0, ...this.setups.map((s) => s.id)) + 1,
            name: body.name.trim(),
            um_per_px: body.um_per_px!,
            calibration_objective: body.calibration_objective!.trim(),
            phone_resolution: body.phone_resolution?.trim() || null,
            created_at: new Date().toISOString(),
          }
          this.setups.push(setup)
          return json(route, setup, 201)
        }
        if (path.startsWith('/setups/') && sub === undefined) {
          const setup = this.setups.find((s) => s.id === Number(idText))
          if (!setup) return json(route, { detail: 'setup not found' }, 404)
          if (method === 'GET') return json(route, setup)
          if (method === 'DELETE') {
            if (this.slides.some((s) => s.setup_id === setup.id)) {
              return json(route, { detail: 'setup is still used by existing slides' }, 409)
            }
            this.setups = this.setups.filter((s) => s.id !== setup.id)
            return route.fulfill({ status: 204, body: '' })
          }
        }
        if (path.startsWith('/slides/')) {
          if (!slide) return json(route, { detail: 'slide not found' }, 404)
          if (sub === 'image') return route.fulfill({ status: 200, contentType: 'image/jpeg', body: PHOTO })
          if (sub === 'heatmap') return route.fulfill({ status: 200, contentType: 'image/png', body: HEATMAP })
          if (sub === 'events') {
            return json(route, [
              { from_state: null, to_state: 'new', note: null, at: slide.created_at },
              { from_state: 'scored', to_state: 'queued', note: null, at: slide.updated_at },
            ])
          }
          try {
            if (sub === 'open') this.move(slide, 'under_review')
            if (sub === 'retry') this.move(slide, 'new')
            if (sub === 'action') {
              const { action, priority } = this.posts.at(-1)!.body as { action: string; priority?: number }
              if (action === 'reassign_priority') {
                if (slide.state === 'under_review') this.move(slide, 'queued')
                slide.priority_override = priority ?? null
              } else {
                this.move(slide, 'archived')
                slide.decision = action as Slide['decision']
              }
            }
          } catch (err) {
            return json(route, { detail: (err as Error).message }, 409)
          }
          return json(route, slide)
        }
        return json(route, { detail: `No mock for ${method} ${path}` }, 501)
      },
    )
  }
}

/** "40x" -> 40, mirroring backend/app/setups.py (NaN when unparseable). */
function parseMag(objective: string): number {
  const m = /^\s*(\d+(?:\.\d+)?)\s*x\s*$/i.exec(objective ?? '')
  return m ? Number(m[1]) : NaN
}

/** Text fields of a multipart body (the file part is left out). */
function multipartFields(body: Buffer | null): Record<string, string> {
  const text = body?.toString('latin1') ?? ''
  return Object.fromEntries(
    [...text.matchAll(/name="(\w+)"\r\n\r\n([^\r]*)\r\n/g)].map((m) => [m[1], Buffer.from(m[2], 'latin1').toString('utf8')]),
  )
}

/** The demo worklist: a high-risk routine slide, a low-risk urgent one, an older low-risk one. */
export const demoSlides = () => [
  makeSlide(1, { risk_score: 0.91, risk_flag: 'red', created_at: '2026-10-09T09:00:00.000Z' }),
  makeSlide(2, { risk_score: 0.12, risk_flag: 'green', indication: 'Urgent', created_at: '2026-10-09T10:00:00.000Z' }),
  makeSlide(3, { risk_score: 0.04, risk_flag: 'green', created_at: '2026-10-08T08:00:00.000Z' }),
]

/** `backend` fixture: the mocked API with the demo worklist, installed before the test navigates. */
export const test = base.extend<{ backend: MockBackend }>({
  // `provide` is Playwright's fixture callback (usually named `use`, which linters mistake for React's hook).
  backend: async ({ page }, provide) => {
    const backend = new MockBackend(demoSlides())
    await backend.install(page)
    await provide(backend)
  },
})

export { expect } from '@playwright/test'
