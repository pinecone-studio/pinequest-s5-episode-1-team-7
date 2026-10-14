import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { EngineStatus } from './EngineStatus.tsx'
import { LanguageSwitcher } from './LanguageSwitcher.tsx'

export function Header() {
  const { t } = useTranslation()
  return (
    <header className="relative z-[1000] border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="mx-auto flex min-h-14 max-w-7xl flex-wrap items-center gap-x-3 gap-y-1 px-4 py-1.5">
        <Link to="/" className="flex shrink-0 items-center gap-2 font-semibold tracking-tight">
          <img src="/favicon.svg" alt="" className="size-7" />
          <span>PathTriage</span>
          <span className="hidden text-sm font-normal text-slate-500 md:inline">{t('app.tagline')}</span>
        </Link>
        <nav aria-label={t('app.calibration')} className="ml-2 flex gap-3">
          <Link to="/calibrate" className="text-sm text-slate-600 hover:text-slate-900 hover:underline dark:text-slate-300 dark:hover:text-white">
            {t('app.calibration')}
          </Link>
          <Link to="/about" className="text-sm text-slate-600 hover:text-slate-900 hover:underline dark:text-slate-300 dark:hover:text-white">
            {t('app.about')}
          </Link>
        </nav>
        <div className="ml-auto flex min-w-0 items-center gap-2">
          <EngineStatus />
          <LanguageSwitcher />
        </div>
      </div>
    </header>
  )
}
