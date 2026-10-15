import * as Dialog from '@radix-ui/react-dialog'
import { useTranslation } from 'react-i18next'

import type { SetupProfile } from '../../shared/api/types.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { SetupForm, SetupList } from './Calibration.tsx'

/** Microscope calibration in a dialog over the worklist (opened from the New slide panel). */
export function CalibrationDialog({
  open,
  onOpenChange,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** A setup was saved: the caller selects it; the dialog then closes. */
  onSaved: (setup: SetupProfile) => void
}) {
  const { t } = useTranslation(['calibrate', 'common'])
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[2000] bg-black/60 backdrop-blur-sm" />
        <Dialog.Content
          aria-describedby={undefined}
          className="panel fixed top-1/2 left-1/2 z-[2001] max-h-[calc(100dvh-2rem)] w-[min(48rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 space-y-6 overflow-y-auto p-5"
        >
          <div className="flex items-center justify-between gap-4">
            <Dialog.Title className="font-display text-[17px] font-bold tracking-[-0.01em]">{t('title')}</Dialog.Title>
            <Dialog.Close asChild>
              <Button size="sm">{t('close')}</Button>
            </Dialog.Close>
          </div>
          <SetupList />
          <SetupForm
            onSaved={(setup) => {
              onSaved(setup)
              onOpenChange(false)
            }}
          />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
