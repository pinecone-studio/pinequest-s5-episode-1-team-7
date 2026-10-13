import { QueryClient } from '@tanstack/react-query'

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      // Everything is polled, so one quick retry is enough; the next poll tries again.
      queries: { retry: 1, staleTime: 1000 },
    },
  })
}
