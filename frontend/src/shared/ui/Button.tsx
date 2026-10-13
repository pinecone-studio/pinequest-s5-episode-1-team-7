import type { ButtonHTMLAttributes } from 'react'

import { cn } from '../lib/cn.ts'

const VARIANT = {
  primary: 'bg-cyan-700 font-semibold text-white hover:bg-cyan-800',
  secondary:
    'border border-slate-300 bg-white text-slate-800 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800',
  danger: 'bg-red-600 font-semibold text-white hover:bg-red-700',
  success: 'bg-emerald-600 font-semibold text-white hover:bg-emerald-700',
  warning: 'bg-amber-500 font-semibold text-slate-950 hover:bg-amber-600',
  link: 'text-cyan-700 hover:underline dark:text-cyan-400',
} as const

const SIZE = { sm: 'px-3 py-1.5 text-sm', md: 'px-4 py-2 text-sm', none: '' } as const

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof VARIANT
  size?: keyof typeof SIZE
  block?: boolean
}

export function Button({ variant = 'secondary', size = 'md', block, className, type = 'button', ...rest }: Props) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-md transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600 disabled:cursor-not-allowed disabled:opacity-40',
        VARIANT[variant],
        variant === 'link' ? SIZE.none : SIZE[size],
        block && 'w-full',
        className,
      )}
      {...rest}
    />
  )
}
