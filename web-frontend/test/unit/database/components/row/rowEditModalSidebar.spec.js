import { TestApp } from '@baserow/test/helpers/testApp'
import RowEditModalSidebar from '@baserow/modules/database/components/row/RowEditModalSidebar'
import { RowModalSidebarType } from '@baserow/modules/database/rowModalSidebarTypes'
import {
  getRowEditModalSidebarTab,
  setRowEditModalSidebarTab,
} from '@baserow/modules/database/utils/rowEditModalSidebar'

// Minimal fake sidebar types so the test does not depend on premium comments.
// Explicit order mirrors the real types (comments 0, history 10); the database
// plugin already registers a real `history` type, which register() overwrites.
const makeType = (
  type,
  { selectedByDefault = false, deactivated = false, order = 50 } = {}
) =>
  class extends RowModalSidebarType {
    static getType() {
      return type
    }

    getName() {
      return type
    }

    getComponent() {
      return { name: `${type}-component`, render: () => null }
    }

    isDeactivated() {
      return deactivated
    }

    isSelectedByDefault() {
      return selectedByDefault
    }

    getOrder() {
      return order
    }
  }

describe('RowEditModalSidebar', () => {
  let testApp = null

  // This Nuxt/happy-dom vitest env does not provide localStorage; polyfill it
  // so the helper's real read/write (and thus persistence assertions) work.
  beforeAll(() => {
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
      }
    }
  })

  beforeEach(() => {
    testApp = new TestApp()
    localStorage.clear()
  })

  afterEach(async () => {
    localStorage.clear()
    await testApp.afterEach()
  })

  const database = { id: 1, workspace: { id: 1 } }
  const table = { id: 1 }

  const registerTypes = (types) => {
    const registry = testApp.getRegistry()
    types.forEach((TypeClass) =>
      registry.register('rowModalSidebar', new TypeClass({ app: testApp._app }))
    )
  }

  const mount = async () =>
    testApp.mount(RowEditModalSidebar, {
      props: { database, table, fields: [], row: { id: 1, _: {} }, view: null },
    })

  test('selects the default tab when no preference is stored', async () => {
    registerTypes([
      makeType('comments', { selectedByDefault: true, order: 0 }),
      makeType('history', { order: 10 }),
    ])
    const wrapper = await mount()
    expect(wrapper.vm.selectedTabIndex).toBe(0)
  })

  test('selects the remembered tab when it is available', async () => {
    setRowEditModalSidebarTab('history')
    registerTypes([
      makeType('comments', { selectedByDefault: true, order: 0 }),
      makeType('history', { order: 10 }),
    ])
    const wrapper = await mount()
    const index = wrapper.vm.sidebarTypes.findIndex(
      (t) => t.getType() === 'history'
    )
    expect(wrapper.vm.selectedTabIndex).toBe(index)
  })

  test('falls back to default and keeps preference when remembered tab is unavailable', async () => {
    setRowEditModalSidebarTab('comments')
    registerTypes([
      makeType('comments', {
        selectedByDefault: true,
        deactivated: true,
        order: 0,
      }),
      makeType('history', { order: 10 }),
    ])
    const wrapper = await mount()
    const historyIndex = wrapper.vm.sidebarTypes.findIndex(
      (t) => t.getType() === 'history'
    )
    expect(wrapper.vm.selectedTabIndex).toBe(historyIndex)
    // Preference is preserved for when comments is available again.
    expect(getRowEditModalSidebarTab()).toBe('comments')
  })

  test('persists the tab type when the user selects a different tab', async () => {
    registerTypes([
      makeType('comments', { selectedByDefault: true, order: 0 }),
      makeType('history', { order: 10 }),
    ])
    const wrapper = await mount()
    const historyIndex = wrapper.vm.sidebarTypes.findIndex(
      (t) => t.getType() === 'history'
    )
    wrapper.vm.onTabSelected(historyIndex)
    expect(getRowEditModalSidebarTab()).toBe('history')
  })
})
