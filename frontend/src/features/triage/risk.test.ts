import { describe, expect, it } from 'vitest'

import { priorityLevel, scorePoints } from './risk.ts'

describe('priorityLevel', () => {
  it('names stored overrides, including hand-set values', () => {
    expect(priorityLevel(1)).toBe('highest')
    expect(priorityLevel(0.5)).toBe('medium')
    expect(priorityLevel(0.3)).toBe('low')
    expect(priorityLevel(0.8)).toBe('high')
  })
})

describe('scorePoints', () => {
  it('turns the 0–1 slide score into 0–100', () => {
    expect(scorePoints(0.834)).toBe(83)
    expect(scorePoints(0)).toBe(0)
    expect(scorePoints(null)).toBeNull()
  })
})
