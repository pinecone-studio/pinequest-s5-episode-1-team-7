import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useDecide, useOpenSlide, useRetry } from '../../shared/api/queries.ts'
import type { Decision, Slide } from '../../shared/api/types.ts'
import { useFormat } from '../../shared/lib/useFormat.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog.tsx'
import { PriorityMenu } from './PriorityMenu.tsx'

const DECISIONS: { decision: Decision; variant: 'danger' | 'success' | 'warning' }[] = [
  { decision: 'confirm_malignancy', variant: 'danger' },
  { decision: 'mark_benign', variant: 'success' },
  { decision: 'request_biopsy', variant: 'warning' },
]

/**
 * Pathologist controls for each state (TDD 3.2, 6.2): start a review, decide, re-assign priority,
 * or retry a failed slide. Mutations live here, not in the per-state views: a successful action
 * swaps the view, and TanStack Query drops `mutate` callbacks of an unmounted component.
 */
export function ReviewPanel({ slide }: { slide: Slide }) {
  const { t } = useTranslation(['slide', 'common'])
  const navigate = useNavigate()
  const open = useOpenSlide(slide.id)
  const decide = useDecide(slide.id)
  const retry = useRetry(slide.id)
  const [pending, setPending] = useState<Decision | null>(null)

  const section = (children: ReactNode) => (
    <section className="space-y-3 border-t border-slate-200 pt-4 dark:border-slate-800">
      <h2 className="text-sm font-semibold">{t('review.title')}</h2>
      {children}
    </section>
  )

  switch (slide.state) {
    case 'queued':
      return section(
        <>
          <p className="text-xs text-slate-500">{t('review.startHint')}</p>
          <Button variant="primary" block disabled={open.isPending} onClick={() => open.mutate()}>
            {t('review.start')}
          </Button>
          <ErrorText error={open.error} />
          <PriorityMenu slide={slide} />
        </>,
      )
    case 'under_review': {
      const chosen = DECISIONS.find((d) => d.decision === pending)
      return section(
        <>
          <div className="grid gap-2">
            {DECISIONS.map(({ decision, variant }) => (
              <Button
                key={decision}
                variant={variant}
                block
                disabled={decide.isPending}
                onClick={() => {
                  decide.reset()
                  setPending(decision)
                }}
              >
                {t(`common:decision.${decision}`)}
              </Button>
            ))}
          </div>
          <p className="text-xs text-slate-500">{t('review.decideHint')}</p>
          <PriorityMenu slide={slide} />
          <ConfirmDialog
            open={pending != null}
            onOpenChange={(isOpen) => !isOpen && !decide.isPending && setPending(null)}
            title={pending ? t(`review.confirm.${pending}`) : ''}
            confirmLabel={pending ? t(`common:decision.${pending}`) : ''}
            confirmVariant={chosen?.variant}
            busy={decide.isPending}
            error={decide.error?.message}
            onConfirm={() => pending && decide.mutate(pending, { onSuccess: () => navigate('/') })}
          >
            <p className="font-semibold text-slate-900 dark:text-slate-100">{t('common:slide.title', { id: slide.id })}</p>
            <p>{t('review.confirmBody')}</p>
          </ConfirmDialog>
        </>,
      )
    }
    case 'archived':
      return section(<Archived slide={slide} />)
    case 'failed':
      return section(
        <>
          <p className="text-xs text-slate-500">{t('review.retryHint')}</p>
          <Button block disabled={retry.isPending} onClick={() => retry.mutate()}>
            {t('review.retry')}
          </Button>
          <ErrorText error={retry.error} />
        </>,
      )
    default:
      return null // still in the pipeline
  }
}

function Archived({ slide }: { slide: Slide }) {
  const { t } = useTranslation(['slide', 'common'])
  const f = useFormat()
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
      <dt className="text-slate-500">{t('review.decision')}</dt>
      <dd className="font-medium">{slide.decision ? t(`common:decision.${slide.decision}`) : '—'}</dd>
      <dt className="text-slate-500">{t('review.archivedAt')}</dt>
      <dd>{f.dateTime(slide.updated_at)}</dd>
    </dl>
  )
}

function ErrorText({ error }: { error: Error | null }) {
  if (!error) return null
  return <p className="text-sm text-red-600 dark:text-red-400">{error.message}</p>
}
