import type { ReactNode } from 'react'

import { cn } from '../lib/cn.ts'

const TONE = {
  error: 'border-[#dfb9b9] bg-[#f7e8e8] text-[#7a3535] dark:border-[#5a3436] dark:bg-[#2a1e20] dark:text-[#e3b8b8]',
  warning: 'border-[#d8c49a] bg-[#f4ecd9] text-[#6d5220] dark:border-[#57492f] dark:bg-[#29241a] dark:text-[#dcc79a]',
  info: 'border-[#a9c0d8] bg-[#e6edf5] text-[#2f4a63] dark:border-[#33465c] dark:bg-[#1b2634] dark:text-[#aec6e2]',
  ok: 'border-[#b3d4c2] bg-[#e4efe7] text-[#2f6b4e] dark:border-[#2f4a3e] dark:bg-[#1c2b24] dark:text-[#aed6ba]',
} as const

export function Alert({ tone, children, className }: { tone: keyof typeof TONE; children: ReactNode; className?: string }) {
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={cn('rounded-[10px] border px-3 py-2 text-sm leading-relaxed', TONE[tone], className)}>
      {children}
    </div>
  )
}
