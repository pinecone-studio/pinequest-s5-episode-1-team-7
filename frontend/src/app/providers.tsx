import { QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'
import { I18nextProvider } from 'react-i18next'
import { BrowserRouter, HashRouter } from 'react-router-dom'

import i18n from '../i18n/index.ts'
import { createQueryClient } from './queryClient.ts'

/** Pages loaded from disk (the desktop app) can't use path URLs, so they route on the #hash instead. */
const Router = window.location.protocol === 'file:' ? HashRouter : BrowserRouter

export function AppProviders({ children }: { children: ReactNode }) {
  const [client] = useState(createQueryClient)
  return (
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={client}>
        <Router>{children}</Router>
      </QueryClientProvider>
    </I18nextProvider>
  )
}
