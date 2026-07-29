import ElementGraphHandler from '@baserow/modules/builder/utils/elementGraphHandler'

// Build a fake page object the handler understands: a graph plus an elementMap
// keyed by stringified id (mirrors how the store builds page.elementMap).
const makePage = (graph, elementIds) => ({
  graph,
  elementMap: Object.fromEntries(elementIds.map((id) => [`${id}`, { id }])),
})

describe('ElementGraphHandler.getOrderedElements', () => {
  test('returns graph-reachable elements in depth-first order', () => {
    const page = makePage(
      {
        0: 1,
        1: { next: { '': [2] } },
        2: {},
      },
      [1, 2]
    )

    const ordered = new ElementGraphHandler(page).getOrderedElements()

    expect(ordered.map((el) => el.id)).toEqual([1, 2])
  })

  test('appends elements absent from the graph at the bottom', () => {
    // Element 3 exists on the page but is not present in the graph (e.g. created
    // during a not-yet-zero-downtime deployment). It must still be returned, after
    // the graph-ordered elements.
    const page = makePage(
      {
        0: 1,
        1: { next: { '': [2] } },
        2: {},
      },
      [1, 2, 3]
    )

    const ordered = new ElementGraphHandler(page).getOrderedElements()

    expect(ordered.map((el) => el.id)).toEqual([1, 2, 3])
  })

  test('returns every element when the graph is empty', () => {
    const page = makePage({}, [5, 6])

    const ordered = new ElementGraphHandler(page).getOrderedElements()

    expect(ordered.map((el) => el.id).sort()).toEqual([5, 6])
  })

  test('skips filtered elements without hiding following root elements', () => {
    const page = makePage(
      {
        0: 1,
        1: { children: { '': [2] }, next: { '': [4] } },
        2: {},
        4: {},
      },
      [4]
    )

    const ordered = new ElementGraphHandler(page).getOrderedElements()

    expect(ordered.map((el) => el.id)).toEqual([4])
  })
})

describe('ElementGraphHandler.getChildren', () => {
  test('skips filtered children without hiding following siblings', () => {
    const page = makePage(
      {
        0: 1,
        1: { children: { 0: [2] } },
        2: { next: { '': [3] } },
        3: {},
      },
      [1, 3]
    )

    const children = new ElementGraphHandler(page).getChildren({ id: 1 })

    expect(children.map((el) => el.id)).toEqual([3])
  })

  test('skips descendants of filtered children', () => {
    const page = makePage(
      {
        0: 1,
        1: { children: { 0: [2] } },
        2: { children: { '': [3] }, next: { '': [4] } },
        3: {},
        4: {},
      },
      [1, 3, 4]
    )

    const children = new ElementGraphHandler(page).getChildren({ id: 1 })

    expect(children.map((el) => el.id)).toEqual([4])
  })
})
