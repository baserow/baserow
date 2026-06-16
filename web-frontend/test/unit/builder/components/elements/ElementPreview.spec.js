import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import ElementPreview from '@baserow/modules/builder/components/elements/ElementPreview'
import { VISIBILITY_ALL } from '@baserow/modules/builder/constants'
import {
  PAGE_ELEMENT_ALIGNMENTS,
  PAGE_ELEMENT_BEHAVIOURS,
} from '@baserow/modules/builder/enums'

describe('ElementPreview', () => {
  let originalIntersectionObserver = null

  beforeEach(() => {
    originalIntersectionObserver = globalThis.IntersectionObserver
    globalThis.IntersectionObserver = class {
      disconnect = vi.fn()
      observe = vi.fn()
    }
  })

  afterEach(() => {
    if (originalIntersectionObserver) {
      globalThis.IntersectionObserver = originalIntersectionObserver
    } else {
      delete globalThis.IntersectionObserver
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

  const createSimpleContainerElement = (page, overrides = {}) => ({
    id: 42,
    type: 'simple_container',
    page_id: page.id,
    order: '1.00000000000000000000',
    parent_element_id: null,
    place_in_container: null,
    css_classes: '',
    visibility: VISIBILITY_ALL,
    visibility_condition: { formula: '' },
    roles: [],
    style_background_file: null,
    behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
    alignment: PAGE_ELEMENT_ALIGNMENTS.BOTTOM,
    _: {
      uid: 'simple-container-42',
    },
    ...overrides,
  })

  const mountComponent = async ({ element, page, sharedPage }) => {
    const workspace = { id: 1 }
    const builder = {
      id: 1,
      pages: [page, sharedPage],
      selectedElement: element,
      theme: {},
    }

    return mountSuspended(ElementPreview, {
      props: {
        element,
      },
      global: {
        provide: {
          applicationContext: {
            builder,
            mode: 'editing',
            page,
            workspace,
          },
          builder,
          currentPage: page,
          dndContext: {
            draggedElement: null,
            dropTargetId: null,
          },
          mode: 'editing',
          pageTopData: { value: 0 },
          workspace,
        },
        stubs: {
          AddElementModal: {
            props: ['page'],
            template: '<div />',
          },
          AddElementZone: {
            props: ['disabled', 'label', 'page', 'parentElement'],
            template: '<div />',
          },
          ElementMenu: {
            props: [
              'allowedDirections',
              'directions',
              'hasParent',
              'isDuplicating',
            ],
            template: '<div />',
          },
          InsertElementButton: {
            template: '<button />',
          },
        },
      },
    })
  }

  test('positions the editor preview wrapper for fixed root containers', async () => {
    const page = createPage()
    const sharedPage = createPage({ id: 2, shared: true })
    const element = createSimpleContainerElement(page)

    page.elements = [element]
    page.orderedElements = [element]
    page.elementMap = { [element.id]: element }

    const wrapper = await mountComponent({ element, page, sharedPage })

    const elementPreview = wrapper.find('.element-preview').element
    expect(elementPreview).not.toBeNull()

    expect(Array.from(elementPreview.classList)).toEqual(
      expect.arrayContaining([
        'element--positioned',
        'element--position-fixed',
        'element--position-alignment-bottom',
        'element-preview--active',
      ])
    )

    const pageElementWrapper = elementPreview.querySelector('.element__wrapper')
    expect(pageElementWrapper).not.toBe(null)
    expect(pageElementWrapper.classList).not.toContain('element--positioned')
    expect(pageElementWrapper.classList).not.toContain(
      'element--position-fixed'
    )
    expect(pageElementWrapper.classList).not.toContain(
      'element--position-alignment-bottom'
    )
  })
})
