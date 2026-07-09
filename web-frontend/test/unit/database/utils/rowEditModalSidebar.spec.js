import {
  ROW_EDIT_MODAL_SIDEBAR_TAB_KEY,
  getRowEditModalSidebarTab,
  setRowEditModalSidebarTab,
} from '@baserow/modules/database/utils/rowEditModalSidebar'
import { installLocalStorageMock } from '@baserow/test/helpers/localStorage'

describe('rowEditModalSidebar utils', () => {
  beforeAll(() => {
    installLocalStorageMock()
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
