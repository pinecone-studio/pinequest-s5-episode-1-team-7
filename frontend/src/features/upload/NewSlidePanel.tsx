import { type DragEvent, type FormEvent, useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { useIngest, useSetups } from '../../shared/api/queries.ts'
import { OBJECTIVES, type Indication, type Objective } from '../../shared/api/types.ts'
import { cn } from '../../shared/lib/cn.ts'
import { useStoredState } from '../../shared/lib/hooks.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { fieldClass } from '../../shared/ui/field.ts'
import { SegmentedControl } from '../../shared/ui/SegmentedControl.tsx'
import { ingestErrorKey } from './errors.ts'

/** Adds a slide by uploading a photo taken with the phone on the microscope (TDD 2.1, 3.1). */
export function NewSlidePanel() {
  const { t } = useTranslation(['upload', 'common'])
  const ids = useId()
  const [patientId, setPatientId] = useState('')
  const [indication, setIndication] = useState<Indication>('Routine')
  const [done, setDone] = useState<number | null>(null)
  const [setupId, setSetupId] = useStoredState<number | null>('pathtriage.setupId', null)
  const [objective, setObjective] = useStoredState<Objective>('pathtriage.objective', '40x')

  const reset = (id: number) => {
    setPatientId('')
    setIndication('Routine')
    setDone(id)
  }

  return (
    <div className="space-y-3">
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

      <ScaleFields setupId={setupId} onSetupChange={setSetupId} objective={objective} onObjectiveChange={setObjective} />

      <UploadForm patientId={patientId} indication={indication} onDone={reset} setupId={setupId} objective={objective} />
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
  /** Calibrated setup + objective, issue #35. Null setup means captured resolution. */
  setupId: number | null
  objective: Objective
}

/** Microscope setup + objective pickers for the upload form. */
function ScaleFields({
  setupId,
  onSetupChange,
  objective,
  onObjectiveChange,
}: {
  setupId: number | null
  onSetupChange: (id: number | null) => void
  objective: Objective
  onObjectiveChange: (o: Objective) => void
}) {
  const { t } = useTranslation('upload')
  const setups = useSetups()
  const list = Array.isArray(setups.data) ? setups.data : []
  const selected = list.find((s) => s.id === setupId) ?? null

  return (
    <div className="grid grid-cols-2 gap-2">
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">{t('setup.label')}</span>
        <select
          className={fieldClass}
          value={setupId ?? ''}
          onChange={(e) => {
            const id = e.target.value === '' ? null : Number(e.target.value)
            onSetupChange(id)
            // A fresh setup starts at the objective it was calibrated at.
            const next = list.find((s) => s.id === id)
            if (next && (OBJECTIVES as readonly string[]).includes(next.calibration_objective)) {
              onObjectiveChange(next.calibration_objective as Objective)
            }
          }}
        >
          <option value="">{t('setup.none')}</option>
          {list.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">{t('objective.label')}</span>
        <select
          className={fieldClass}
          value={objective}
          disabled={selected == null}
          title={selected == null ? t('setup.hint') : t('objective.hint')}
          onChange={(e) => onObjectiveChange(e.target.value as Objective)}
        >
          {OBJECTIVES.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </label>
      <p className="col-span-2 text-[11px] text-slate-500">
        {t('setup.hint')} <Link to="/calibrate" className="text-cyan-700 underline dark:text-cyan-400">{t('setup.calibrate')}</Link>
      </p>
    </div>
  )
}

function useErrorText(error: unknown) {
  const { t } = useTranslation('upload')
  if (!error) return ''
  const key = ingestErrorKey(error)
  return key ? t(`error.${key}`) : t('error.rejected', { detail: error instanceof Error ? error.message : String(error) })
}

function UploadForm({ patientId, indication, onDone, setupId, objective }: FormProps) {
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
    if (setupId != null) {
      form.append('setup_id', String(setupId))
      form.append('objective', objective)
    }
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
