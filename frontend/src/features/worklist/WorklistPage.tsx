import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAllSlides, useOrgans, useQueue } from '../../shared/api/queries.ts'
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
  const [organFilter, setOrganFilter] = useStoredState<string>('pathtriage.organFilter', '')
  const organs = useOrgans()
  const organList = Array.isArray(organs.data) ? organs.data : []
  const queue = useQueue('risk', organFilter || undefined)
  const all = useAllSlides(organFilter || undefined)
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
            <h1 id="worklist-title" className="font-display text-[22px] font-bold tracking-[-0.02em] text-ink">
              {t('title')}
            </h1>
            <p className="mt-0.5 text-sm text-ink-dim">{t('subtitle')}</p>
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

        {organList.length > 1 && (
          <div className="mb-3 flex items-center gap-2 text-xs text-ink-dim">
            <label className="flex items-center gap-2">
              {t('filter.organ')}
              <select
                className="rounded-[10px] border border-line bg-surface px-2 py-1.5 text-sm text-ink outline-none focus:border-mist-dim"
                value={organFilter}
                onChange={(e) => setOrganFilter(e.target.value)}
              >
                <option value="">{t('filter.allOrgans')}</option>
                {organList.map((o) => (
                  <option key={o} value={o}>
                    {t(`common:organ.names.${o}`, { defaultValue: o })}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

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
              <span className="text-xs text-ink-faint">{t(sortMode === 'risk' ? 'sort.riskHint' : 'sort.arrivalHint')}</span>
            </div>
          </>
        )}
        {tab === 'review' && <p className="mb-3 text-xs text-ink-faint">{t('reviewHint')}</p>}

        <div className="panel overflow-hidden">
          <div
            aria-hidden
            className="hidden grid-cols-[120px_minmax(0,1fr)_90px_120px_150px] gap-3 border-b border-line-soft bg-raised/40 px-4 py-2 font-display text-xs font-bold tracking-[0.06em] text-ink-faint uppercase md:grid"
          >
            <span>{t('column.risk')}</span>
            <span>{t('column.slide')}</span>
            <span>{t('column.indication')}</span>
            <span>{t('column.score')}</span>
            <span>{t('column.status')}</span>
          </div>
          {!visible && !error && <p className="p-8 text-center text-sm text-ink-faint">{t('common:status.loading')}</p>}
          {visible?.length === 0 && <p className="p-8 text-center text-sm text-ink-faint">{t(`empty.${tab}`)}</p>}
          <ul aria-label={t(`tab.${tab}List`)}>
            {visible?.map((s) => (
              <li key={s.id} ref={rowRef(s.id)} className="relative bg-surface">
                <SlideRow s={s} now={now} />
              </li>
            ))}
          </ul>
        </div>
      </section>

      <aside className="lg:sticky lg:top-[4.5rem] lg:self-start" aria-labelledby="new-slide-title">
        <div className="panel p-5">
          <h2 id="new-slide-title" className="font-display text-[15px] font-bold tracking-[-0.01em]">
            {t('upload:title')}
          </h2>
          <p className="mb-4 text-xs leading-relaxed text-ink-dim">{t('upload:intro')}</p>
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
      className="inline-flex items-center gap-2 rounded-lg text-sm font-medium text-ink-dim transition hover:text-ink focus-visible:outline-2 focus-visible:outline-mist"
    >
      <span aria-hidden className={cn('relative h-5 w-9 shrink-0 rounded-full transition', on ? 'bg-mist-dim' : 'bg-overlay ring-1 ring-line')}>
        <span className={cn('absolute top-0.5 left-0.5 size-4 rounded-full bg-ink shadow transition-transform', on && 'translate-x-4')} />
      </span>
      {t('sort.byRisk')}
    </button>
  )
}

function Stats({ queued, processing }: { queued: Slide[]; processing: Slide[] }) {
  const { t } = useTranslation('worklist')
  const stats = [
    { key: 'red', value: queued.filter((s) => s.risk_flag === 'red').length, tone: 'text-[#b23a1f] dark:text-[#ff7a45]', icon: null },
    { key: 'yellow', value: queued.filter((s) => s.risk_flag === 'yellow').length, tone: 'text-[#4f4f08] dark:text-[#ebcb8b]', icon: null },
    // Urgent is a human request, not an AI score: neutral ink + bolt, never a risk colour.
    { key: 'urgent', value: queued.filter((s) => s.indication === 'Urgent').length, tone: 'text-ink', icon: 'bolt' },
    {
      key: 'processing',
      value: processing.filter((s) => s.state !== 'failed').length,
      tone: 'text-[#3d5f86] dark:text-[#8fa9c6]',
      icon: null,
    },
  ] as const
  return (
    <dl className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {stats.map((s) => (
        <div key={s.key} className="panel px-4 py-3">
          <dd className={cn('tnum flex items-center gap-1.5 text-[26px] leading-none font-semibold', s.tone)}>
            {s.icon === 'bolt' && (
              <svg viewBox="0 0 16 16" className="size-5 shrink-0 text-ink-faint" fill="currentColor" aria-hidden>
                <path d="M9.5 1 3 9h4l-1 6 6.5-8.5H8.7L9.5 1Z" />
              </svg>
            )}
            {s.value}
          </dd>
          <dt className="mt-1.5 text-xs text-ink-faint">{t(`stats.${s.key}`)}</dt>
        </div>
      ))}
    </dl>
  )
}

/** Slides still in the pipeline, or failed and waiting for a retry. */
function ProcessingList({ slides }: { slides: Slide[] }) {
  const { t } = useTranslation(['worklist', 'common'])
  return (
    <section aria-labelledby="processing-title" className="panel mb-4 px-4 py-3">
      <h2 id="processing-title" className="mb-2 font-display text-xs font-bold tracking-[0.06em] text-ink-faint uppercase">
        {t('processing.title')}
      </h2>
      <ul className="flex flex-wrap gap-2">
        {slides.map((s) => (
          <li key={s.id}>
            <Link
              to={`/slides/${s.id}`}
              className={cn(
                'inline-flex items-center gap-2 rounded-[10px] border border-line-soft bg-canvas px-2.5 py-1 text-sm transition hover:border-mist-dim hover:bg-raised',
                // Failed analysis is an error (magenta), never a risk colour.
                s.state === 'failed' && 'border-[#dfa3be] dark:border-[#6b3450]',
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
