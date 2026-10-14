import { ApiError } from '../../shared/api/client.ts'

export type IngestErrorKey = 'offline' | 'blurry' | 'unreadable' | 'tooLarge' | 'unknownSetup'

/**
 * Recognises the backend's upload errors (backend/app/ingest.py, quality.py,
 * setups.py) so they can be shown in the viewer's language. Unknown errors return undefined
 * and are shown with the backend's own message.
 */
export function ingestErrorKey(error: unknown): IngestErrorKey | undefined {
  if (!(error instanceof ApiError)) return undefined
  const message = error.message.toLowerCase()
  if (error.status === 0) return 'offline'
  if (message.includes('too blurry')) return 'blurry'
  if (message.includes('not a valid image') || message.includes('empty file')) return 'unreadable'
  if (message.includes('larger than') || error.status === 413) return 'tooLarge'
  if (message.includes('unknown setup')) return 'unknownSetup'
  return undefined
}
