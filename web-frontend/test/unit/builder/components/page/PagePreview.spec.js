import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import PagePreview from '@baserow/modules/builder/components/page/PagePreview'
import {
  PAGE_PLACES,
  PAGE_ELEMENT_ALIGNMENTS,
  PAGE_ELEMENT_BEHAVIOURS,
} from '@baserow/modules/builder/enums'

describe('PagePreview', () => {
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

  const createPage = (overrides = {}) => ({
    id: 1,
    path: '/',
    shared: false,
    order: 1,
    elements: [],
    elementMap: {},
    orderedElements: [],
    workflowActions: [],
    ...overrides,
  })

  const createElement = (overrides = {}) => ({
    id: 42,
    type: 'simple_container',
    page_id: 1,
    parent_element_id: null,
    behaviour: PAGE_ELEMENT_BEHAVIOURS.NORMAL,
    alignment: PAGE_ELEMENT_ALIGNMENTS.TOP,
    ...overrides,
  })

  const mountComponent = async ({
    elements = [],
    sharedElements = [],
  } = {}) => {
    const currentPage = createPage({ elements })
    const sharedPage = createPage({
      id: 2,
      shared: true,
      elements: sharedElements,
    })
    const builder = {
      id: 1,
      pages: [currentPage, sharedPage],
      theme: {},
    }
    const workspace = { id: 1 }

    const wrapper = mount(PagePreview, {
      attachTo: document.body,
      global: {
        provide: {
          builder,
          currentPage,
          workspace,
        },
        mocks: {
          $hasPermission: () => true,
          $registry: {
            getAll: () => ({}),
            getOrderedList: (registryName) => {
              if (registryName === 'themeConfigBlock') {
                return [
                  {
                    getCSS: () => ({ '--main-primary-color': '#000000' }),
                    getColorVariables: () => [],
                  },
                ]
              }
              return []
            },
            get: (registryName, type) => {
              if (registryName === 'device') {
                return { type: 'desktop', maxWidth: null }
              }
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
            getters: {
              'element/getChildren': () => [],
              'element/getClosestSiblingElement': () => null,
              'element/getElementById': () => null,
              'element/getRootElements': (page) => page.elements,
              'element/getSelected': () => null,
              'page/getById': () => currentPage,
              'page/getDeviceTypeSelected': 'desktop',
              'page/getSharedPage': () => sharedPage,
            },
          },
          $t: (key) => key,
        },
        stubs: {
          AddElementModal: {
            props: ['page'],
            template: '<div />',
          },
          AddElementZone: {
            props: ['label', 'page'],
            template: '<div />',
          },
          ElementPreview: {
            props: ['element', 'isFirstElement'],
            template:
              '<div class="element-preview-stub" :data-element-id="String(element.id)" :data-is-first="String(isFirstElement)" />',
          },
          PreviewNavigationBar: {
            props: ['page'],
            template: '<div />',
          },
          ThemeProvider: {
            template: '<div><slot /></div>',
          },
        },
      },
    })
    wrappers.push(wrapper)

    return {
      wrapper,
    }
  }

  test('renders the fixed elements overlay before the scrollable preview', async () => {
    const { wrapper } = await mountComponent()
    const preview = wrapper.find('.page-preview').element
    const fixedElements = wrapper.find('.page-preview__fixed-elements').element
    const previewScaled = wrapper.find('.page-preview__scaled').element
    const previewChildren = Array.from(preview.children)

    expect(previewChildren.indexOf(fixedElements)).toBeLessThan(
      previewChildren.indexOf(previewScaled)
    )
  })

  test('renders fixed root elements in the fixed overlay', async () => {
    const fixedElement = createElement({
      id: 42,
      behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
      alignment: PAGE_ELEMENT_ALIGNMENTS.BOTTOM,
      parent_element_id: 7,
    })
    const normalElement = createElement({
      id: 43,
    })
    const { wrapper } = await mountComponent({
      elements: [fixedElement, normalElement],
    })
    const fixedElements = wrapper.find('.page-preview__fixed-elements')
    const scrollablePreview = wrapper.find('.page-preview__scaled')

    expect(fixedElements.find('[data-element-id="42"]').exists()).toBeTruthy()
    expect(fixedElements.find('[data-element-id="43"]').exists()).toBeFalsy()
    expect(
      scrollablePreview.find('[data-element-id="42"]').exists()
    ).toBeFalsy()
    expect(
      scrollablePreview.find('[data-element-id="43"]').exists()
    ).toBeTruthy()
  })

  test('renders fixed header and footer elements in their page sections', async () => {
    const fixedHeader = createElement({
      id: 44,
      type: 'header',
      page_id: 2,
      behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
    })
    const scrollableHeader = createElement({
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
    const { wrapper } = await mountComponent({
      sharedElements: [fixedHeader, scrollableHeader, fixedFooter],
    })
    const fixedElements = wrapper.find('.page-preview__fixed-elements')
    const headers = wrapper.findAll('.page__header')
    const footer = wrapper.find('.page__footer')

    expect(fixedElements.find('[data-element-id="44"]').exists()).toBeFalsy()
    expect(fixedElements.find('[data-element-id="46"]').exists()).toBeFalsy()
    expect(headers).toHaveLength(2)
    expect(headers[0].classes()).toContain('page__header--position-fixed')
    expect(headers[1].classes()).not.toContain('page__header--position-fixed')
    expect(footer.classes()).toContain('page__footer--position-fixed')
    expect(headers[0].find('[data-element-id="44"]').exists()).toBeTruthy()
    expect(headers[0].find('[data-element-id="45"]').exists()).toBeFalsy()
    expect(headers[1].find('[data-element-id="44"]').exists()).toBeFalsy()
    expect(headers[1].find('[data-element-id="45"]').exists()).toBeTruthy()
    expect(footer.find('[data-element-id="46"]').exists()).toBeTruthy()
  })

  test('scales the fixed elements overlay with the page preview', () => {
    const fixedElements = {
      style: {},
    }

    PagePreview.methods.updateFixedElementsScale.call(
      {
        $refs: {
          fixedElements,
        },
      },
      {
        scale: 0.5,
        width: 800,
        height: 600,
      }
    )

    expect(fixedElements.style).toEqual({
      transform: 'scale(0.5)',
      transformOrigin: '0 0',
      width: '800px',
      height: '600px',
    })
  })
})
