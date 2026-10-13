import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { EngineStatus } from './EngineStatus.tsx'
import { LanguageSwitcher } from './LanguageSwitcher.tsx'

export function Header() {
  const { t } = useTranslation()
  return (
    <header className="relative z-[1000] border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
        <Link to="/" className="flex shrink-0 items-center gap-2 font-semibold tracking-tight">
          <img src="/favicon.svg" alt="" className="size-7" />
          <span>PathTriage</span>
          <span className="hidden text-sm font-normal text-slate-500 md:inline">{t('app.tagline')}</span>
        </Link>
        <div className="ml-auto flex min-w-0 items-center gap-2">
          <EngineStatus />
          <LanguageSwitcher />
        </div>
      </div>
    </header>
  )
}
