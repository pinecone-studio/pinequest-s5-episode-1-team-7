import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { api, ApiError } from '../../shared/api/client.ts'
import { useSlide } from '../../shared/api/queries.ts'
import type { Slide } from '../../shared/api/types.ts'
import { useDocumentTitle } from '../../shared/lib/hooks.ts'
import { useFormat } from '../../shared/lib/useFormat.ts'
import { Alert } from '../../shared/ui/Alert.tsx'
import { IndicationBadge, StateLabel } from '../triage/TriageBadges.tsx'
import { SlideViewer } from '../viewer/SlideViewer.tsx'
import { EventLog } from './EventLog.tsx'
import { PipelineProgress } from './PipelineProgress.tsx'
import { ReviewPanel } from './ReviewPanel.tsx'
import { ScoreCard } from './ScoreCard.tsx'

export function SlidePage() {
  const { id = '' } = useParams()
  const { t } = useTranslation(['slide', 'common'])
  const { data: slide, error } = useSlide(id)
  useDocumentTitle(`${slide ? t('common:slide.title', { id: slide.id }) : t('title')} · PathTriage`)

  if (error && !slide) {
    const notFound = error instanceof ApiError && error.status === 404
    return (
      <main className="p-8 text-center">
        <p className="text-critical">{notFound ? t('notFound') : error.message}</p>
        <Link to="/" className="mt-2 inline-block text-mist underline hover:text-mist-strong">
          {t('backToWorklist')}
        </Link>
      </main>
    )
  }
  if (!slide) return <main className="p-8 text-center text-ink-faint">{t('loading')}</main>
  return <SlideWorkspace slide={slide} />
}

function SlideWorkspace({ slide }: { slide: Slide }) {
  const { t } = useTranslation('slide')
  const scored = slide.risk_score != null
  return (
    <main className="grid lg:h-full lg:grid-cols-[1fr_400px]">
      <section className="relative h-[60vh] min-h-80 bg-[#0c1116] lg:h-auto" aria-label={t('viewerLabel')}>
        <SlideViewer imageUrl={api.imageUrl(slide.id)} heatmapUrl={slide.has_heatmap ? api.heatmapUrl(slide.id) : undefined} />
      </section>

      <aside className="border-l border-line-soft bg-surface lg:overflow-y-auto">
        <div className="space-y-5 p-5">
          <Heading slide={slide} />
          <ScaleNotice slide={slide} />
          {scored ? <ScoreCard slide={slide} /> : <PipelineProgress slide={slide} />}
          <ReviewPanel slide={slide} />
          <EventLog slide={slide} />
        </div>
      </aside>
    </main>
  )
}

/** Magnification audit trail, issue #35: warn when the AI read the photo at an
 * uncalibrated scale, and show the calibrated scale otherwise. */
function ScaleNotice({ slide }: { slide: Slide }) {
  const { t } = useTranslation('slide')
  if (slide.scale_warning) {
    return <Alert tone="warning">{t('scale.engineNote', { detail: slide.scale_warning })}</Alert>
  }
  if (slide.um_per_px == null) {
    return <Alert tone="warning">{t('scale.uncalibrated')}</Alert>
  }
  return (
    <p className="text-xs text-ink-faint">
      {t('scale.calibrated', { value: slide.um_per_px.toFixed(2), objective: slide.objective ?? '?' })}
    </p>
  )
}

function Heading({ slide }: { slide: Slide }) {
  const { t } = useTranslation(['slide', 'common'])
  const f = useFormat()
  return (
    <div>
      <Link to="/" className="text-sm text-mist hover:text-mist-strong hover:underline">
        ← {t('backToWorklist')}
      </Link>
      <div className="mt-2 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate font-display text-[20px] font-bold tracking-[-0.02em]">{t('common:slide.title', { id: slide.id })}</h1>
          <p className="tnum truncate text-[13px] text-ink-faint" title={t('codeHint')}>
            {t('common:slide.code', { code: slide.local_hash })}
          </p>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-ink-dim">
            <span title={f.dateTime(slide.created_at)}>{t('received', { when: f.ago(slide.created_at) })}</span>
            <IndicationBadge indication={slide.indication} />
            <span>{t(`common:organ.names.${slide.organ ?? 'lymph_node'}`, { defaultValue: slide.organ ?? 'lymph_node' })}</span>
          </p>
        </div>
        <StateLabel state={slide.state} />
      </div>
    </div>
  )
}
