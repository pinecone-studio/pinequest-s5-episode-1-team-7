import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { useTranslation } from 'react-i18next'

import { useReassignPriority } from '../../shared/api/queries.ts'
import type { Slide } from '../../shared/api/types.ts'
import { PRIORITY_LEVELS, priorityLevel } from '../triage/risk.ts'

/**
 * "Re-assign priority" (TDD 6.2). The backend lists manually prioritised slides above AI-ranked ones;
 * on an under-review slide it also hands the slide back to the worklist.
 */
export function PriorityMenu({ slide }: { slide: Slide }) {
  const { t } = useTranslation(['slide', 'common'])
  const reassign = useReassignPriority(slide.id)
  const current = slide.priority_override == null ? '' : priorityLevel(slide.priority_override)

  return (
    <div>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger
          disabled={reassign.isPending}
          className="inline-flex w-full items-center justify-center gap-1 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-cyan-600 disabled:opacity-40 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          {t('priority.trigger')}
          <svg viewBox="0 0 20 20" className="size-3.5 opacity-60" fill="currentColor" aria-hidden>
            <path d="M5.2 7.5a.75.75 0 0 1 1.06 0L10 11.2l3.74-3.7a.75.75 0 1 1 1.06 1.06l-4.27 4.25a.75.75 0 0 1-1.06 0L5.2 8.56a.75.75 0 0 1 0-1.06Z" />
          </svg>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="center"
            sideOffset={6}
            className="z-[1500] w-72 rounded-lg border border-slate-200 bg-white p-1 text-sm shadow-xl dark:border-slate-700 dark:bg-slate-900"
          >
            <DropdownMenu.Label className="px-2 py-1.5 text-xs text-slate-500">
              {t(slide.state === 'under_review' ? 'priority.hintReview' : 'priority.hint')}
            </DropdownMenu.Label>
            <DropdownMenu.RadioGroup
              value={current}
              onValueChange={(key) => {
                const level = PRIORITY_LEVELS.find((l) => l.key === key)
                if (level) reassign.mutate(level.value)
              }}
            >
              {PRIORITY_LEVELS.map((level) => (
                <DropdownMenu.RadioItem
                  key={level.key}
                  value={level.key}
                  className="relative flex cursor-pointer items-center justify-between gap-2 rounded py-1.5 pr-2 pl-7 outline-none select-none data-[highlighted]:bg-slate-100 dark:data-[highlighted]:bg-slate-800"
                >
                  <DropdownMenu.ItemIndicator className="absolute left-2 text-cyan-700 dark:text-cyan-400">✓</DropdownMenu.ItemIndicator>
                  {t(`common:priority.level.${level.key}`)}
                  <span className="text-xs text-slate-400 tabular-nums">{Math.round(level.value * 100)}</span>
                </DropdownMenu.RadioItem>
              ))}
            </DropdownMenu.RadioGroup>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      {reassign.error && <p className="mt-1 text-sm text-red-600 dark:text-red-400">{reassign.error.message}</p>}
    </div>
  )
}
