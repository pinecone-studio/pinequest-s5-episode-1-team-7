import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAllSlides, useQueue } from '../../shared/api/queries.ts'
import { PROCESSING_STATES, type Slide } from '../../shared/api/types.ts'
import { cn } from '../../shared/lib/cn.ts'
import { useDocumentTitle, useNow, useStoredState } from '../../shared/lib/hooks.ts'
import { Alert } from '../../shared/ui/Alert.tsx'
import { SegmentedControl } from '../../shared/ui/SegmentedControl.tsx'
import { StateLabel } from '../triage/TriageBadges.tsx'
import { NewSlidePanel } from '../upload/NewSlidePanel.tsx'
import { SlideRow } from './SlideRow.tsx'
import { type SortMode, sortSlides } from './sortSlides.ts'
import { useReorderAnimation } from './useReorderAnimation.ts'

type Tab = 'queue' | 'review' | 'archived'

export function WorklistPage() {
  const { t } = useTranslation(['worklist', 'common', 'upload'])
  useDocumentTitle(`${t('title')} · PathTriage`)
  const [tab, setTab] = useStoredState<Tab>('pathtriage.worklistTab', 'queue')
  const [sortMode, setSortMode] = useStoredState<SortMode>('pathtriage.queueSort', 'risk')
  const queue = useQueue('risk')
  const all = useAllSlides()
  const now = useNow()

  const slides = all.data ?? []
  const processing = slides.filter((s) => PROCESSING_STATES.includes(s.state) || s.state === 'failed')
  const underReview = slides.filter((s) => s.state === 'under_review')
  const archived = slides.filter((s) => s.state === 'archived')
  const queued = queue.data ? sortSlides(queue.data, sortMode) : undefined

  const visible = tab === 'queue' ? queued : all.data ? (tab === 'review' ? underReview : archived) : undefined
  const error = queue.error ?? all.error
  const rowRef = useReorderAnimation((visible ?? []).map((s) => s.id).join(','))

  return (
    <main className="mx-auto grid w-full max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[1fr_340px]">
      <section className="min-w-0" aria-labelledby="worklist-title">
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div className="min-w-0">
            <h1 id="worklist-title" className="text-xl font-semibold tracking-tight">
              {t('title')}
            </h1>
            <p className="text-sm text-slate-500">{t('subtitle')}</p>
          </div>
          <SegmentedControl
            className="ml-auto"
            label={t('tab.label')}
            value={tab}
            onChange={setTab}
            options={[
              { value: 'queue', label: t('tab.queue', { count: queue.data?.length ?? 0 }) },
              { value: 'review', label: t('tab.review', { count: underReview.length }) },
              { value: 'archived', label: t('tab.archived') },
            ]}
          />
        </div>

        {error && (
          <Alert tone="error" className="mb-3">
            {t('offline.title')}: {error.message}
            <p className="mt-1">{t('offline.hint')}</p>
          </Alert>
        )}

        {tab === 'queue' && (
          <>
            {queued && <Stats queued={queued} processing={processing} />}
            {processing.length > 0 && <ProcessingList slides={processing} />}
            <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
              <SortSwitch mode={sortMode} onChange={setSortMode} />
              <span className="text-xs text-slate-500">{t(sortMode === 'risk' ? 'sort.riskHint' : 'sort.arrivalHint')}</span>
            </div>
          </>
        )}
        {tab === 'review' && <p className="mb-3 text-xs text-slate-500">{t('reviewHint')}</p>}

        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
          <div
            aria-hidden
            className="hidden grid-cols-[120px_minmax(0,1fr)_90px_120px_150px] gap-3 border-b border-slate-200 px-4 py-2 text-xs font-medium tracking-wide text-slate-500 uppercase md:grid dark:border-slate-800"
          >
            <span>{t('column.risk')}</span>
            <span>{t('column.slide')}</span>
            <span>{t('column.indication')}</span>
            <span>{t('column.score')}</span>
            <span>{t('column.status')}</span>
          </div>
          {!visible && !error && <p className="p-8 text-center text-sm text-slate-500">{t('common:status.loading')}</p>}
          {visible?.length === 0 && <p className="p-8 text-center text-sm text-slate-500">{t(`empty.${tab}`)}</p>}
          <ul aria-label={t(`tab.${tab}List`)}>
            {visible?.map((s) => (
              <li key={s.id} ref={rowRef(s.id)} className="relative bg-white dark:bg-slate-900">
                <SlideRow s={s} now={now} />
              </li>
            ))}
          </ul>
        </div>
      </section>

      <aside className="lg:sticky lg:top-6 lg:self-start" aria-labelledby="new-slide-title">
        <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
          <h2 id="new-slide-title" className="mb-1 font-semibold">
            {t('upload:title')}
          </h2>
          <p className="mb-3 text-xs text-slate-500">{t('upload:intro')}</p>
          <NewSlidePanel />
        </div>
      </aside>
    </main>
  )
}

function SortSwitch({ mode, onChange }: { mode: SortMode; onChange: (mode: SortMode) => void }) {
  const { t } = useTranslation('worklist')
  const on = mode === 'risk'
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(on ? 'arrival' : 'risk')}
      className="inline-flex items-center gap-2 rounded-md text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600"
    >
      <span aria-hidden className={cn('relative h-5 w-9 shrink-0 rounded-full transition', on ? 'bg-cyan-700' : 'bg-slate-300 dark:bg-slate-700')}>
        <span className={cn('absolute top-0.5 left-0.5 size-4 rounded-full bg-white shadow transition-transform', on && 'translate-x-4')} />
      </span>
      {t('sort.byRisk')}
    </button>
  )
}

function Stats({ queued, processing }: { queued: Slide[]; processing: Slide[] }) {
  const { t } = useTranslation('worklist')
  const stats = [
    { key: 'red', value: queued.filter((s) => s.risk_flag === 'red').length, tone: 'text-red-600 dark:text-red-400' },
    { key: 'yellow', value: queued.filter((s) => s.risk_flag === 'yellow').length, tone: 'text-amber-600 dark:text-amber-400' },
    { key: 'urgent', value: queued.filter((s) => s.indication === 'Urgent').length, tone: 'text-rose-700 dark:text-rose-400' },
    {
      key: 'processing',
      value: processing.filter((s) => s.state !== 'failed').length,
      tone: 'text-sky-600 dark:text-sky-400',
    },
  ] as const
  return (
    <dl className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {stats.map((s) => (
        <div key={s.key} className="rounded-lg border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900">
          <dd className={cn('text-2xl font-semibold tabular-nums', s.tone)}>{s.value}</dd>
          <dt className="text-xs text-slate-500">{t(`stats.${s.key}`)}</dt>
        </div>
      ))}
    </dl>
  )
}

/** Slides still in the pipeline, or failed and waiting for a retry. */
function ProcessingList({ slides }: { slides: Slide[] }) {
  const { t } = useTranslation(['worklist', 'common'])
  return (
    <section aria-labelledby="processing-title" className="mb-4 rounded-lg border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900">
      <h2 id="processing-title" className="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase">
        {t('processing.title')}
      </h2>
      <ul className="flex flex-wrap gap-2">
        {slides.map((s) => (
          <li key={s.id}>
            <Link
              to={`/slides/${s.id}`}
              className={cn(
                'inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-sm hover:bg-slate-50 dark:hover:bg-slate-800',
                s.state === 'failed' ? 'border-red-200 dark:border-red-900/60' : 'border-slate-200 dark:border-slate-700',
              )}
            >
              <span className="font-medium">{t('common:slide.title', { id: s.id })}</span>
              <StateLabel state={s.state} />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
