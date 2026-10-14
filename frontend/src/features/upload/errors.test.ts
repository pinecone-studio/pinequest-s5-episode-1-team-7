import { describe, expect, it } from 'vitest'

import { ApiError } from '../../shared/api/client.ts'
import { ingestErrorKey } from './errors.ts'

describe('ingestErrorKey', () => {
  it.each([
    [new ApiError('Failed to fetch', 0), 'offline'],
    [new ApiError('image is too blurry (sharpness 12.0 < 100); retake the capture in focus', 422), 'blurry'],
    [new ApiError('not a valid image', 422), 'unreadable'],
    [new ApiError('file larger than 40 MB', 422), 'tooLarge'],
    [new ApiError('unknown setup_id: 7', 422), 'unknownSetup'],
  ])('%s -> %s', (error, key) => {
    expect(ingestErrorKey(error)).toBe(key)
  })

  it('leaves unknown errors to the backend message', () => {
    expect(ingestErrorKey(new ApiError('indication must be Routine or Urgent', 422))).toBeUndefined()
    expect(ingestErrorKey(new Error('boom'))).toBeUndefined()
  })
})
