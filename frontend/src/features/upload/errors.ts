import { ApiError } from '../../shared/api/client.ts'

export type IngestErrorKey = 'offline' | 'blurry' | 'unreadable' | 'tooLarge' | 'badSource' | 'cameraUnavailable' | 'cameraOff'

/**
 * Recognises the backend's ingest and capture errors (backend/app/ingest.py, quality.py,
 * capture/source.py) so they can be shown in the viewer's language. Unknown errors return undefined
 * and are shown with the backend's own message.
 */
export function ingestErrorKey(error: unknown): IngestErrorKey | undefined {
  if (!(error instanceof ApiError)) return undefined
  const message = error.message.toLowerCase()
  if (error.status === 0) return 'offline'
  if (message.includes('too blurry')) return 'blurry'
  if (message.includes('not a valid image') || message.includes('empty file')) return 'unreadable'
  if (message.includes('larger than') || error.status === 413) return 'tooLarge'
  if (message.includes('source must') || message.includes('uvc source')) return 'badSource'
  if (error.status === 502) return 'cameraUnavailable'
  if (error.status === 409) return 'cameraOff'
  return undefined
}
