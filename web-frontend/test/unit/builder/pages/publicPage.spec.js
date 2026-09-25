import { mountSuspended } from '@nuxt/test-utils/runtime'
import { ref } from 'vue'
import { beforeEach, describe, expect, test, vi } from 'vitest'

const { getTokenIfEnoughTimeLeft, navigateTo, store, useAsyncData } =
  vi.hoisted(() => ({
    getTokenIfEnoughTimeLeft: vi.fn(),
    navigateTo: vi.fn(),
    store: {
      dispatch: vi.fn(),
      getters: {},
    },
    useAsyncData: vi.fn(),
  }))

vi.mock('@baserow/modules/core/utils/auth', async (importOriginal) => ({
  ...(await importOriginal()),
  getTokenIfEnoughTimeLeft,
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
  navigateTo,
  useAsyncData,
  useNuxtApp: () => ({
    $i18n: { t: (key) => key },
    $registry: {},
    $config: { public: {} },
  }),
}))

vi.mock('#imports', () => ({
  useHead: vi.fn(),
  useRequestURL: () =>
    new URL('https://preview.example.com/builder/preview/42/missing'),
  useRoute: () => ({
    fullPath: '/builder/preview/missing',
    meta: { builderPageMode: 'preview' },
    params: { builderId: '42', pathMatch: 'missing' },
    query: {},
  }),
}))

const PublicPage = await import('@baserow/modules/builder/pages/publicPage.vue')

describe('PublicPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.getters = {}
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

  test('stops loading the stale page after an authentication refresh fails', async () => {
    const builder = { id: 42, user_sources: [] }
    store.getters['application/getSelected'] = null
    store.getters['userSourceUser/isAuthenticated'] = () => false
    store.dispatch.mockImplementation((type) => {
      if (type === 'publicBuilder/fetchPreview') {
        return { id: builder.id }
      }
      if (type === 'application/selectById') {
        return builder
      }
      if (type === 'userSourceUser/refreshAuth') {
        return Promise.reject({ response: { status: 401 } })
      }
    })
    getTokenIfEnoughTimeLeft.mockResolvedValue('expired-refresh-token')
    navigateTo.mockResolvedValue()

    await mountSuspended(PublicPage.default, {
      props: { builderId: builder.id, mode: 'preview', pathMatch: 'missing' },
    })
    const loadPublicPage = useAsyncData.mock.calls[0][1]
    await loadPublicPage()

    expect(navigateTo).toHaveBeenCalledOnce()
    expect(store.dispatch).not.toHaveBeenCalledWith(
      'dataSource/fetchPublished',
      expect.anything()
    )
  })
})
