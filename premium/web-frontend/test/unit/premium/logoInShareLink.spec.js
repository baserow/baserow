import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import MockPremiumServer from '@baserow_premium_test/fixtures/mockPremiumServer'
import ShareViewLink from '@baserow/modules/database/components/view/ShareViewLink'
import Context from '@baserow/modules/core/components/Context'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

async function openShareViewLinkContext(testApp, view) {
  const shareViewLinkComponent = await testApp.mount(ShareViewLink, {
    propsData: {
      view,
      readOnly: false,
    },
  })
  await shareViewLinkComponent.find('.header__filter-link').trigger('click')
  const context = shareViewLinkComponent.findComponent(Context)
  expect(context.isVisible()).toBe(true)
  return context
}

describe('Premium Share View Link Tests', () => {
  let testApp = null
  let mockServer = null

  beforeAll(() => {
    testApp = new PremiumTestApp()
    mockServer = new MockPremiumServer(testApp.mock)
  })

  afterEach(() => testApp.afterEach())

  test('User without global premium cannot toggle off the Baserow logo', async () => {
    const workspace = { id: 1, name: 'testWorkspace' }
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)
    const tableId = 1
    const databaseId = 3
    const viewId = 4
    testApp.getStore().dispatch('application/forceCreate', {
      id: databaseId,
      type: 'database',
      tables: [{ id: tableId }],
      workspace,
    })
    const view = {
      id: viewId,
      type: 'grid',
      public: true,
      table: { database_id: databaseId },
      show_logo: true,
      isShared: true,
    }
    testApp.getStore().dispatch('view/forceCreate', { data: view })

    const shareViewLinkContext = await openShareViewLinkContext(testApp, view)
    const logoSharingOption = shareViewLinkContext
      .findAll('.view-sharing__option')
      .filter((el) => el.text().includes('shareLinkOptions.baserowLogo.label'))
      .at(0)
    await logoSharingOption.find('.switch').trigger('click')
    expect(
      shareViewLinkContext.findAllComponents(PaidFeaturesModal)
    ).toHaveLength(1)
  })

  test('User with global premium can toggle off the Baserow logo', async () => {
    const workspace = { id: 1, name: 'testWorkspace' }
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)
    const tableId = 1
    const databaseId = 3
    const viewId = 4
    testApp.getStore().dispatch('application/forceCreate', {
      id: databaseId,
      type: 'database',
      tables: [{ id: tableId }],
      workspace,
    })
    const view = {
      id: viewId,
      type: 'grid',
      public: true,
      table: { database_id: databaseId },
      show_logo: true,
    }
    mockServer.expectPremiumViewUpdate(viewId, {
      show_logo: false,
    })
    testApp.getStore().dispatch('view/forceCreate', { data: view })
    testApp.giveCurrentUserGlobalPremiumFeatures()

    const shareViewLinkContext = await openShareViewLinkContext(testApp, view)
    const logoSharingOption = shareViewLinkContext
      .findAll('.view-sharing__option')
      .filter((el) => el.text().includes('shareLinkOptions.baserowLogo.label'))
      .at(0)
    await logoSharingOption.find('.switch').trigger('click')
    expect(
      shareViewLinkContext.findAllComponents(PaidFeaturesModal)
    ).toHaveLength(0)
  })
})
