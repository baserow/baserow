import { describe, expect, test, vi } from 'vitest'

vi.mock('#imports', () => ({
  defineNuxtPlugin: vi.fn((plugin) => plugin),
  useRequestURL: vi.fn(),
  useRouter: vi.fn(),
  useRuntimeConfig: vi.fn(),
}))

const { shouldRemoveRoute } = await import(
  '@baserow/modules/builder/plugins/router'
)

const publishedHostname = {
  isWebFrontendHostname: false,
  isBuilderPreviewHostname: false,
  isBuilderPreviewRequest: false,
}

describe('builder router route filtering', () => {
  test('keeps a route shared by published and preview builders on published hostnames', () => {
    const route = {
      meta: { publishedBuilderRoute: true, previewBuilderRoute: true },
    }

    expect(shouldRemoveRoute(route, publishedHostname)).toBe(false)
  })

  test('removes preview-only routes from published hostnames', () => {
    const route = { meta: { previewBuilderRoute: true } }

    expect(shouldRemoveRoute(route, publishedHostname)).toBe(true)
  })

  test('removes regular frontend routes from published hostnames', () => {
    const route = { meta: {} }

    expect(shouldRemoveRoute(route, publishedHostname)).toBe(true)
  })
})
