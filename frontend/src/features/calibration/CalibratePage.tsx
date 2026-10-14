import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../shared/api/client.ts'
import { useCreateSetup, useDeleteSetup, useSetups } from '../../shared/api/queries.ts'
import { OBJECTIVES, type Objective, type SetupProfile } from '../../shared/api/types.ts'
import { useDocumentTitle } from '../../shared/lib/hooks.ts'
import { useImageSize } from '../viewer/useImageSize.ts'
import { Alert } from '../../shared/ui/Alert.tsx'
import { Button } from '../../shared/ui/Button.tsx'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog.tsx'
import { fieldClass } from '../../shared/ui/field.ts'
import { SegmentedControl } from '../../shared/ui/SegmentedControl.tsx'
import { umPerPx, type Point } from './scale.ts'

/**
 * Stage-micrometer calibration (issue #35): one setup per microscope + phone +
 * adapter. The technician photographs a stage micrometer, clicks two marks a known
 * distance apart, and the app stores µm/px at the objective used. Every later
 * capture names this setup plus its objective, and the engine resizes to its
 * training magnification from that.
 */
export function CalibratePage() {
  const { t } = useTranslation('calibrate')
  useDocumentTitle(`${t('title')} · PathTriage`)
  return (
    <main className="mx-auto max-w-3xl space-y-8 p-4 md:p-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{t('intro')}</p>
      </div>
      <SetupList />
      <SetupForm />
    </main>
  )
}

function SetupList() {
  const { t } = useTranslation(['calibrate', 'common'])
  const setups = useSetups()
  const remove = useDeleteSetup()
  const [confirmId, setConfirmId] = useState<number | null>(null)
  const list = Array.isArray(setups.data) ? setups.data : []
  const target: SetupProfile | undefined = list.find((s) => s.id === confirmId)

  return (
    <section aria-label={t('setups.title')} className="space-y-2">
      <h2 className="text-sm font-semibold">{t('setups.title')}</h2>
      {setups.isPending && <p className="text-sm text-slate-500">{t('common:status.loading')}</p>}
      {list.length === 0 && !setups.isPending && <p className="text-sm text-slate-500">{t('setups.empty')}</p>}
      <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
        {list.map((s) => (
          <li key={s.id} className="flex items-center gap-3 p-3">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{s.name}</p>
              <p className="text-xs text-slate-500">
                {t('setups.umPerPx', { value: s.um_per_px.toFixed(2), objective: s.calibration_objective })}
                {s.phone_resolution ? ` · ${t('setups.resolution', { value: s.phone_resolution })}` : ''}
              </p>
            </div>
            <Button variant="danger" disabled={remove.isPending} onClick={() => setConfirmId(s.id)}>
              {t('setups.delete')}
            </Button>
          </li>
        ))}
      </ul>
      {remove.error && (
        <Alert tone="error">
          {remove.error instanceof ApiError && remove.error.status === 409 ? t('error.inUse') : t('error.rejected', { detail: messageOf(remove.error) })}
        </Alert>
      )}
      <ConfirmDialog
        open={confirmId != null}
        onOpenChange={(open) => !open && setConfirmId(null)}
        title={t('setups.delete')}
        confirmLabel={t('setups.delete')}
        confirmVariant="danger"
        busy={remove.isPending}
        onConfirm={() => target && remove.mutate(target.id, { onSuccess: () => setConfirmId(null) })}
      >
        {target && <p>{t('setups.confirmDelete', { name: target.name })}</p>}
      </ConfirmDialog>
    </section>
  )
}

function SetupForm() {
  const { t } = useTranslation(['calibrate', 'common'])
  const create = useCreateSetup()
  const [name, setName] = useState('')
  const [objective, setObjective] = useState<Objective>('40x')
  const [resolution, setResolution] = useState('')
  const [photo, setPhoto] = useState('')
  const [marks, setMarks] = useState<Point[]>([])
  const [distance, setDistance] = useState('')
  const [saved, setSaved] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const { size } = useImageSize(photo)

  useEffect(() => () => URL.revokeObjectURL(photo), [photo])

  const pick = (list: FileList | null | undefined) => {
    const picked = [...(list ?? [])].find((f) => f.type.startsWith('image/'))
    if (!picked) return
    if (photo) URL.revokeObjectURL(photo)
    create.reset()
    setSaved(null)
    setMarks([])
    setPhoto(URL.createObjectURL(picked))
  }

  /** Clicks become natural-pixel marks, so µm/px does not depend on display size. */
  const onPhotoClick = (e: MouseEvent<HTMLImageElement>) => {
    e.stopPropagation() // or the drop-zone underneath would reopen the file picker
    if (!size) return
    const rect = e.currentTarget.getBoundingClientRect()
    const point = {
      x: ((e.clientX - rect.left) / rect.width) * size.width,
      y: ((e.clientY - rect.top) / rect.height) * size.height,
    }
    setMarks((prev) => (prev.length >= 2 ? [point] : [...prev, point]))
  }

  const value = marks.length === 2 ? umPerPx(marks[0], marks[1], Number(distance)) : null
  const canSave = name.trim() !== '' && value != null && !create.isPending

  const submit = () => {
    if (!canSave || value == null) return
    create.mutate(
      {
        name: name.trim(),
        um_per_px: value,
        calibration_objective: objective,
        phone_resolution: resolution.trim() || undefined,
      },
      {
        onSuccess: (setup) => {
          setSaved(t('form.saved', { name: setup.name, value: setup.um_per_px.toFixed(2) }))
          setName('')
          setResolution('')
          setDistance('')
          setMarks([])
          if (photo) URL.revokeObjectURL(photo)
          setPhoto('')
        },
      },
    )
  }

  return (
    <section aria-label={t('calibrate:form.title')} className="space-y-3">
      <h2 className="text-sm font-semibold">{t('calibrate:form.title')}</h2>

      <label className="block">
        <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">{t('calibrate:form.name')}</span>
        <input className={fieldClass} value={name} onChange={(e) => setName(e.target.value)} placeholder={t('calibrate:form.namePlaceholder')} autoComplete="off" />
      </label>

      <div>
        <span aria-hidden className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">
          {t('calibrate:form.objective')}
        </span>
        <SegmentedControl
          label={t('calibrate:form.objective')}
          value={objective}
          onChange={setObjective}
          options={OBJECTIVES.map((o) => ({ value: o, label: o }))}
        />
      </div>

      <label className="block">
        <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">{t('calibrate:form.resolution')}</span>
        <input
          className={fieldClass}
          value={resolution}
          onChange={(e) => setResolution(e.target.value)}
          placeholder={t('calibrate:form.resolutionPlaceholder')}
          autoComplete="off"
          spellCheck={false}
        />
      </label>

      <div>
        <span aria-hidden className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">
          {t('calibrate:form.marks')}
        </span>
        <div
          role="button"
          tabIndex={0}
          aria-label={t('calibrate:form.marks')}
          onClick={() => input.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              input.current?.click()
            }
          }}
          className="relative flex cursor-pointer items-center justify-center overflow-hidden rounded-lg border-2 border-dashed border-slate-300 text-center text-sm hover:border-cyan-600 focus-visible:outline-2 focus-visible:outline-cyan-600 dark:border-slate-700"
        >
          {photo ? (
            <div className="relative">
              <img src={photo} alt={t('calibrate:form.photo')} className="max-h-80 object-contain" onClick={onPhotoClick} />
              {size &&
                marks.map((m, i) => (
                  <span
                    key={i}
                    aria-hidden
                    className="absolute flex size-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-cyan-600 text-xs font-bold text-white"
                    style={{ left: `${(m.x / size.width) * 100}%`, top: `${(m.y / size.height) * 100}%` }}
                  >
                    {i === 0 ? 'A' : 'B'}
                  </span>
                ))}
            </div>
          ) : (
            <div className="px-4 py-10 text-slate-500">
              <div className="font-medium text-slate-700 dark:text-slate-200">{t('calibrate:form.photo')}</div>
              <div className="mt-1 text-xs">{t('calibrate:form.photoHint')}</div>
            </div>
          )}
          <input
            ref={input}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              pick(e.target.files)
              e.target.value = ''
            }}
          />
        </div>
        <p className="mt-1 text-[11px] text-slate-500">{photo ? t('calibrate:form.marksHint') : t('calibrate:form.photoHint')}</p>
      </div>

      <label className="block">
        <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">{t('calibrate:form.distance')}</span>
        <input
          className={fieldClass}
          type="number"
          min={0}
          step="any"
          inputMode="decimal"
          value={distance}
          onChange={(e) => setDistance(e.target.value)}
        />
      </label>

      <p role="status" className="text-sm text-slate-600 dark:text-slate-300">
        {value != null ? t('calibrate:form.result', { value: value.toFixed(3) }) : t('calibrate:form.needMarks')}
      </p>

      {create.error && (
        <Alert tone="error">
          {create.error instanceof ApiError && create.error.message.includes('already exists')
            ? t('calibrate:error.duplicate')
            : t('calibrate:error.rejected', { detail: messageOf(create.error) })}
        </Alert>
      )}
      {saved && (
        <Alert tone="info">
          <p>{saved}</p>
        </Alert>
      )}

      <Button variant="primary" block disabled={!canSave} onClick={submit}>
        {create.isPending ? t('calibrate:form.saving') : t('calibrate:form.save')}
      </Button>
    </section>
  )
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
