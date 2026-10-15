import type { ReactNode } from 'react'

import { cn } from '../lib/cn.ts'

/**
 * Colour budget: errors are magenta-pink, clearly distinct from the
 * orange-red risk flag. Each tone also carries an icon so meaning never
 * relies on colour alone.
 */
const TONE = {
  error: 'border-[#dfa3be] bg-[#f9e3ec] text-[#8e2a5b] dark:border-[#6b3450] dark:bg-[#38222e] dark:text-[#f0a6c8]',
  warning: 'border-[#d8c49a] bg-[#f4ecd9] text-[#6d5220] dark:border-[#57492f] dark:bg-[#29241a] dark:text-[#dcc79a]',
  info: 'border-[#a9c0d8] bg-[#e6edf5] text-[#2f4a63] dark:border-[#33465c] dark:bg-[#1b2634] dark:text-[#aec6e2]',
  ok: 'border-[#b3d4c2] bg-[#e4efe7] text-[#2f6b4e] dark:border-[#2f4a3e] dark:bg-[#1c2b24] dark:text-[#aed6ba]',
} as const

function ToneIcon({ tone }: { tone: keyof typeof TONE }) {
  if (tone === 'error') {
    return (
      <svg viewBox="0 0 16 16" className="mt-0.5 size-4 shrink-0" fill="currentColor" aria-hidden>
        <path d="M8 1.2 15.2 14H.8L8 1.2Zm0 4.1L4.4 12.4h7.2L8 5.3ZM7.2 7.4h1.6v3H7.2v-3Zm0 3.6h1.6v1.6H7.2V11Z" />
      </svg>
    )
  }
  if (tone === 'warning') {
    return (
      <svg viewBox="0 0 16 16" className="mt-0.5 size-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden>
        <path d="M8 1.5 15 14H1L8 1.5Z" strokeLinejoin="round" />
        <path d="M8 6v3.4" strokeLinecap="round" />
        <circle cx="8" cy="11.6" r="0.9" fill="currentColor" stroke="none" />
      </svg>
    )
  }
  if (tone === 'ok') {
    return (
      <svg viewBox="0 0 16 16" className="mt-0.5 size-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden>
        <circle cx="8" cy="8" r="6.5" />
        <path d="m5.4 8.2 1.9 1.9 3.3-3.9" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 16 16" className="mt-0.5 size-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden>
      <circle cx="8" cy="8" r="6.5" />
      <path d="M8 7.4v3.4" strokeLinecap="round" />
      <circle cx="8" cy="5.2" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  )
}

export function Alert({ tone, children, className }: { tone: keyof typeof TONE; children: ReactNode; className?: string }) {
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={cn('flex items-start gap-2 rounded-[10px] border px-3 py-2 text-sm leading-relaxed', TONE[tone], className)}>
      <ToneIcon tone={tone} />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}
