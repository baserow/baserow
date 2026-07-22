import { mountSuspended } from '@nuxt/test-utils/runtime'
import { ref } from 'vue'
import { beforeEach, describe, expect, test, vi } from 'vitest'

const { store, useAsyncData } = vi.hoisted(() => ({
  store: {
    dispatch: vi.fn(),
  },
  useAsyncData: vi.fn(),
}))

vi.mock('vuex', async (importOriginal) => ({
  ...(await importOriginal()),
  useStore: () => store,
}))

vi.mock('@baserow/modules/builder/components/PublicPageContent.vue', () => ({
  default: { template: '<div />' },
}))

vi.mock('#app', async (importOriginal) => ({
  ...(await importOriginal()),
  createError: vi.fn(),
  navigateTo: vi.fn(),
  useAsyncData,
  useNuxtApp: () => ({
    $i18n: { t: (key) => key },
    $registry: {},
    $config: {
      public: { builderPreviewPathPrefix: '/builder-preview' },
    },
  }),
}))

vi.mock('#imports', () => ({
  useHead: vi.fn(),
  useRequestURL: () => new URL('https://preview.example.com/builder-preview'),
  useRoute: () => ({
    fullPath: '/builder-preview/missing',
    meta: { builderPageMode: 'preview' },
    params: { pathMatch: 'missing' },
    query: {},
  }),
}))

const PublicPage = await import('@baserow/modules/builder/pages/publicPage.vue')

describe('PublicPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAsyncData.mockReturnValue({
      data: ref(null),
      error: ref(null),
      pending: ref(true),
    })
  })

  test('enables preview async data during SSR', async () => {
    await mountSuspended(PublicPage.default)

    expect(useAsyncData).toHaveBeenCalledOnce()
    expect(useAsyncData.mock.calls[0]).toHaveLength(2)
  })

  test('throws an initial missing-page error during SSR', async () => {
    const pageNotFoundError = new Error('Page not found')
    useAsyncData.mockReturnValue({
      data: ref(null),
      error: ref(pageNotFoundError),
      pending: ref(false),
    })

    await expect(mountSuspended(PublicPage.default)).rejects.toThrow(
      pageNotFoundError
    )
  })
})
