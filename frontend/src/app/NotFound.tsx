import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

export function NotFound() {
  const { t } = useTranslation()
  return (
    <main className="p-8 text-center">
      <h1 className="text-lg font-semibold">{t('notFound.title')}</h1>
      <Link to="/" className="mt-2 inline-block text-cyan-700 underline dark:text-cyan-400">
        {t('notFound.back')}
      </Link>
    </main>
  )
}
