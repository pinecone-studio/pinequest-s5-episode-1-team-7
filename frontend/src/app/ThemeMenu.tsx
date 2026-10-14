import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { useTranslation } from 'react-i18next'

import { setTheme, type Theme, THEMES, useTheme } from './theme.ts'

const ICON: Record<Theme, string> = {
  light:
    'M10 2a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 10 2Zm0 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm7.25 3.25a.75.75 0 0 1 0 1.5h-1.5a.75.75 0 0 1 0-1.5h1.5ZM4.25 10a.75.75 0 0 1-.75.75H2a.75.75 0 0 1 0-1.5h1.5a.75.75 0 0 1 .75.75ZM10 15a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 10 15Zm5.3-10.3a.75.75 0 0 1 0 1.06l-1.06 1.06a.75.75 0 1 1-1.06-1.06l1.06-1.06a.75.75 0 0 1 1.06 0ZM6.82 13.18a.75.75 0 0 1 0 1.06L5.76 15.3a.75.75 0 0 1-1.06-1.06l1.06-1.06a.75.75 0 0 1 1.06 0Zm8.48 2.12a.75.75 0 0 1-1.06 0l-1.06-1.06a.75.75 0 1 1 1.06-1.06l1.06 1.06a.75.75 0 0 1 0 1.06ZM6.82 6.82a.75.75 0 0 1-1.06 0L4.7 5.76A.75.75 0 0 1 5.76 4.7l1.06 1.06a.75.75 0 0 1 0 1.06Z',
  dark: 'M7.46 2.2a.75.75 0 0 1 .17.82 6 6 0 0 0 7.35 7.35.75.75 0 0 1 .99.99A7.5 7.5 0 1 1 6.64 2.03a.75.75 0 0 1 .82.17Z',
  system:
    'M2 4.75A1.75 1.75 0 0 1 3.75 3h12.5A1.75 1.75 0 0 1 18 4.75v8.5A1.75 1.75 0 0 1 16.25 15h-4.5l.5 1.5h1a.75.75 0 0 1 0 1.5h-6.5a.75.75 0 0 1 0-1.5h1l.5-1.5h-4.5A1.75 1.75 0 0 1 2 13.25v-8.5Zm1.75-.25a.25.25 0 0 0-.25.25v8.5c0 .14.11.25.25.25h12.5a.25.25 0 0 0 .25-.25v-8.5a.25.25 0 0 0-.25-.25H3.75Z',
}

function Icon({ theme }: { theme: Theme }) {
  return (
    <svg viewBox="0 0 20 20" className="size-4" fill="currentColor" aria-hidden>
      <path fillRule="evenodd" clipRule="evenodd" d={ICON[theme]} />
    </svg>
  )
}

/** Header button: Light, Dark, or follow the device. */
export function ThemeMenu() {
  const { t } = useTranslation()
  const theme = useTheme()
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger
        aria-label={t('theme.label', { theme: t(`theme.${theme}`) })}
        title={t(`theme.${theme}`)}
        className="flex size-8 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-cyan-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:text-white"
      >
        <Icon theme={theme} />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={6}
          className="z-[1500] min-w-44 rounded-lg border border-slate-200 bg-white p-1 text-sm shadow-xl dark:border-slate-700 dark:bg-slate-900"
        >
          <DropdownMenu.RadioGroup value={theme} onValueChange={(value) => setTheme(value as Theme)}>
            {THEMES.map((option) => (
              <DropdownMenu.RadioItem
                key={option}
                value={option}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 outline-none select-none data-[highlighted]:bg-slate-100 data-[state=checked]:font-medium data-[state=checked]:text-cyan-700 dark:data-[highlighted]:bg-slate-800 dark:data-[state=checked]:text-cyan-400"
              >
                <Icon theme={option} />
                {t(`theme.${option}`)}
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
