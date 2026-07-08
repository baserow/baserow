import { beforeAll } from 'vitest'
import {
  ROW_EDIT_MODAL_SIDEBAR_TAB_KEY,
  getRowEditModalSidebarTab,
  setRowEditModalSidebarTab,
} from '@baserow/modules/database/utils/rowEditModalSidebar'

describe('rowEditModalSidebar utils', () => {
  beforeAll(() => {
    // Provide localStorage if not available in test environment
    if (!global.localStorage) {
      const store = {}
      global.localStorage = {
        getItem: (key) => store[key] ?? null,
        setItem: (key, value) => {
          store[key] = value
        },
        removeItem: (key) => {
          delete store[key]
        },
        clear: () => {
          Object.keys(store).forEach((key) => delete store[key])
        },
        key: (index) => Object.keys(store)[index] ?? null,
        length: Object.keys(store).length,
      }
    }
  })

  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  test('returns null when nothing is stored', () => {
    expect(getRowEditModalSidebarTab()).toBe(null)
  })

  test('round-trips a stored tab type', () => {
    setRowEditModalSidebarTab('history')
    expect(localStorage.getItem(ROW_EDIT_MODAL_SIDEBAR_TAB_KEY)).toBe('history')
    expect(getRowEditModalSidebarTab()).toBe('history')
  })

  test('get returns null when localStorage throws', () => {
    vi.spyOn(localStorage, 'getItem').mockImplementation(() => {
      throw new Error('unavailable')
    })
    expect(getRowEditModalSidebarTab()).toBe(null)
  })

  test('set does not throw when localStorage throws', () => {
    vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('unavailable')
    })
    expect(() => setRowEditModalSidebarTab('comments')).not.toThrow()
  })
})
