import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { EngineStatus } from './EngineStatus.tsx'
import { LanguageSwitcher } from './LanguageSwitcher.tsx'
import { ThemeToggle } from './ThemeToggle.tsx'

export function Header() {
  const { t } = useTranslation()
  return (
    <header className="sticky top-0 z-[1000] border-b border-line-soft bg-canvas/85 backdrop-blur-md">
      <div className="mx-auto flex min-h-14 max-w-7xl flex-wrap items-center gap-x-3 gap-y-1 px-4 py-1.5">
        <Link to="/" className="flex shrink-0 items-center gap-2.5 font-display font-bold tracking-[-0.02em]">
          <span className="grid size-8 place-items-center rounded-[10px] border border-mist-dim/40 bg-mist-wash">
            <img src="/favicon.svg" alt="" className="size-5" />
          </span>
          <span className="text-[15px] text-ink">PathTriage</span>
          <span className="hidden text-[13px] font-normal text-ink-faint md:inline">{t('app.tagline')}</span>
        </Link>
        <nav aria-label={t('app.calibration')} className="ml-2 flex items-center gap-1">
          <Link
            to="/calibrate"
            className="rounded-lg px-2.5 py-1.5 font-display text-[13px] font-semibold text-ink-dim transition hover:bg-raised hover:text-ink"
          >
            {t('app.calibration')}
          </Link>
          <Link
            to="/about"
            className="rounded-lg px-2.5 py-1.5 font-display text-[13px] font-semibold text-ink-dim transition hover:bg-raised hover:text-ink"
          >
            {t('app.about')}
          </Link>
        </nav>
        <div className="ml-auto flex min-w-0 items-center gap-2">
          <EngineStatus />
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
