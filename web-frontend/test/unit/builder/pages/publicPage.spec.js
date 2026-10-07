import { mountSuspended } from '@nuxt/test-utils/runtime'
import { ref } from 'vue'
import { beforeEach, describe, expect, test, vi } from 'vitest'

const {
  getTokenIfEnoughTimeLeft,
  navigateTo,
  reloadNuxtApp,
  route,
  store,
  useAsyncData,
} = vi.hoisted(() => ({
  getTokenIfEnoughTimeLeft: vi.fn(),
  navigateTo: vi.fn(),
  reloadNuxtApp: vi.fn(),
  route: {
    fullPath: '/builder/preview/missing',
    meta: { builderPageMode: 'preview' },
    params: { builderId: '42', pathMatch: 'missing' },
    query: {},
  },
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
  reloadNuxtApp,
  useAsyncData,
  useNuxtApp: () => ({
    $i18n: { t: (key) => key },
    $registry: { getAll: vi.fn(() => []) },
    $config: { public: {} },
  }),
}))

vi.mock('#imports', () => ({
  useHead: vi.fn(),
  useRequestURL: () =>
    new URL('https://preview.example.com/builder/preview/42/missing'),
  useRoute: () => route,
  useRuntimeConfig: () => ({ public: { builderPreviewUrl: '' } }),
}))

const PublicPage = await import('@baserow/modules/builder/pages/publicPage.vue')

describe('PublicPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.dispatch.mockReset()
    getTokenIfEnoughTimeLeft.mockReset()
    route.fullPath = '/builder/preview/missing'
    route.params.pathMatch = 'missing'
    route.query = {}
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

  test('does not render public content without an async data result', async () => {
    useAsyncData.mockReturnValue({
      data: ref(null),
      error: ref(null),
      pending: ref(false),
    })

    const wrapper = await mountSuspended(PublicPage.default)

    expect(wrapper.html()).toMatchInlineSnapshot(`"<!--v-if-->"`)
  })

  test('stops loading a stale non-home page after logout', async () => {
    const builder = { id: 42, user_sources: [] }
    store.getters['application/getSelected'] = null
    store.getters['userSourceUser/isAuthenticated'] = () => false
    store.dispatch.mockImplementation((type) => {
      if (type === 'publicBuilder/fetch') {
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

    await mountSuspended(PublicPage.default, {
      props: { builderId: builder.id, mode: 'preview', pathMatch: 'missing' },
    })
    const loadPublicPage = useAsyncData.mock.calls[0][1]
    await loadPublicPage()

    expect(reloadNuxtApp).not.toHaveBeenCalled()
    expect(navigateTo).toHaveBeenCalledWith('/builder/preview/42/')
    expect(store.dispatch).not.toHaveBeenCalledWith(
      'dataSource/fetchPublished',
      expect.anything()
    )
  })

  test('restarts the home page after a data source logs out', async () => {
    route.fullPath = '/builder/preview/42/'
    route.params.pathMatch = undefined
    const page = { id: 2 }
    const builder = {
      id: 42,
      user_sources: [],
      workspace: { id: 3, licenses: [] },
    }
    store.getters['application/getSelected'] = builder
    store.getters['userSourceUser/isAuthenticated'] = () => true
    store.getters['page/getVisiblePages'] = () => [
      { id: page.id, path: '/', query_params: [] },
    ]
    store.getters['page/getById'] = () => page
    store.getters['auth/isAuthenticated'] = false
    store.dispatch.mockImplementation((type) => {
      if (type === 'dataSource/fetchPublished') {
        return Promise.reject({ response: { status: 401 } })
      }
    })

    await mountSuspended(PublicPage.default, {
      props: { builderId: builder.id, mode: 'preview', pathMatch: '' },
    })
    const loadPublicPage = useAsyncData.mock.calls[0][1]
    const result = await loadPublicPage()

    expect(reloadNuxtApp).toHaveBeenCalledWith({
      path: '/builder/preview/42/',
      force: true,
    })
    expect(navigateTo).not.toHaveBeenCalled()
    expect(store.dispatch).toHaveBeenCalledWith('userSourceUser/logoff', {
      application: builder,
    })
    expect(store.dispatch).not.toHaveBeenCalledWith(
      'page/selectById',
      expect.anything()
    )
    expect(result).toBeUndefined()
  })
})
