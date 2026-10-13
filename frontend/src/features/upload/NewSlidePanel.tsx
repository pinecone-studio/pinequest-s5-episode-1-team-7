import { type DragEvent, type FormEvent, useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useCaptureControl, useCaptureStatus, useIngest } from '../../shared/api/queries.ts'
import type { Indication } from '../../shared/api/types.ts'
import { cn } from '../../shared/lib/cn.ts'
import { useStoredState } from '../../shared/lib/hooks.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { fieldClass } from '../../shared/ui/field.ts'
import { SegmentedControl } from '../../shared/ui/SegmentedControl.tsx'
import { ingestErrorKey } from './errors.ts'

type Mode = 'upload' | 'camera'

/** Adds a slide: upload a photo, or capture a frame from the phone on the microscope (TDD 2.1, 3.1). */
export function NewSlidePanel() {
  const { t } = useTranslation(['upload', 'common'])
  const ids = useId()
  const [mode, setMode] = useStoredState<Mode>('pathtriage.newSlideMode', 'upload')
  const [patientId, setPatientId] = useState('')
  const [indication, setIndication] = useState<Indication>('Routine')
  const [done, setDone] = useState<number | null>(null)

  const reset = (id: number) => {
    setPatientId('')
    setIndication('Routine')
    setDone(id)
  }

  return (
    <div className="space-y-3">
      <SegmentedControl
        label={t('mode.label')}
        value={mode}
        onChange={(m) => {
          setMode(m)
          setDone(null)
        }}
        options={[
          { value: 'upload', label: t('mode.upload') },
          { value: 'camera', label: t('mode.camera') },
        ]}
      />

      <label className="block">
        <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">{t('field.patient')}</span>
        <input
          className={fieldClass}
          value={patientId}
          onChange={(e) => setPatientId(e.target.value)}
          autoComplete="off"
          aria-describedby={`${ids}-privacy`}
        />
        <span id={`${ids}-privacy`} className="mt-1 block text-[11px] text-slate-500">
          {t('field.patientHint')}
        </span>
      </label>
      <div>
        <span aria-hidden className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">
          {t('field.indication')}
        </span>
        <SegmentedControl
          label={t('field.indication')}
          value={indication}
          onChange={setIndication}
          options={[
            { value: 'Routine', label: t('common:indication.Routine') },
            { value: 'Urgent', label: t('common:indication.Urgent') },
          ]}
        />
      </div>

      {mode === 'upload' ? (
        <UploadForm patientId={patientId} indication={indication} onDone={reset} />
      ) : (
        <CameraForm patientId={patientId} indication={indication} onDone={reset} />
      )}
      {done != null && (
        <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">
          {t('added', { id: done })}
        </p>
      )}
    </div>
  )
}

interface FormProps {
  patientId: string
  indication: Indication
  onDone: (slideId: number) => void
}

function useErrorText(error: unknown) {
  const { t } = useTranslation('upload')
  if (!error) return ''
  const key = ingestErrorKey(error)
  return key ? t(`error.${key}`) : t('error.rejected', { detail: error instanceof Error ? error.message : String(error) })
}

function UploadForm({ patientId, indication, onDone }: FormProps) {
  const { t } = useTranslation('upload')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [dragging, setDragging] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const ingest = useIngest()
  const error = useErrorText(ingest.error)

  useEffect(() => () => URL.revokeObjectURL(preview), [preview])

  function pick(list: FileList | null | undefined) {
    const picked = [...(list ?? [])].find((f) => f.type.startsWith('image/'))
    if (!picked) return
    ingest.reset()
    setFile(picked)
    setPreview(URL.createObjectURL(picked))
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    pick(e.dataTransfer.files)
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    if (patientId.trim()) form.append('patient_id', patientId.trim())
    form.append('indication', indication)
    ingest.mutate(form, {
      onSuccess: ({ id }) => {
        setFile(null)
        setPreview('')
        onDone(id)
      },
    })
  }

  return (
    <form onSubmit={submit} className="space-y-3" noValidate>
      <div
        role="button"
        tabIndex={0}
        aria-label={t('drop.title')}
        onClick={() => input.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            input.current?.click()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'relative flex cursor-pointer items-center justify-center overflow-hidden rounded-lg border-2 border-dashed text-center text-sm transition focus-visible:outline-2 focus-visible:outline-cyan-600',
          file ? 'py-3' : 'aspect-[4/3]',
          dragging ? 'border-cyan-600 bg-cyan-50 dark:bg-cyan-950/30' : 'border-slate-300 hover:border-cyan-600 dark:border-slate-700',
        )}
      >
        {file ? (
          <img src={preview} alt={t('selectedPhoto')} className="max-h-56 rounded object-contain" />
        ) : (
          <div className="px-4 text-slate-500">
            <div className="font-medium text-slate-700 dark:text-slate-200">{t('drop.title')}</div>
            <div className="mt-1 text-xs">{t('drop.formats')}</div>
          </div>
        )}
        <input
          ref={input}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => {
            pick(e.target.files)
            e.target.value = '' // allow picking the same file again
          }}
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      <Button type="submit" variant="primary" block disabled={!file || ingest.isPending}>
        {ingest.isPending ? t('submitting') : t('submit')}
      </Button>
    </form>
  )
}

/** Phone on the eyepiece, streamed over USB (UVC) or local Wi-Fi (RTSP/HTTP); see backend/app/capture. */
function CameraForm({ patientId, indication, onDone }: FormProps) {
  const { t } = useTranslation('upload')
  const status = useCaptureStatus()
  const { start, stop, snapshot } = useCaptureControl()
  const [source, setSource] = useStoredState('pathtriage.captureSource', 'uvc:0')
  const active = !!status.data?.active
  const error = useErrorText(start.error ?? stop.error ?? snapshot.error ?? status.error)

  return (
    <div className="space-y-3">
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">{t('camera.source')}</span>
        <div className="flex gap-2">
          <input
            className={fieldClass}
            value={source}
            disabled={active}
            onChange={(e) => setSource(e.target.value)}
            placeholder="uvc:0 · rtsp://192.168.1.20:8554/live"
            spellCheck={false}
          />
          {active ? (
            <Button disabled={stop.isPending} onClick={() => stop.mutate()}>
              {t('camera.disconnect')}
            </Button>
          ) : (
            <Button disabled={!source.trim() || start.isPending} onClick={() => start.mutate(source.trim())}>
              {start.isPending ? t('camera.connecting') : t('camera.connect')}
            </Button>
          )}
        </div>
        <span className="mt-1 block text-[11px] text-slate-500">{t('camera.sourceHint')}</span>
      </label>

      <p role="status" className="flex items-center gap-2 text-sm">
        <span className={cn('size-2 rounded-full', active ? 'bg-emerald-500' : 'bg-slate-400')} />
        {active ? t('camera.connected', { source: status.data?.source }) : t('camera.disconnected')}
      </p>

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      <Button
        variant="primary"
        block
        disabled={!active || snapshot.isPending}
        onClick={() =>
          snapshot.mutate(
            { patient_id: patientId.trim() || undefined, indication },
            { onSuccess: ({ id }) => onDone(id) },
          )
        }
      >
        {snapshot.isPending ? t('submitting') : t('camera.capture')}
      </Button>
    </div>
  )
}
