import { useSyncExternalStore } from 'react'

/**
 * Light / dark appearance. "system" follows the operating system and changes with it.
 * index.html applies the stored choice before first paint, so a dark page never flashes white.
 */
export const THEMES = ['light', 'dark', 'system'] as const
export type Theme = (typeof THEMES)[number]

const STORAGE_KEY = 'pathtriage.theme'
const dark = window.matchMedia?.('(prefers-color-scheme: dark)')

const isTheme = (value: unknown): value is Theme => THEMES.includes(value as Theme)

function stored(): Theme {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return isTheme(value) ? value : 'system'
  } catch {
    return 'system'
  }
}

let current = stored()
const listeners = new Set<() => void>()

function apply() {
  const isDark = current === 'dark' || (current === 'system' && !!dark?.matches)
  document.documentElement.classList.toggle('dark', isDark)
}

export function setTheme(theme: Theme) {
  current = theme
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* storage unavailable (private mode): the choice lasts for this page only */
  }
  apply()
  listeners.forEach((listener) => listener())
}

dark?.addEventListener('change', apply)
apply()

const subscribe = (listener: () => void) => {
  listeners.add(listener)
  return () => void listeners.delete(listener)
}

export const useTheme = () => useSyncExternalStore(subscribe, () => current)
