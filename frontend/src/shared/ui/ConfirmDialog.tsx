import * as Dialog from '@radix-ui/react-dialog'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from './Button.tsx'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  children: ReactNode
  confirmLabel: string
  confirmVariant?: 'primary' | 'danger' | 'success' | 'warning'
  busy?: boolean
  error?: string
  onConfirm: () => void
}

/** Modal that asks before an action that changes a patient's case. */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  children,
  confirmLabel,
  confirmVariant = 'primary',
  busy,
  error,
  onConfirm,
}: Props) {
  const { t } = useTranslation()
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[2000] bg-black/60 backdrop-blur-sm" />
        <Dialog.Content className="panel fixed top-1/2 left-1/2 z-[2001] w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 p-5">
          <Dialog.Title className="font-display text-[17px] font-bold tracking-[-0.01em]">{title}</Dialog.Title>
          <Dialog.Description asChild>
            <div className="mt-2 space-y-2 text-sm leading-relaxed text-ink-dim">{children}</div>
          </Dialog.Description>
          {error && <p className="mt-3 text-sm text-critical">{error}</p>}
          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button disabled={busy}>{t('action.cancel')}</Button>
            </Dialog.Close>
            <Button variant={confirmVariant} disabled={busy} onClick={onConfirm}>
              {busy ? t('status.saving') : confirmLabel}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
