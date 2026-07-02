import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import PagePreview from '@baserow/modules/builder/components/page/PagePreview'
import {
  PAGE_PLACES,
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

  const getRenderedIds = (wrapper) => {
    return wrapper
      .findAll('.element-preview-stub')
      .map((element) => element.attributes('data-element-id'))
  }

  const getDirectChildClassNames = (wrapper) => {
    return Array.from(wrapper.element.children).map((child) => child.className)
  }

  test('renders fixed multi-page elements in sticky page stacks', async () => {
    const fixedTopElement = createElement({
      id: 42,
      behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
      parent_element_id: 7,
    })
    const normalElement = createElement({
      id: 43,
    })
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
    const fixedBottomElement = createElement({
      id: 46,
      behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
    })
    const fixedFooter = createElement({
      id: 47,
      type: 'footer',
      page_id: 2,
      behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
    })
    const normalFooter = createElement({
      id: 48,
      type: 'footer',
      page_id: 2,
    })
    const { wrapper } = await mountComponent({
      elements: [fixedTopElement, normalElement, fixedBottomElement],
      sharedElements: [fixedHeader, normalHeader, fixedFooter, normalFooter],
    })
    const topStack = wrapper.find('.page__fixed-stack--top')
    const bottomStack = wrapper.find('.page__fixed-stack--bottom')
    const header = wrapper.find('.page__header')
    const content = wrapper.find('.page__content')
    const footer = wrapper.find('.page__footer')

    expect(wrapper.find('.page-preview__fixed-elements').exists()).toBeFalsy()
    expect(topStack.classes()).toContain('page__fixed-stack--header')
    expect(getRenderedIds(topStack)).toEqual(['44'])
    expect(getDirectChildClassNames(topStack)).toEqual([
      'element-preview-stub',
      'page-preview__separator',
    ])
    expect(getRenderedIds(header)).toEqual(['45'])
    expect(getRenderedIds(content)).toEqual(['42', '43', '46'])
    expect(getRenderedIds(footer)).toEqual(['48'])
    expect(bottomStack.classes()).toContain('page__fixed-stack--footer')
    expect(getRenderedIds(bottomStack)).toEqual(['47'])
    expect(getDirectChildClassNames(bottomStack)).toEqual([
      'page-preview__separator',
      'element-preview-stub',
    ])
    expect(wrapper.findAll('.page-preview__separator')).toHaveLength(4)
  })

  test('renders normal header and footer elements in their page sections', async () => {
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
    const topStack = wrapper.find('.page__fixed-stack--top')
    const headers = wrapper.findAll('.page__header')
    const bottomStack = wrapper.find('.page__fixed-stack--bottom')

    expect(getRenderedIds(topStack)).toEqual(['44'])
    expect(headers).toHaveLength(1)
    expect(getRenderedIds(headers[0])).toEqual(['45'])
    expect(getRenderedIds(bottomStack)).toEqual(['46'])
  })

  test('renders the empty page add zone in the content section', async () => {
    const { wrapper } = await mountComponent()
    const content = wrapper.find('.page__content')

    expect(content.exists()).toBe(true)
    expect(content.classes()).toContain('add-element-zone--full-height')
  })

  test('renders header and footer separators when only fixed elements exist', async () => {
    const fixedHeader = createElement({
      id: 44,
      type: 'header',
      page_id: 2,
      behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
    })
    const fixedFooter = createElement({
      id: 46,
      type: 'footer',
      page_id: 2,
      behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
    })
    const { wrapper } = await mountComponent({
      sharedElements: [fixedHeader, fixedFooter],
    })
    const topStack = wrapper.find('.page__fixed-stack--top')
    const bottomStack = wrapper.find('.page__fixed-stack--bottom')

    expect(wrapper.find('.page__header').exists()).toBe(false)
    expect(wrapper.find('.page__footer').exists()).toBe(false)
    expect(wrapper.findAll('.page-preview__separator')).toHaveLength(2)
    expect(getDirectChildClassNames(topStack)).toEqual([
      'element-preview-stub',
      'page-preview__separator',
    ])
    expect(getDirectChildClassNames(bottomStack)).toEqual([
      'page-preview__separator',
      'element-preview-stub',
    ])
    expect(topStack.find('.page-preview__separator-label').text()).toBe(
      'pagePreview.fixedHeader'
    )
    expect(bottomStack.find('.page-preview__separator-label').text()).toBe(
      'pagePreview.fixedFooter'
    )
  })
})
