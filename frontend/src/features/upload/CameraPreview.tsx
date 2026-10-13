import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '../../shared/api/client.ts'
import { usePageVisible } from '../../shared/lib/hooks.ts'

/**
 * Live view of the phone on the microscope (MJPEG from the backend), so the technician can frame and
 * focus before capturing. Mounted only while connected and visible: unmounting closes the stream.
 */
export function CameraPreview({ source }: { source: string | null }) {
  const { t } = useTranslation('upload')
  const visible = usePageVisible()
  const [attempt, setAttempt] = useState(0)
  const [failed, setFailed] = useState(false)

  return (
    <figure className="space-y-1">
      <div className="relative flex aspect-video items-center justify-center overflow-hidden rounded-lg bg-slate-950 text-center text-xs text-slate-400">
        {!visible ? (
          <span className="px-4">{t('camera.previewPaused')}</span>
        ) : failed ? (
          <span className="space-y-2 px-4">
            <span className="block">{t('camera.previewUnavailable')}</span>
            <button
              type="button"
              onClick={() => {
                setFailed(false)
                setAttempt((n) => n + 1)
              }}
              className="rounded border border-slate-600 px-2 py-1 text-slate-200 hover:bg-slate-800"
            >
              {t('camera.previewRetry')}
            </button>
          </span>
        ) : (
          <img
            // A new URL per source and retry restarts the stream; the query is ignored by the backend.
            key={`${source}-${attempt}`}
            src={`${api.capturePreviewUrl()}?v=${encodeURIComponent(source ?? '')}-${attempt}`}
            alt={t('camera.preview')}
            onError={() => setFailed(true)}
            className="size-full object-contain"
          />
        )}
      </div>
      <figcaption className="text-[11px] text-slate-500">{t('camera.previewHint')}</figcaption>
    </figure>
  )
}
