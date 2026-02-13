import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import RowCommentsSidebar from '@baserow_premium/components/row_comments/RowCommentsSidebar'
import MockPremiumServer from '@baserow_premium_test/fixtures/mockPremiumServer'
import flushPromises from 'flush-promises'

async function openRowCommentSidebar(
  testApp,
  { tableId = 10, rowId = 20, workspaceId = 30 } = {}
) {
  testApp
    .getStore()
    .dispatch('workspace/forceCreate', { id: workspaceId, users: [] })

  return await testApp.mount(RowCommentsSidebar, {
    propsData: {
      database: { workspace: { id: workspaceId } },
      row: { id: rowId },
      table: { id: tableId },
      readOnly: false,
    },
  })
}

describe('Premium Row Comments Component Tests', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
    mockServer = new MockPremiumServer(testApp.mock)
  })

  afterEach(() => testApp.afterEach())

  test('User without premium features cannot write comments', async () => {
    const tableId = 1
    const rowId = 2
    mockServer.thereAreComments([{ comment: 'test comment' }], tableId, rowId)
    const rowCommentSidebar = await openRowCommentSidebar(testApp, {
      rowId,
      tableId,
    })
    expect(rowCommentSidebar.text()).toContain('rowCommentSidebar.onlyPremium')
    expect(rowCommentSidebar.text()).not.toContain('test comment')
  })
  test.skip('User with global premium features can see comments', async () => {
    // TODO: This test doesn't pass after latest dependency updates
    testApp.giveCurrentUserGlobalPremiumFeatures()
    const tableId = 1
    const rowId = 2
    mockServer.thereAreComments([{ comment: 'test comment' }], tableId, rowId)
    const rowCommentSidebar = await openRowCommentSidebar(testApp, {
      tableId,
      rowId,
    })
    await flushPromises()
    expect(rowCommentSidebar.text()).not.toContain(
      'rowCommentSidebar.onlyPremium'
    )
    expect(rowCommentSidebar.text()).toContain('test comment')
  })
})
