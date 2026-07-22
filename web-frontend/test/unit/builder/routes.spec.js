import { describe, expect, test } from 'vitest'

import { routes } from '@baserow/modules/builder/routes'

describe('builder routes', () => {
  test('the preview route has the fixed builder-scoped shape', () => {
    const previewRoute = routes.find(
      ({ name }) => name === 'application-builder-preview'
    )

    expect(previewRoute.path).toBe(
      '/builder-preview/:builderId/:pathMatch(.*)*'
    )
  })
})
