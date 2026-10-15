import { cn } from '../lib/cn.ts'

export interface SegmentOption<T extends string> {
  value: T
  label: string
  disabled?: boolean
  title?: string
}

interface Props<T extends string> {
  /** Accessible name of the group. */
  label: string
  value: T
  options: SegmentOption<T>[]
  onChange: (value: T) => void
  tone?: 'light' | 'dark'
  className?: string
}

/** A row of mutually exclusive buttons (radio group), e.g. queue filters or the language switch. */
export function SegmentedControl<T extends string>({ label, value, options, onChange, tone = 'light', className }: Props<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        'flex rounded-[10px] border border-line-soft bg-canvas p-1 text-sm',
        tone === 'dark' && 'border-white/10 bg-white/10',
        className,
      )}
    >
      {options.map((o) => {
        const selected = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={o.disabled}
            title={o.title}
            onClick={() => onChange(o.value)}
            className={cn(
              'flex-1 rounded-lg px-3 py-1.5 font-display text-[13px] font-semibold tracking-[-0.005em] transition focus-visible:outline-2 focus-visible:outline-mist disabled:opacity-35',
              selected
                ? 'bg-mist text-mist-ink shadow-[0_4px_12px_-6px_rgb(127_179_168/0.7)]'
                : 'text-ink-dim hover:bg-raised hover:text-ink',
              tone === 'dark' && !selected && 'text-ink-dim hover:bg-white/10 hover:text-ink',
              tone === 'dark' && selected && 'bg-mist text-mist-ink',
            )}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
