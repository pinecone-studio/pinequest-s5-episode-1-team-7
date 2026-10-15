import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

export function NotFound() {
  const { t } = useTranslation()
  return (
    <main className="p-8 text-center">
      <h1 className="font-display text-lg font-bold">{t('notFound.title')}</h1>
      <Link to="/" className="mt-2 inline-block text-mist underline hover:text-mist-strong">
        {t('notFound.back')}
      </Link>
    </main>
  )
}
