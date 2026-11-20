import { describe, expect, test, vi } from 'vitest'

import {
  getCategoryName,
  sortCategories,
} from '@baserow/modules/core/utils/templateCategory'

const makeI18n = async () => {
  const { createI18n } = await vi.importActual('vue-i18n')
  return createI18n({
    legacy: true,
    locale: 'nl',
    messages: {
      nl: {
        templateCategoryNames: {
          'Sales and CRM': 'Verkoop en CRM',
          '🔥 Most Popular': '🔥 Populairst',
          Legal: 'Wettelijk',
        },
      },
    },
  }).global
}

describe('templateCategory', () => {
  test('shows the translated name, emoji included', async () => {
    const i18n = await makeI18n()
    expect(getCategoryName({ name: 'Sales and CRM' }, i18n)).toBe(
      'Verkoop en CRM'
    )
    expect(getCategoryName({ name: '🔥 Most Popular' }, i18n)).toBe(
      '🔥 Populairst'
    )
  })

  test('shows the stored name without a translation', async () => {
    const i18n = await makeI18n()
    expect(getCategoryName({ name: 'Teachers' }, i18n)).toBe('Teachers')
  })

  test('sorts by the shown name, ignoring a leading emoji', async () => {
    const i18n = await makeI18n()
    const names = sortCategories(
      [
        { name: 'Legal' },
        { name: 'Sales and CRM' },
        { name: '🔥 Most Popular' },
        { name: 'Marketing' },
      ],
      i18n
    ).map((category) => category.name)
    expect(names).toEqual([
      'Marketing',
      '🔥 Most Popular',
      'Sales and CRM',
      'Legal',
    ])
  })
})
