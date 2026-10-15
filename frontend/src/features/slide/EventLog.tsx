import { useTranslation } from 'react-i18next'

import { useLookup } from '../../i18n/useLookup.ts'
import { useEvents } from '../../shared/api/queries.ts'
import type { Slide } from '../../shared/api/types.ts'
import { useFormat } from '../../shared/lib/useFormat.ts'

/** The slide's audit trail (GET /slides/{id}/events), newest last. */
export function EventLog({ slide }: { slide: Slide }) {
  const { t } = useTranslation(['slide', 'common'])
  const lookup = useLookup('slide')
  const f = useFormat()
  const { data: events } = useEvents(String(slide.id), slide.state)
  if (!events?.length) return null
  return (
    <section className="border-t border-line-soft pt-4">
      <details>
        <summary className="cursor-pointer text-sm font-display font-bold select-none">{t('history.title', { count: events.length })}</summary>
        <ol className="mt-2 space-y-1.5 border-l border-line pl-3 text-xs">
          {events.map((e, i) => (
            <li key={i}>
              <span className="font-medium text-ink-dim">{t(`common:state.${e.to_state}`)}</span>
              {e.note && <span className="text-ink-faint"> · {lookup(`history.note.${e.note.replace(/\s+/g, '_')}`, e.note)}</span>}
              <span className="tnum block text-ink-faint">{f.dateTime(e.at)}</span>
            </li>
          ))}
        </ol>
      </details>
    </section>
  )
}
