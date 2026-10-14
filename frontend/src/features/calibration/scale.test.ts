import { describe, expect, it } from 'vitest'

import { scaledUmPerPx, umPerPx } from './scale.ts'

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
