import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

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
})

// The test app is served on the editor's hostname, like a default install.
describe('PublicPageContent Preview security notice', () => {
  let wrapper = null
  let publicConfig
  let original

  beforeEach(() => {
    publicConfig = useRuntimeConfig().public
    original = {
      builderPreviewUrl: publicConfig.builderPreviewUrl,
      publicWebFrontendUrl: publicConfig.publicWebFrontendUrl,
      builderDangerousRelaxPreviewSecurity:
        publicConfig.builderDangerousRelaxPreviewSecurity,
    }
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    Object.assign(publicConfig, original)
    useHead.mockClear()
  })

  const embed = { id: 10, type: 'iframe', source_type: 'embed' }
  const urlIFrame = { id: 11, type: 'iframe', source_type: 'url' }

  const mountPage = async ({
    mode = 'preview',
    builderPreviewUrl = 'https://editor.example.com:3001',
    relaxed = false,
    untrustedContent = false,
    elements = [],
    sharedElements = [],
  }) => {
    Object.assign(publicConfig, {
      builderPreviewUrl,
      publicWebFrontendUrl: 'https://editor.example.com',
      builderDangerousRelaxPreviewSecurity: relaxed,
    })
    const page = {
      id: 1,
      name: 'Page',
      path: '/',
      shared: false,
      graph: {},
      elements: [],
      elementMap: {},
      orderedElements: elements,
      query_params: [],
      visibility: 'all',
    }
    const sharedPage = {
      ...page,
      id: 2,
      shared: true,
      orderedElements: sharedElements,
    }
    const builder = {
      id: 1,
      breakpoints: { mobile: 640, tablet: 1024 },
      theme: {},
      pages: [page, sharedPage],
      user_sources: [],
      login_page_id: null,
      scripts: [],
      untrusted_content: untrustedContent,
      custom_code: { css: '', js: '' },
    }

    wrapper = await mountSuspended(PublicPageContent, {
      props: {
        workspace: { id: 1 },
        builder,
        page,
        params: {},
        path: '/',
        mode,
      },
      global: {
        stubs: { BuilderToasts: true, PageContent: true },
      },
    })
    await flushPromises()
    return wrapper.find('.preview-security-notice').exists()
  }

  test('is shown in Preview on the editor hostname when the page has author code', async () => {
    expect(await mountPage({ elements: [embed] })).toBe(true)
  })

  test('is shown when the shared page has author code', async () => {
    expect(await mountPage({ sharedElements: [embed] })).toBe(true)
  })

  test.each([false, true])(
    'shows the untrusted content notice even when domain restrictions are relaxed: %s',
    async (relaxed) => {
      expect(await mountPage({ untrustedContent: true, relaxed })).toBe(true)
      expect(wrapper.text()).toContain('previewSecurityNotice.untrustedSummary')
      expect(wrapper.text()).not.toContain('previewSecurityNotice.summary')
    }
  )

  test.each([
    ['the page has no author code', { elements: [urlIFrame] }],
    [
      'the instance relaxes Preview security',
      { elements: [embed], relaxed: true },
    ],
    ['the application is published', { elements: [embed], mode: 'public' }],
  ])('is hidden when %s', async (_, options) => {
    expect(await mountPage(options)).toBe(false)
  })
})
