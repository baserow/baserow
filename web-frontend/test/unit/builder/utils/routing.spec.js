import { createMemoryHistory, createRouter } from 'vue-router'

import {
  resolveApplicationRoute,
  resolveBuilderPagePath,
  resolveSafeNextPath,
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
        path: '/builder/preview/:builderId/:pathMatch(.*)*',
        component: {},
      },
    ],
  })

describe('resolveApplicationRoute', () => {
  test.each([
    ['the published homepage', '/'],
    ['the preview homepage', '/builder/preview/263/'],
  ])('resolves %s with an empty catch-all parameter', (_, url) => {
    const homepage = { id: 439, path: '/' }
    const route = createBuilderRouter().resolve(url)

    expect(route.params.pathMatch).toBeFalsy()

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

describe('resolveSafeNextPath', () => {
  test.each([
    ['/products', '/products'],
    ['%2Fbuilder%2Fpreview%2F2%2Fproducts', '/builder/preview/2/products'],
    ['https%3A%2F%2Fevil.example', null],
    ['%2F%2Fevil.example', null],
    ['%2F%5Cevil.example', null],
    ['%', null],
    [undefined, null],
  ])('resolves %s to %s', (next, expected) => {
    expect(resolveSafeNextPath(next)).toBe(expected)
  })
})
