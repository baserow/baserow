import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import PageContent from '@baserow/modules/builder/components/page/PageContent'
import {
  PAGE_ELEMENT_BEHAVIOURS,
  PAGE_PLACES,
} from '@baserow/modules/builder/enums'

describe('PageContent', () => {
  let originalResizeObserver = null
  let wrappers = []

  beforeEach(() => {
    wrappers = []
    originalResizeObserver = globalThis.ResizeObserver
    globalThis.ResizeObserver = class {
      disconnect = vi.fn()
      observe = vi.fn()
    }
  })

  afterEach(() => {
    wrappers.forEach((wrapper) => wrapper.unmount())
    if (originalResizeObserver) {
      globalThis.ResizeObserver = originalResizeObserver
    } else {
      delete globalThis.ResizeObserver
    }
  })

  const createElement = (overrides = {}) => ({
    id: 42,
    type: 'simple_container',
    page_id: 1,
    parent_element_id: null,
    behaviour: PAGE_ELEMENT_BEHAVIOURS.NORMAL,
    ...overrides,
  })

  const mountComponent = ({ elements = [], sharedElements = [] } = {}) => {
    const currentPage = { id: 1, path: '/' }
    const builder = { id: 1, pages: [currentPage] }

    const wrapper = mount(PageContent, {
      props: {
        elements,
        params: {},
        path: '/',
        sharedElements,
      },
      global: {
        provide: {
          builder,
          currentPage,
          mode: 'public',
        },
        mocks: {
          $registry: {
            getAll: (registryName) => {
              if (registryName === 'device') {
                return {
                  desktop: {
                    getOrder: () => 1,
                    getType: () => 'desktop',
                    maxWidth: null,
                  },
                }
              }
              return {}
            },
            get: (registryName, type) => {
              if (registryName === 'element') {
                return {
                  getPagePlace: () => {
                    if (type === 'header') {
                      return PAGE_PLACES.HEADER
                    }
                    if (type === 'footer') {
                      return PAGE_PLACES.FOOTER
                    }
                    return PAGE_PLACES.CONTENT
                  },
                }
              }
              return null
            },
          },
          $store: {
            dispatch: vi.fn(),
          },
        },
        stubs: {
          PageElement: {
            props: ['element'],
            template:
              '<div class="page-element-stub" :data-element-id="String(element.id)" />',
          },
        },
      },
    })
    wrappers.push(wrapper)
    return wrapper
  }

  test('renders fixed header and footer containers in sticky page sections', () => {
    const fixedHeader = createElement({
      id: 44,
      type: 'header',
      page_id: 2,
      behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
    })
    const normalHeader = createElement({
      id: 45,
      type: 'header',
      page_id: 2,
    })
    const fixedFooter = createElement({
      id: 46,
      type: 'footer',
      page_id: 2,
      behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
    })

    const wrapper = mountComponent({
      sharedElements: [fixedHeader, normalHeader, fixedFooter],
    })
    const header = wrapper.find('.page__header')
    const footer = wrapper.find('.page__footer')

    expect(header.classes()).toContain('page__header--position-fixed')
    expect(footer.classes()).toContain('page__footer--position-fixed')
    expect(header.find('[data-element-id="44"]').exists()).toBeTruthy()
    expect(header.find('[data-element-id="45"]').exists()).toBeTruthy()
    expect(footer.find('[data-element-id="46"]').exists()).toBeTruthy()
  })
})
