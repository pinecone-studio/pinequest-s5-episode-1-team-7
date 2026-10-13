import { cn } from '../lib/cn.ts'

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn('inline-block size-3 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent', className)}
    />
  )
}
