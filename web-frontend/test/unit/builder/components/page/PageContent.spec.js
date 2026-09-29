import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import PageContent from '@baserow/modules/builder/components/page/PageContent'
import {
  DesktopDeviceType,
  SmartphoneDeviceType,
  TabletDeviceType,
} from '@baserow/modules/builder/deviceTypes'
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

  const createDeviceTypes = () => ({
    desktop: new DesktopDeviceType(),
    tablet: new TabletDeviceType(),
    smartphone: new SmartphoneDeviceType(),
  })

  const mountComponent = ({
    elements = [],
    sharedElements = [],
    breakpoints = { mobile: 640, tablet: 1024 },
  } = {}) => {
    const currentPage = { id: 1, path: '/' }
    const builder = { id: 1, pages: [currentPage], breakpoints }
    const deviceTypes = createDeviceTypes()

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
                return deviceTypes
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
                  getPageSection: (element) => {
                    if (type === 'header') {
                      return element?.behaviour ===
                        PAGE_ELEMENT_BEHAVIOURS.FIXED
                        ? 'fixed-header'
                        : PAGE_PLACES.HEADER
                    }
                    if (type === 'footer') {
                      return element?.behaviour ===
                        PAGE_ELEMENT_BEHAVIOURS.FIXED
                        ? 'fixed-footer'
                        : PAGE_PLACES.FOOTER
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

  const getRenderedIds = (wrapper) => {
    return wrapper
      .findAll('.page-element-stub')
      .map((element) => element.attributes('data-element-id'))
  }

  test('stacks fixed multi-page elements without moving content elements', () => {
    const fixedTopContent = createElement({
      id: 42,
      behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
    })
    const normalContent = createElement({
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
    const fixedBottomContent = createElement({
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

    const wrapper = mountComponent({
      elements: [fixedTopContent, normalContent, fixedBottomContent],
      sharedElements: [fixedHeader, normalHeader, fixedFooter, normalFooter],
    })
    const topStack = wrapper.find('.page__fixed-stack--top')
    const bottomStack = wrapper.find('.page__fixed-stack--bottom')
    const header = wrapper.find('.page__header')
    const content = wrapper.find('.page__content')
    const footer = wrapper.find('.page__footer')

    expect(getRenderedIds(topStack)).toEqual(['44'])
    expect(getRenderedIds(header)).toEqual(['45'])
    expect(getRenderedIds(content)).toEqual(['42', '43', '46'])
    expect(getRenderedIds(footer)).toEqual(['48'])
    expect(getRenderedIds(bottomStack)).toEqual(['47'])
  })

  test('selects devices using the configured breakpoint boundaries', () => {
    const wrapper = mountComponent({
      breakpoints: { mobile: 640, tablet: 1024 },
    })

    expect(
      [640, 641, 1024, 1025].map((width) =>
        wrapper.vm.closestDeviceType(width).getType()
      )
    ).toEqual(['smartphone', 'tablet', 'tablet', 'desktop'])
  })
})
