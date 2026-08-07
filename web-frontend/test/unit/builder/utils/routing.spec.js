import { createMemoryHistory, createRouter } from 'vue-router'

import { resolveApplicationRoute } from '@baserow/modules/builder/utils/routing'

const createBuilderRouter = () =>
  createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        name: 'application-builder-page',
        path: '/:pathMatch(.*)*',
        component: {},
      },
      {
        name: 'application-builder-preview',
        path: '/builder/:builderId/preview/:pathMatch(.*)*',
        component: {},
      },
    ],
  })

describe('resolveApplicationRoute', () => {
  test.each([
    ['the published homepage', '/'],
    ['the preview homepage', '/builder/263/preview/'],
  ])('resolves %s when Vue Router omits the catch-all parameter', (_, url) => {
    const homepage = { id: 439, path: '/' }
    const route = createBuilderRouter().resolve(url)

    expect(route.params.pathMatch).toBeUndefined()

    const found = resolveApplicationRoute([homepage], route.params.pathMatch)

    expect(found?.[0]).toBe(homepage)
    expect(found?.[1]).toBe('')
  })
})
