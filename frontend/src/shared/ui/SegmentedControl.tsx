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
        'flex rounded-md p-0.5 text-sm',
        tone === 'light' ? 'border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900' : 'bg-white/10',
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
              'flex-1 rounded px-3 py-1 leading-tight transition focus-visible:outline-2 focus-visible:outline-cyan-600 disabled:opacity-35',
              tone === 'light'
                ? selected
                  ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                  : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100'
                : selected
                  ? 'bg-cyan-600 font-medium text-white'
                  : 'hover:bg-white/10',
            )}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
