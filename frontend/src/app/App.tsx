import { lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { Route, Routes } from 'react-router-dom'

import { WorklistPage } from '../features/worklist/WorklistPage.tsx'
import { AboutPage } from '../features/about/AboutPage.tsx'
import { CalibratePage } from '../features/calibration/CalibratePage.tsx'
import { DisclaimerBanner } from './DisclaimerBanner.tsx'
import { ErrorBoundary } from './ErrorBoundary.tsx'
import { Header } from './Header.tsx'
import { NotFound } from './NotFound.tsx'

// The slide page carries the Leaflet viewer; load it on first visit instead of with the worklist.
const SlidePage = lazy(() => import('../features/slide/SlidePage.tsx').then((m) => ({ default: m.SlidePage })))

/** Full-height shell: header and safety banner stay put, the page below scrolls. */
export default function App() {
  const { t } = useTranslation()
  return (
    <div className="flex h-dvh flex-col bg-canvas text-ink">
      <Header />
      <DisclaimerBanner />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <ErrorBoundary>
          <Suspense fallback={<p className="p-8 text-center text-ink-faint">{t('status.loading')}</p>}>
            <Routes>
              <Route path="/" element={<WorklistPage />} />
              <Route path="/slides/:id" element={<SlidePage />} />
              <Route path="/calibrate" element={<CalibratePage />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </div>
    </div>
  )
}
