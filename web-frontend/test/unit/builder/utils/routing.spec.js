import { createMemoryHistory, createRouter } from 'vue-router'

import {
  resolveApplicationRoute,
  resolveBuilderPagePath,
} from '@baserow/modules/builder/utils/routing'

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
        path: '/builder-preview/:builderId/:pathMatch(.*)*',
        component: {},
      },
    ],
  })

describe('resolveApplicationRoute', () => {
  test.each([
    ['the published homepage', '/'],
    ['the preview homepage', '/builder-preview/263/'],
  ])('resolves %s when Vue Router omits the catch-all parameter', (_, url) => {
    const homepage = { id: 439, path: '/' }
    const route = createBuilderRouter().resolve(url)

    expect(route.params.pathMatch).toBeUndefined()

    const found = resolveApplicationRoute([homepage], route.params.pathMatch)

    expect(found?.[0]).toBe(homepage)
    expect(found?.[1]).toBe('')
  })
})

describe('resolveBuilderPagePath', () => {
  test.each([
    [undefined, ''],
    [null, ''],
    ['', ''],
    ['products/42', 'products/42'],
    [['products', '42'], 'products/42'],
  ])('normalizes %s', (path, expected) => {
    expect(resolveBuilderPagePath(path)).toBe(expected)
  })
})
