import { useTranslation } from 'react-i18next'

import { useTheme } from '../shared/lib/theme.ts'

/** Dark / light switch. Dark (default) is the eye-friendly clinical theme. */
export function ThemeToggle() {
  const { t } = useTranslation()
  const { theme, toggle } = useTheme()
  const dark = theme === 'dark'
  return (
    <button
      type="button"
      onClick={toggle}
      role="switch"
      aria-checked={dark}
      title={t('theme.toggle', { defaultValue: dark ? 'Switch to light' : 'Switch to dark' })}
      aria-label={t('theme.toggle', { defaultValue: dark ? 'Switch to light' : 'Switch to dark' })}
      className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-raised text-ink-dim transition hover:border-mist-dim hover:text-ink"
    >
      {dark ? (
        <svg viewBox="0 0 20 20" className="size-4" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden>
          <circle cx="10" cy="10" r="3.2" />
          <path d="M10 1.8v1.8M10 16.4v1.8M1.8 10h1.8M16.4 10h1.8M4 4l1.3 1.3M14.7 14.7 16 16M16 4l-1.3 1.3M5.3 14.7 4 16" strokeLinecap="round" />
        </svg>
      ) : (
        <svg viewBox="0 0 20 20" className="size-4" fill="currentColor" aria-hidden>
          <path d="M16.2 13.4A7 7 0 0 1 6.6 3.8a.75.75 0 0 0-.9-.9 8.5 8.5 0 1 0 11.6 11.6.75.75 0 0 0-.9-.9l-.2-.2Z" />
        </svg>
      )}
    </button>
  )
}
