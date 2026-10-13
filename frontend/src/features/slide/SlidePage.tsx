import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { api, ApiError } from '../../shared/api/client.ts'
import { useSlide } from '../../shared/api/queries.ts'
import type { Slide } from '../../shared/api/types.ts'
import { useDocumentTitle } from '../../shared/lib/hooks.ts'
import { useFormat } from '../../shared/lib/useFormat.ts'
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
        <p className="text-red-600 dark:text-red-400">{notFound ? t('notFound') : error.message}</p>
        <Link to="/" className="mt-2 inline-block text-cyan-700 underline dark:text-cyan-400">
          {t('backToWorklist')}
        </Link>
      </main>
    )
  }
  if (!slide) return <main className="p-8 text-center text-slate-500">{t('loading')}</main>
  return <SlideWorkspace slide={slide} />
}

function SlideWorkspace({ slide }: { slide: Slide }) {
  const { t } = useTranslation('slide')
  const scored = slide.risk_score != null
  return (
    <main className="grid lg:h-full lg:grid-cols-[1fr_400px]">
      <section className="relative h-[60vh] min-h-80 bg-slate-950 lg:h-auto" aria-label={t('viewerLabel')}>
        <SlideViewer imageUrl={api.imageUrl(slide.id)} heatmapUrl={slide.has_heatmap ? api.heatmapUrl(slide.id) : undefined} />
      </section>

      <aside className="border-l border-slate-200 bg-white lg:overflow-y-auto dark:border-slate-800 dark:bg-slate-900">
        <div className="space-y-5 p-5">
          <Heading slide={slide} />
          {scored ? <ScoreCard slide={slide} /> : <PipelineProgress slide={slide} />}
          <ReviewPanel slide={slide} />
          <EventLog slide={slide} />
        </div>
      </aside>
    </main>
  )
}

function Heading({ slide }: { slide: Slide }) {
  const { t } = useTranslation(['slide', 'common'])
  const f = useFormat()
  return (
    <div>
      <Link to="/" className="text-sm text-cyan-700 hover:underline dark:text-cyan-400">
        ← {t('backToWorklist')}
      </Link>
      <div className="mt-2 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold tracking-tight">{t('common:slide.title', { id: slide.id })}</h1>
          <p className="text-sm text-slate-500" title={t('codeHint')}>
            {t('common:slide.code', { code: slide.local_hash })}
          </p>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-slate-500">
            <span title={f.dateTime(slide.created_at)}>{t('received', { when: f.ago(slide.created_at) })}</span>
            <IndicationBadge indication={slide.indication} />
          </p>
        </div>
        <StateLabel state={slide.state} />
      </div>
    </div>
  )
}
