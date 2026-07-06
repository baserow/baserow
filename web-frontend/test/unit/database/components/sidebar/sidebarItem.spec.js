import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test, describe } from 'vitest'

import SidebarItem from '@baserow/modules/database/components/sidebar/SidebarItem'

describe('SidebarItem import permission gating', () => {
  const database = {
    id: 1,
    workspace: { id: 10 },
    _: { loading: false },
    tables: [],
  }
  const table = { id: 5, name: 'Cars', _: { selected: false }, data_sync: null }

  // Mount with an explicit set of granted permission operations. The context
  // menu content lives inside a <Context> slot (only rendered once opened), so
  // Context is stubbed to render its slot immediately.
  const mountSidebar = (granted) =>
    mountSuspended(SidebarItem, {
      props: { database, table },
      global: {
        mocks: {
          $hasPermission: (operation) => granted.includes(operation),
        },
        stubs: {
          SidebarImportTableContextItem: {
            template: '<a class="import-item-stub" />',
          },
          SidebarDuplicateTableContextItem: true,
          ExportTableModal: true,
          WebhookModal: true,
          SyncTableModal: true,
          ConfigureDataSyncModal: true,
          Context: { template: '<div><slot /></div>' },
        },
      },
    })

  test('shows the import item when the user has import_rows permission', async () => {
    const wrapper = await mountSidebar(['database.table.import_rows'])
    expect(wrapper.find('.import-item-stub').exists()).toBe(true)
    // import_rows alone must reveal the three-dots menu button (showOptions).
    expect(wrapper.find('.tree__options').exists()).toBe(true)
  })

  test('hides the import item without import_rows permission', async () => {
    // Export is granted so the menu still opens; the import item must stay gated.
    const wrapper = await mountSidebar(['database.table.run_export'])
    expect(wrapper.find('.tree__options').exists()).toBe(true)
    expect(wrapper.find('.import-item-stub').exists()).toBe(false)
  })
})
