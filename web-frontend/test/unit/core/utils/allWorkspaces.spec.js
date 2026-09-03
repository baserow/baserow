import {
  isTypeFilterActive,
  SORT_BY_CREATED,
  SORT_BY_LAST_VIEWED,
  SORT_BY_NAME_ASC,
  SORT_BY_NAME_DESC,
  getApplicationComparator,
  getSearchResultComparator,
  latestViewedOf,
  sortWorkspaces,
} from '@baserow/modules/core/utils/allWorkspaces'

const app = (id, order, lastViewed = null, name = `App ${id}`) => ({
  id,
  order,
  name,
  last_viewed: lastViewed,
})

describe('allWorkspaces utils', () => {
  describe('isTypeFilterActive', () => {
    test('is inactive when none or all types are selected', () => {
      expect(isTypeFilterActive([], 4)).toBe(false)
      expect(isTypeFilterActive(['a', 'b', 'c', 'd'], 4)).toBe(false)
    })

    test('is active for a partial selection', () => {
      expect(isTypeFilterActive(['a'], 4)).toBe(true)
      expect(isTypeFilterActive(['a', 'b', 'c'], 4)).toBe(true)
    })
  })

  describe('getApplicationComparator', () => {
    test('created keeps the manual order', () => {
      const applications = [
        app(1, 3, '2026-01-03T00:00:00Z'),
        app(2, 1),
        app(3, 2),
      ]
      applications.sort(getApplicationComparator(SORT_BY_CREATED))
      expect(applications.map(({ id }) => id)).toEqual([2, 3, 1])
    })

    test('last viewed puts the most recently viewed first', () => {
      const applications = [
        app(1, 1, '2026-01-01T00:00:00Z'),
        app(2, 2, '2026-01-03T00:00:00Z'),
        app(3, 3, '2026-01-02T00:00:00Z'),
      ]
      applications.sort(getApplicationComparator(SORT_BY_LAST_VIEWED))
      expect(applications.map(({ id }) => id)).toEqual([2, 3, 1])
    })

    test('never viewed applications go last in manual order', () => {
      const applications = [
        app(1, 2),
        app(2, 3, '2026-01-01T00:00:00Z'),
        app(3, 1),
        app(4, 4, '2026-01-02T00:00:00Z'),
      ]
      applications.sort(getApplicationComparator(SORT_BY_LAST_VIEWED))
      expect(applications.map(({ id }) => id)).toEqual([4, 2, 3, 1])
    })

    test('name sorts are case insensitive', () => {
      const applications = [
        app(1, 1, null, 'banana'),
        app(2, 2, null, 'Apple'),
        app(3, 3, null, 'cherry'),
      ]
      applications.sort(getApplicationComparator(SORT_BY_NAME_ASC))
      expect(applications.map(({ id }) => id)).toEqual([2, 1, 3])
      applications.sort(getApplicationComparator(SORT_BY_NAME_DESC))
      expect(applications.map(({ id }) => id)).toEqual([3, 1, 2])
    })
  })

  test('search results keep never viewed applications grouped', () => {
    const matches = [
      app(1, 2, null),
      app(2, 3, '2026-01-01T00:00:00Z'),
      app(3, 1, null),
    ]
    matches.sort(getSearchResultComparator(SORT_BY_LAST_VIEWED))
    expect(matches.map(({ id }) => id)).toEqual([2, 1, 3])
    matches.sort(getSearchResultComparator(SORT_BY_NAME_DESC))
    expect(matches.map(({ id }) => id)).toEqual([3, 2, 1])
  })

  test('latestViewedOf', () => {
    expect(latestViewedOf([])).toBeNull()
    expect(latestViewedOf([app(1, 1), app(2, 2)])).toBeNull()
    expect(
      latestViewedOf([
        app(1, 1, '2026-01-01T00:00:00Z'),
        app(2, 2, '2026-01-05T00:00:00Z'),
        app(3, 3),
        app(4, 4, '2026-01-03T00:00:00Z'),
      ])
    ).toBe('2026-01-05T00:00:00Z')
  })

  test('sortWorkspaces', () => {
    const workspaces = [
      { id: 1, order: 1, name: 'Delta' },
      { id: 2, order: 2, name: 'alpha' },
      { id: 3, order: 3, name: 'Charlie' },
      { id: 4, order: 4, name: 'bravo' },
    ]
    const applicationsByWorkspace = {
      1: [app(1, 1, '2026-01-01T00:00:00Z')],
      2: [],
      3: [app(2, 1), app(3, 2, '2026-01-04T00:00:00Z')],
      4: [app(4, 1)],
    }
    const applicationsOf = (workspace) => applicationsByWorkspace[workspace.id]
    const ids = (sortBy) =>
      sortWorkspaces(workspaces, sortBy, applicationsOf).map(({ id }) => id)

    expect(ids(SORT_BY_CREATED)).toEqual([1, 2, 3, 4])
    expect(ids(SORT_BY_LAST_VIEWED)).toEqual([3, 1, 2, 4])
    expect(ids(SORT_BY_NAME_ASC)).toEqual([2, 4, 3, 1])
    expect(ids(SORT_BY_NAME_DESC)).toEqual([1, 3, 4, 2])
    // The input must not be mutated because it comes from a store getter.
    expect(workspaces.map(({ id }) => id)).toEqual([1, 2, 3, 4])
  })
})
