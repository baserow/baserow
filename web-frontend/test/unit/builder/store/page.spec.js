import { describe, expect, test } from 'vitest'

import pageStore from '@baserow/modules/builder/store/page'

describe('builder page store', () => {
  test('a page already in the builder is not added twice', () => {
    const page = { id: 1, name: 'Home' }
    const builder = { pages: [page] }

    pageStore.mutations.ADD_ITEM({}, { builder, page: { ...page } })

    expect(builder.pages).toEqual([page])
  })
})
