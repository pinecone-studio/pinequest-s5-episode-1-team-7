import type { ButtonHTMLAttributes } from 'react'

import { cn } from '../lib/cn.ts'

const VARIANT = {
  // Muted eucalyptus: solid but not neon.
  primary: 'bg-mist font-semibold text-mist-ink hover:bg-mist-strong shadow-[0_8px_20px_-10px_rgb(63_111_102/0.5)] dark:shadow-[0_8px_20px_-10px_rgb(127_179_168/0.6)]',
  secondary:
    'border border-line bg-raised text-ink hover:border-mist-dim hover:bg-overlay',
  danger:
    'border border-[#dfb9b9] bg-[#f3e2e2] font-semibold text-[#7a3535] hover:bg-[#ecd4d4] dark:border-[#5a3436] dark:bg-[#3a2426] dark:text-[#eec3c3] dark:hover:bg-[#4a2d30]',
  success:
    'border border-[#b3d4c2] bg-[#e2efe6] font-semibold text-[#2f6b4e] hover:bg-[#d3e6da] dark:border-[#2f4a3e] dark:bg-[#22382f] dark:text-[#b7dcc4] dark:hover:bg-[#2a4438]',
  warning:
    'border border-[#d8c49a] bg-[#f2e8d3] font-semibold text-[#6d5220] hover:bg-[#e9dcbd] dark:border-[#57492f] dark:bg-[#3d3524] dark:text-[#e6cf9c] dark:hover:bg-[#4a402c]',
  link: 'text-mist hover:text-mist-strong hover:underline',
} as const

const SIZE = { sm: 'min-h-8 px-3 py-1.5 text-[13px]', md: 'min-h-10 px-4 py-2 text-sm', none: '' } as const

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
        'inline-flex items-center justify-center gap-2 rounded-[10px] font-display font-semibold tracking-[-0.005em] transition duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mist disabled:cursor-not-allowed disabled:opacity-40',
        VARIANT[variant],
        variant === 'link' ? SIZE.none : SIZE[size],
        block && 'w-full',
        className,
      )}
      {...rest}
    />
  )
}
