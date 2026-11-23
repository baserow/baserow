import { flushPromises } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import sidebarTabOrder from '@baserow/modules/core/directives/sidebarTabOrder'

test('keeps only the workspace switcher in the sidebar tab order', async () => {
  const sidebar = document.createElement('div')
  const switcher = document.createElement('button')
  switcher.setAttribute('data-sidebar-tab-stop', '')
  const shortcut = document.createElement('button')
  const navigate = vi.fn()
  shortcut.addEventListener('click', navigate)
  sidebar.append(switcher, shortcut)

  sidebarTabOrder.mounted(sidebar)
  try {
    expect(switcher.tabIndex).toBe(0)
    expect(shortcut.tabIndex).toBe(-1)
    shortcut.click()
    expect(navigate).toHaveBeenCalledOnce()

    const subitem = document.createElement('a')
    const app = document.createElement('li')
    app.append(subitem)
    sidebar.append(app)
    await flushPromises()
    subitem.href = '#table'
    await flushPromises()
    expect(subitem.tabIndex).toBe(-1)

    shortcut.tabIndex = 0
    await flushPromises()
    expect(shortcut.tabIndex).toBe(-1)
  } finally {
    sidebarTabOrder.beforeUnmount(sidebar)
  }
})
