import { flushPromises } from '@vue/test-utils'
import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { reactive } from 'vue'

import PublicPageContent from '@baserow/modules/builder/components/PublicPageContent'
import { ElementType } from '@baserow/modules/builder/elementTypes'

const { useHead, reloadNuxtApp } = vi.hoisted(() => ({
  useHead: vi.fn(),
  reloadNuxtApp: vi.fn(),
}))

vi.mock('#app', async (importOriginal) => ({
  ...(await importOriginal()),
  useHead,
  reloadNuxtApp,
}))

// Lets a test move the router's current route without a matching app route.
const routerOverride = vi.hoisted(() => ({ currentRoute: null }))
mockNuxtImport('useRouter', (original) => () => {
  const router = original()
  return routerOverride.currentRoute
    ? { ...router, currentRoute: routerOverride.currentRoute }
    : router
})

class ResponsiveStyleElementType extends ElementType {
  static getType() {
    return 'responsive-style-test'
  }

  getPublicResponsiveStyles(builder) {
    return `@media (max-width: ${builder.breakpoints.mobile}px) { .responsive-style-test { display: none; } }`
  }
}

describe('PublicPageContent', () => {
  let wrapper = null
  let registry = null

  afterEach(() => {
    wrapper?.unmount()
    registry?.unregister('element', ResponsiveStyleElementType.getType())
    useHead.mockClear()
    wrapper = null
    registry = null
  })

  test('adds element responsive styles and provides the root data scope', async () => {
    const page = {
      id: 1,
      name: 'Public page',
      path: '/',
      shared: false,
      graph: {},
      elements: [],
      elementMap: {},
      orderedElements: [],
      query_params: [],
      visibility: 'all',
    }
    const sharedPage = {
      ...page,
      id: 2,
      shared: true,
    }
    const builder = {
      id: 1,
      breakpoints: { mobile: 640, tablet: 1024 },
      theme: {},
      pages: [page, sharedPage],
      user_sources: [],
      login_page_id: null,
      scripts: [],
      custom_code: { css: '', js: '' },
    }

    registry = useNuxtApp().$registry
    registry.register('element', new ResponsiveStyleElementType())

    wrapper = await mountSuspended(PublicPageContent, {
      props: {
        workspace: { id: 1 },
        builder,
        page,
        params: {},
        path: '/',
        mode: 'public',
      },
      global: {
        stubs: {
          BuilderToasts: true,
          PageContent: true,
          RecursiveWrapper: {
            inject: ['applicationContext'],
            template:
              '<div data-test-id="root-scope">{{ applicationContext.dataScope.includeTargetElement }}<slot /></div>',
          },
        },
      },
    })
    await flushPromises()

    expect(useHead).toHaveBeenCalledTimes(1)
    const [headConfig] = useHead.mock.calls[0]
    const responsiveStyle = headConfig.value.style.find(({ innerHTML }) =>
      innerHTML.includes('.responsive-style-test')
    )

    expect(responsiveStyle.innerHTML).toContain('@media (max-width: 640px)')
    expect(wrapper.find('[data-test-id="root-scope"]').text()).toBe('false')
  })

  test('reloads when the site was published again before a logout', async () => {
    const page = {
      id: 1,
      name: 'Public page',
      path: '/',
      shared: false,
      graph: {},
      elements: [],
      elementMap: {},
      orderedElements: [],
      query_params: [],
      visibility: 'all',
    }
    const builder = reactive({
      id: 1,
      breakpoints: { mobile: 640, tablet: 1024 },
      theme: {},
      pages: [page, { ...page, id: 2, shared: true }],
      user_sources: [],
      login_page_id: null,
      scripts: [],
      custom_code: { css: '', js: '' },
      userSourceUser: { authenticated: true },
    })

    const store = useNuxtApp().$store
    const originalDispatch = store.dispatch.bind(store)
    const dispatch = vi
      .spyOn(store, 'dispatch')
      .mockImplementation((type, payload) => {
        if (type === 'dataSourceContent/debouncedFetchPageDataSourceContent') {
          // Logging out changes the dispatch context, which would schedule a
          // content fetch that outlives this test.
          return Promise.resolve()
        }
        if (type.endsWith('/fetchPublished')) {
          return Promise.reject({
            response: {
              status: 404,
              data: { error: 'ERROR_PAGE_DOES_NOT_EXIST' },
            },
          })
        }
        return originalDispatch(type, payload)
      })
    routerOverride.currentRoute = { value: { fullPath: '/' } }

    try {
      wrapper = await mountSuspended(PublicPageContent, {
        props: {
          workspace: { id: 1 },
          builder,
          page,
          params: {},
          path: '/',
          mode: 'public',
        },
        global: {
          stubs: {
            BuilderToasts: true,
            PageContent: true,
            RecursiveWrapper: { template: '<div><slot /></div>' },
          },
        },
      })
      await flushPromises()
      expect(reloadNuxtApp).not.toHaveBeenCalled()

      // The logout has already moved the visitor to another page, whose URL
      // has a hash that the reload must drop.
      routerOverride.currentRoute.value = {
        fullPath: '/login?next=%2Fjobs#form',
      }
      builder.userSourceUser.authenticated = false
      await flushPromises()

      expect(reloadNuxtApp).toHaveBeenCalledWith({
        path: '/login?next=%2Fjobs',
        force: true,
      })
    } finally {
      dispatch.mockRestore()
      reloadNuxtApp.mockClear()
      routerOverride.currentRoute = null
    }
  })
})
