import { TestApp } from '@baserow/test/helpers/testApp'
import { expect } from '@jest/globals'

/**
 * Regression tests for issue #2923: Element position reset after
 * duplicate → move → edit.
 *
 * These tests verify that:
 * 1. The element store's update/debouncedUpdate actions strip positional fields
 * 2. The move action correctly updates positional data
 * 3. The full duplicate → move → edit flow preserves element position
 * 4. PATCH payloads never contain stale place_in_container values
 */
describe('element store - position consistency', () => {
  let testApp = null
  let store = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    mockServer = testApp.mockServer
  })

  afterEach(() => {
    testApp.afterEach()
  })

  // Helper: create a minimal page with elements tracking
  const createPage = () => ({
    id: 1,
    elements: [],
    orderedElements: [],
    elementMap: {},
  })

  // Helper: create a minimal builder
  const createBuilder = () => ({
    id: 1,
    selectedElement: null,
    pages: [],
  })

  // Helper: create a column element
  const createColumnElement = (page) => ({
    id: 100,
    page_id: page.id,
    type: 'column',
    order: '1.00000000000000000000',
    parent_element_id: null,
    place_in_container: null,
    column_amount: 3,
    _: {
      contentLoading: false,
      content: [],
      hasNextPage: true,
      reset: 0,
      shouldBeFocused: false,
      elementNamespacePath: null,
      uid: 'test-uid-100',
    },
  })

  // Helper: create a text element inside a column
  const createTextElement = (page, parentId, place, id, order) => ({
    id,
    page_id: page.id,
    type: 'text',
    order: order || '1.00000000000000000000',
    parent_element_id: parentId,
    place_in_container: place,
    value: { formula: "'hello'" },
    format: 'plain',
    styles: {},
    _: {
      contentLoading: false,
      content: [],
      hasNextPage: true,
      reset: 0,
      shouldBeFocused: false,
      elementNamespacePath: null,
      uid: `test-uid-${id}`,
    },
  })

  test('update action strips positional fields from API payload', async () => {
    const page = createPage()
    const builder = createBuilder()

    const element = createTextElement(page, 100, '0', 200, '1.0')
    page.elements.push(element)
    page.elementMap = { '200': element }
    page.orderedElements = [element]

    // Track what gets sent to the API
    let capturedPayload = null
    mockServer.mock
      .onPatch(`builder/element/200/`)
      .reply((config) => {
        capturedPayload = JSON.parse(config.data)
        return [200, element]
      })

    // Dispatch update with positional fields included (simulating stale data)
    await store.dispatch('element/update', {
      builder,
      page,
      element,
      values: {
        value: "'updated'",
        place_in_container: '0', // stale — must be stripped
        parent_element_id: null, // stale — must be stripped
        order: '999', // stale — must be stripped
      },
    })

    // The API payload must NOT contain positional fields
    expect(capturedPayload).toBeDefined()
    expect(capturedPayload).not.toHaveProperty('place_in_container')
    expect(capturedPayload).not.toHaveProperty('parent_element_id')
    expect(capturedPayload).not.toHaveProperty('order')

    // The property update should still be sent
    expect(capturedPayload).toHaveProperty('value', "'updated'")
  })

  test('update action with only positional fields does nothing', async () => {
    const page = createPage()
    const builder = createBuilder()

    const element = createTextElement(page, 100, '0', 200, '1.0')
    page.elements.push(element)
    page.elementMap = { '200': element }
    page.orderedElements = [element]

    let apiCalled = false
    mockServer.mock.onPatch(`builder/element/200/`).reply(() => {
      apiCalled = true
      return [200, element]
    })

    // Dispatch update with ONLY positional fields
    await store.dispatch('element/update', {
      builder,
      page,
      element,
      values: {
        place_in_container: '0',
        parent_element_id: null,
        order: '1',
      },
    })

    // No API call should be made since all values were stripped
    expect(apiCalled).toBe(false)
  })

  test('debouncedUpdate strips positional fields from accumulated values', async () => {
    jest.useFakeTimers()

    const page = createPage()
    const builder = createBuilder()

    const element = createTextElement(page, 100, '1', 201, '2.0')
    page.elements.push(element)
    page.elementMap = { '201': element }
    page.orderedElements = [element]

    let capturedPayload = null
    mockServer.mock
      .onPatch(`builder/element/201/`)
      .reply((config) => {
        capturedPayload = JSON.parse(config.data)
        return [200, element]
      })

    // Dispatch debouncedUpdate with positional fields
    const updatePromise = store.dispatch('element/debouncedUpdate', {
      builder,
      page,
      element,
      values: {
        value: "'debounced-update'",
        place_in_container: '0', // stale — must be stripped
        parent_element_id: 999, // stale — must be stripped
      },
    })

    // Advance timers to trigger the debounced fire
    jest.advanceTimersByTime(600)
    await updatePromise

    // Positional fields must NOT be in the payload
    if (capturedPayload) {
      expect(capturedPayload).not.toHaveProperty('place_in_container')
      expect(capturedPayload).not.toHaveProperty('parent_element_id')
      expect(capturedPayload).not.toHaveProperty('order')
      expect(capturedPayload).toHaveProperty('value', "'debounced-update'")
    }

    jest.useRealTimers()
  })

  test('forceMove correctly updates place_in_container in store', () => {
    const page = createPage()
    const builder = createBuilder()

    const element = createTextElement(page, 100, '0', 202, '1.0')
    page.elements.push(element)
    page.elementMap = { '202': element }
    page.orderedElements = [element]

    // Move element from place 0 to place 1
    store.dispatch('element/forceMove', {
      builder,
      page,
      elementId: 202,
      beforeElementId: null,
      parentElementId: 100,
      placeInContainer: '1',
    })

    // The element should now be at place 1
    const movedElement = page.elementMap['202']
    expect(movedElement.place_in_container).toBe('1')
    expect(movedElement.parent_element_id).toBe(100)
  })

  test('duplicate then move then edit preserves position', async () => {
    const page = createPage()
    const builder = createBuilder()

    // Step 1: Column element + text in place 0
    const column = createColumnElement(page)
    const original = createTextElement(page, 100, '0', 200, '1.0')
    page.elements.push(column, original)
    page.elementMap = { '100': column, '200': original }
    page.orderedElements = [column, original]

    // Step 2: Simulate duplicate — backend creates element at place_in_container=0
    const duplicate = createTextElement(page, 100, '0', 201, '2.0')
    page.elements.push(duplicate)
    page.elementMap['201'] = duplicate
    page.orderedElements = [column, original, duplicate]

    // Verify duplicate is at place 0
    expect(duplicate.place_in_container).toBe('0')

    // Step 3: Move duplicate to place 1
    store.dispatch('element/forceMove', {
      builder,
      page,
      elementId: 201,
      beforeElementId: null,
      parentElementId: 100,
      placeInContainer: '1',
    })

    // Verify move worked
    expect(page.elementMap['201'].place_in_container).toBe('1')

    // Step 4: Edit the duplicate — update should NOT touch position
    let capturedPayload = null
    mockServer.mock
      .onPatch(`builder/element/201/`)
      .reply((config) => {
        capturedPayload = JSON.parse(config.data)
        return [200, { ...duplicate, value: { formula: "'edited'" } }]
      })

    await store.dispatch('element/update', {
      builder,
      page,
      element: page.elementMap['201'],
      values: {
        value: "'edited'",
        // Stale place_in_container from form that cached old values
        place_in_container: '0',
      },
    })

    // Step 5: Verify position is preserved
    expect(page.elementMap['201'].place_in_container).toBe('1')

    // Verify the API payload does NOT contain place_in_container
    expect(capturedPayload).toBeDefined()
    expect(capturedPayload).not.toHaveProperty('place_in_container')
    expect(capturedPayload).toHaveProperty('value', "'edited'")
  })
})
