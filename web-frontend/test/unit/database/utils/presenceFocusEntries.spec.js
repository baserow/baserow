import { describe, expect, test } from 'vitest'

import { activeFocusEntry } from '@baserow/modules/database/utils/presenceFocusEntries'

describe('activeFocusEntry', () => {
  test('returns null for empty entries', () => {
    expect(activeFocusEntry([])).toBeNull()
  })

  test('returns the first entry when nobody is editing', () => {
    const first = { user_id: 10, editing: false }
    const second = { user_id: 20, editing: false }

    expect(activeFocusEntry([first, second])).toBe(first)
  })

  test('returns the first editing entry', () => {
    const first = { user_id: 10, editing: false }
    const second = { user_id: 20, editing: true }
    const third = { user_id: 30, editing: true }

    expect(activeFocusEntry([first, second, third])).toBe(second)
  })
})
