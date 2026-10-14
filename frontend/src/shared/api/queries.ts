import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client.ts'
import { type Decision, type Indication, type Objective, PROCESSING_STATES, type QueueSort, type Slide } from './types.ts'

/** Polling intervals (ms). Queries pause while the tab is hidden. */
const POLL = { queue: 4000, slide: 2500, health: 15000, capture: 5000 } as const

export const queryKeys = {
  slides: ['slides'] as const,
  queue: (sort: QueueSort) => ['slides', 'queue', sort] as const,
  all: ['slides', 'all'] as const,
  slide: (id: number | string) => ['slides', 'detail', String(id)] as const,
  events: (id: number | string) => ['slides', 'events', String(id)] as const,
  health: ['health'] as const,
  capture: ['capture'] as const,
  setups: ['setups'] as const,
  model: ['model'] as const,
}

/** The pipeline is still working on the slide, so it will change on its own. */
export const isProcessing = (s: Slide | undefined) => !s || PROCESSING_STATES.includes(s.state)

export function useQueue(sort: QueueSort) {
  return useQuery({ queryKey: queryKeys.queue(sort), queryFn: () => api.queue(sort), refetchInterval: POLL.queue })
}

/** Every slide (all states), for the processing, under-review and archived lists. */
export function useAllSlides() {
  return useQuery({ queryKey: queryKeys.all, queryFn: () => api.slides(), refetchInterval: POLL.queue })
}

export function useSlide(id: string) {
  return useQuery({
    queryKey: queryKeys.slide(id),
    queryFn: () => api.slide(id),
    refetchInterval: (query) => (isProcessing(query.state.data) ? POLL.slide : false),
  })
}

export function useEvents(id: string, state: Slide['state'] | undefined) {
  return useQuery({
    // Refetched whenever the slide changes state.
    queryKey: [...queryKeys.events(id), state],
    queryFn: () => api.events(id),
    enabled: state != null,
  })
}

export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: api.health, refetchInterval: POLL.health, retry: false })
}

/** Stores a slide returned by a mutation and refreshes every list. */
function useSlideWriter() {
  const client = useQueryClient()
  return (slide: Slide) => {
    client.setQueryData(queryKeys.slide(slide.id), slide)
    return client.invalidateQueries({ queryKey: queryKeys.slides })
  }
}

function useInvalidateSlides() {
  const client = useQueryClient()
  return () => client.invalidateQueries({ queryKey: queryKeys.slides })
}

export function useIngest() {
  const refresh = useInvalidateSlides()
  return useMutation({ mutationFn: api.ingest, onSuccess: refresh })
}

export function useOpenSlide(id: number) {
  const write = useSlideWriter()
  return useMutation({ mutationFn: () => api.open(id), onSuccess: write })
}

export function useDecide(id: number) {
  const write = useSlideWriter()
  return useMutation({ mutationFn: (decision: Decision) => api.decide(id, decision), onSuccess: write })
}

export function useReassignPriority(id: number) {
  const write = useSlideWriter()
  return useMutation({ mutationFn: (priority: number) => api.reassignPriority(id, priority), onSuccess: write })
}

export function useRetry(id: number) {
  const write = useSlideWriter()
  return useMutation({ mutationFn: () => api.retry(id), onSuccess: write })
}

export function useCaptureStatus() {
  return useQuery({ queryKey: queryKeys.capture, queryFn: api.captureStatus, refetchInterval: POLL.capture })
}

export function useCaptureControl() {
  const client = useQueryClient()
  const store = (status: Awaited<ReturnType<typeof api.captureStatus>>) => client.setQueryData(queryKeys.capture, status)
  const refresh = useInvalidateSlides()
  return {
    start: useMutation({ mutationFn: api.captureStart, onSuccess: store }),
    stop: useMutation({ mutationFn: api.captureStop, onSuccess: store }),
    snapshot: useMutation({
      mutationFn: (body: { patient_id?: string; indication: Indication; setup_id?: number; objective?: Objective }) =>
        api.captureSnapshot(body),
      onSuccess: refresh,
    }),
  }
}

/** Calibrated microscope + phone setups for the magnification pickers (issue #35). */
export function useSetups() {
  return useQuery({ queryKey: queryKeys.setups, queryFn: api.setups })
}

export function useCreateSetup() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: api.createSetup,
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.setups }),
  })
}

export function useDeleteSetup() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: api.deleteSetup,
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.setups }),
  })
}

/** The model card + live model status for the About page. Static per deployment: no polling. */
export function useModelInfo() {
  return useQuery({ queryKey: queryKeys.model, queryFn: api.model })
}
