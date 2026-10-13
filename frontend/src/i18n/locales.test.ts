import { describe, expect, it } from 'vitest'

import { LANGUAGES, resources } from './resources.ts'

type Tree = { [key: string]: Tree | string | string[] }

/** Every leaf as [path, value]. Arrays (tissue "look for" lists) are leaves. */
function leaves(tree: Tree, prefix = ''): [string, string | string[]][] {
  return Object.entries(tree).flatMap(([k, v]) =>
    typeof v === 'string' || Array.isArray(v) ? [[`${prefix}${k}`, v] as [string, string | string[]]] : leaves(v, `${prefix}${k}.`),
  )
}

const variables = (text: string) => [...text.matchAll(/{{\s*(\w+)/g)].map((m) => m[1]).sort()
const tags = (text: string) => [...text.matchAll(/<\/?(\w+)>/g)].map((m) => m[0]).sort()

describe.each(Object.keys(resources.en))('%s namespace', (ns) => {
  const en = new Map(leaves(resources.en[ns as keyof typeof resources.en] as Tree))

  it.each(LANGUAGES.filter((l) => l !== 'en'))('%s has exactly the English keys', (lng) => {
    const other = new Map(leaves(resources[lng][ns as keyof typeof resources.en] as Tree))
    expect([...other.keys()].sort()).toEqual([...en.keys()].sort())
  })

  it.each(LANGUAGES)('%s has no empty text and keeps every {{variable}} and <tag>', (lng) => {
    const other = new Map(leaves(resources[lng][ns as keyof typeof resources.en] as Tree))
    for (const [key, enValue] of en) {
      const value = other.get(key)
      if (Array.isArray(enValue)) {
        expect(value, key).toBeInstanceOf(Array)
        expect((value as string[]).length, key).toBe(enValue.length)
        for (const item of value as string[]) expect(item.trim(), key).not.toBe('')
        continue
      }
      expect(typeof value, key).toBe('string')
      expect((value as string).trim(), key).not.toBe('')
      expect(variables(value as string), key).toEqual(variables(enValue))
      expect(tags(value as string), key).toEqual(tags(enValue))
    }
  })
})

describe('plural keys', () => {
  it('every _one key has an _other twin in every language', () => {
    for (const lng of LANGUAGES) {
      for (const tree of Object.values(resources[lng])) {
        const keys = new Set(leaves(tree as Tree).map(([k]) => k))
        for (const key of keys) {
          if (key.endsWith('_one')) expect(keys.has(key.replace(/_one$/, '_other')), `${lng} ${key}`).toBe(true)
        }
      }
    }
  })
})
