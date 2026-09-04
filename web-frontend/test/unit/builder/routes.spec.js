import { describe, expect, test } from 'vitest'

import { routes } from '@baserow/modules/builder/routes'

describe('builder routes', () => {
  test('the preview route has the fixed builder-scoped shape', () => {
    const previewRoute = routes.find(
      ({ name }) => name === 'application-builder-preview'
    )

    expect(previewRoute.path).toBe(
      '/builder/preview/:builderId/:pathMatch(.*)*'
    )
  })

  test('the published-by-id route does not use the secured preview prefix', () => {
    const publishedRoute = routes.find(
      ({ name }) => name === 'application-builder-published'
    )

    expect(publishedRoute.path).toBe(
      '/builder/published/:builderId/:pathMatch(.*)*'
    )
  })
})
