// Persists the last-opened row edit modal sidebar tab, globally per browser.
// Access localStorage only through here so the backing store can be swapped
// later (e.g. to a cookie if the row modal ever becomes server-rendered).
export const ROW_EDIT_MODAL_SIDEBAR_TAB_KEY = 'baserow.rowEditModalSidebarTab'

// Returns the stored tab type string, or null when unset/unavailable.
export function getRowEditModalSidebarTab() {
  try {
    return localStorage.getItem(ROW_EDIT_MODAL_SIDEBAR_TAB_KEY) || null
  } catch (e) {
    return null
  }
}

// Stores the tab type string. No-op when localStorage is unavailable.
export function setRowEditModalSidebarTab(type) {
  try {
    localStorage.setItem(ROW_EDIT_MODAL_SIDEBAR_TAB_KEY, type)
  } catch (e) {}
}
