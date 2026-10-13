import { QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'
import { I18nextProvider } from 'react-i18next'
import { BrowserRouter } from 'react-router-dom'

import i18n from '../i18n/index.ts'
import { createQueryClient } from './queryClient.ts'

export function AppProviders({ children }: { children: ReactNode }) {
  const [client] = useState(createQueryClient)
  return (
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={client}>
        <BrowserRouter>{children}</BrowserRouter>
      </QueryClientProvider>
    </I18nextProvider>
  )
}
