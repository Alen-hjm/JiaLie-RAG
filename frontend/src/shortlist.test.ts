// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest'
import { readShortlist, toggleShortlist } from './shortlist'

describe('local shortlist', () => {
  beforeEach(() => localStorage.clear())
  it('persists IDs, deduplicates selections, and supports removing a saved candidate', () => {
    toggleShortlist('candidate-a'); toggleShortlist('candidate-b')
    expect(readShortlist()).toEqual(['candidate-a','candidate-b'])
    toggleShortlist('candidate-a')
    expect(readShortlist()).toEqual(['candidate-b'])
    expect(localStorage.getItem('jialie.shortlist.v1')).toBe('["candidate-b"]')
  })
  it('recovers from invalid or outdated browser data', () => {
    localStorage.setItem('jialie.shortlist.v1', '{broken')
    expect(readShortlist()).toEqual([])
    localStorage.setItem('jialie.shortlist.v1', '["a","a",null,123]')
    expect(readShortlist()).toEqual(['a'])
  })
})
