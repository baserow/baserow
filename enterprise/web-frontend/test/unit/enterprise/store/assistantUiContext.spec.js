import { describe, expect, test } from 'vitest'

import { getters } from '@baserow_enterprise/store/assistant'

const builder = {
  id: 3,
  type: 'builder',
  name: 'Portal',
  pages: [{ id: 7, name: 'Tasks' }],
}
const page = { id: 7 }

// The table element reads from data source 11, and the heading is inside it.
const table = { id: 20, type: 'table', page_id: 7, data_source_id: 11 }
const heading = { id: 21, type: 'heading', page_id: 7, data_source_id: null }
const text = { id: 22, type: 'text', page_id: 7, data_source_id: null }
const parents = { [heading.id]: table }

function uiContext(selectedElement) {
  const rootGetters = {
    'undoRedo/getCurrentScope': { workspace: 1, application: 3, page: 7 },
    'workspace/get': () => ({ id: 1, name: 'Workspace' }),
    'application/get': () => builder,
    'element/getSelected': () => selectedElement,
    'page/getById': () => page,
    'element/getAncestors': (elementPage, element, options) => {
      expect(elementPage).toBe(page)
      expect(options).toEqual({ includeSelf: true, parentFirst: true })
      return parents[element.id] ? [element, parents[element.id]] : [element]
    },
  }
  return getters.uiContext({}, {}, {}, rootGetters)
}

describe('assistant uiContext', () => {
  test('includes the selected element and its data source', () => {
    expect(uiContext(table).element).toEqual({
      id: 20,
      type: 'table',
      data_source_id: 11,
    })
  })

  test("uses the data source of the element's collection", () => {
    expect(uiContext(heading).element).toEqual({
      id: 21,
      type: 'heading',
      data_source_id: 11,
    })
  })

  test('has no data source for an element outside a collection', () => {
    expect(uiContext(text).element).toEqual({
      id: 22,
      type: 'text',
      data_source_id: null,
    })
  })

  test('leaves the element out when none is selected', () => {
    const context = uiContext(null)

    expect(context.element).toBeUndefined()
    expect(context.page).toEqual({ id: 7, name: 'Tasks' })
  })
})
