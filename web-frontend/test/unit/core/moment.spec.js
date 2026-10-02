import { afterEach, describe, expect, test } from 'vitest'
import moment, { loadMomentLocale } from '@baserow/modules/core/moment'

describe('lazy Moment locale modules', () => {
  afterEach(() => {
    moment.locale('en')
  })

  test.each([
    ['en', 'January'],
    ['fr', 'janvier'],
    ['nl', 'januari'],
    ['de', 'Januar'],
    ['es', 'enero'],
    ['it', 'gennaio'],
    ['pl', 'styczeń'],
    ['ko', '1월'],
    ['uk', 'січень'],
  ])(
    'registers %s on the timezone-enabled Moment instance',
    async (locale, month) => {
      await loadMomentLocale(locale)
      moment.locale(locale)

      expect(moment('2026-01-01').format('MMMM')).toBe(month)
      expect(moment.tz('2026-01-01 12:00', 'Europe/Rome').utc().hour()).toBe(11)
    }
  )
})
