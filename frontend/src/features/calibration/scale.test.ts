import { describe, expect, it } from 'vitest'

import { imagePointToMap, mapToImagePoint, scaledUmPerPx, umPerPx } from './scale.ts'

describe('umPerPx', () => {
  it('divides the known distance by the pixel distance', () => {
    expect(umPerPx({ x: 0, y: 0 }, { x: 200, y: 0 }, 100)).toBeCloseTo(0.5)
    expect(umPerPx({ x: 0, y: 0 }, { x: 60, y: 80 }, 100)).toBeCloseTo(1)
  })

  it('returns null for coincident marks or a non-positive distance', () => {
    expect(umPerPx({ x: 5, y: 5 }, { x: 5, y: 5 }, 100)).toBeNull()
    expect(umPerPx({ x: 0, y: 0 }, { x: 10, y: 0 }, 0)).toBeNull()
    expect(umPerPx({ x: 0, y: 0 }, { x: 10, y: 0 }, -50)).toBeNull()
  })
})

describe('scaledUmPerPx', () => {
  it('scales the calibrated value by objective power', () => {
    expect(scaledUmPerPx(0.5, '40x', '40x')).toBeCloseTo(0.5)
    expect(scaledUmPerPx(0.5, '40x', '10x')).toBeCloseTo(2)
    expect(scaledUmPerPx(0.5, '40x', '20x')).toBeCloseTo(1)
  })

  it('returns null for bad labels', () => {
    expect(scaledUmPerPx(0.5, '40x', 'wide')).toBeNull()
    expect(scaledUmPerPx(0.5, 'wide', '10x')).toBeNull()
    expect(scaledUmPerPx(-1, '40x', '10x')).toBeNull()
  })
})

describe('mapToImagePoint / imagePointToMap', () => {
  const size = { width: 1536, height: 1152 }

  it('flips the map y axis into top-left image pixels', () => {
    expect(mapToImagePoint(1152, 0, size)).toEqual({ x: 0, y: 0 })
    expect(mapToImagePoint(0, 1536, size)).toEqual({ x: 1536, y: 1152 })
    expect(mapToImagePoint(1000.5, 250.25, size)).toEqual({ x: 250.25, y: 151.5 })
  })

  it('ignores clicks outside the photo', () => {
    expect(mapToImagePoint(1200, 10, size)).toBeNull()
    expect(mapToImagePoint(10, -1, size)).toBeNull()
    expect(mapToImagePoint(-0.5, 10, size)).toBeNull()
    expect(mapToImagePoint(10, 1537, size)).toBeNull()
  })

  it('round-trips', () => {
    const [lat, lng] = imagePointToMap({ x: 123.4, y: 567.8 }, size)
    expect(mapToImagePoint(lat, lng, size)).toEqual({ x: 123.4, y: expect.closeTo(567.8) })
  })
})
