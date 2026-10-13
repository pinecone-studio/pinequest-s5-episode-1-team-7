import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import i18n from '../i18n/index.ts'
import { renderWithProviders } from '../test/render.tsx'
import { DisclaimerBanner } from './DisclaimerBanner.tsx'
import { LanguageSwitcher } from './LanguageSwitcher.tsx'

describe('LanguageSwitcher', () => {
  it('switches the whole UI, the <html lang> and remembers the choice', async () => {
    await i18n.changeLanguage('mn')
    renderWithProviders(
      <>
        <LanguageSwitcher />
        <DisclaimerBanner />
      </>,
    )
    expect(screen.getByText('Эрэмбэлэх туслах хэрэгсэл, оношлох систем биш.')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('radio', { name: 'EN' }))
    expect(screen.getByText('Prioritisation assistant, not a diagnostic engine.')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'EN' })).toHaveAttribute('aria-checked', 'true')
    expect(document.documentElement.lang).toBe('en')
    expect(localStorage.getItem('pathtriage.language')).toBe('en')
  })
})
