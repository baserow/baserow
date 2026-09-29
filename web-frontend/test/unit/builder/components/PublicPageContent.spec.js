import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, test, vi } from 'vitest'

import PublicPageContent from '@baserow/modules/builder/components/PublicPageContent'
import { ElementType } from '@baserow/modules/builder/elementTypes'

const useHead = vi.hoisted(() => vi.fn())

vi.mock('#app', async (importOriginal) => ({
  ...(await importOriginal()),
  useHead,
}))

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

  test('adds element responsive styles through useHead', async () => {
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
          RecursiveWrapper: { template: '<div><slot /></div>' },
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
  })
})
