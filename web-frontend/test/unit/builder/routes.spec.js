import { describe, expect, test } from 'vitest'

import { routes } from '@baserow/modules/builder/routes'

describe('builder routes', () => {
  test('the preview route accepts prefixes supplied after the image was built', () => {
    const previewRoute = routes.find(
      ({ name }) => name === 'application-builder-preview'
    )

    expect(previewRoute.path).toBe('/:pathMatch(.*)*')
  })
})
