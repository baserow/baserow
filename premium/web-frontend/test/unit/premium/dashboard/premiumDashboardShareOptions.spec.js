import { flushPromises } from '@vue/test-utils'

import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import MockPremiumServer from '@baserow_premium_test/fixtures/mockPremiumServer'
import ShareDashboardLink from '@baserow/modules/dashboard/components/sharing/ShareDashboardLink'
import Context from '@baserow/modules/core/components/Context'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

const DASHBOARD_ID = 10

async function openShareDashboardLinkContext(testApp, dashboard) {
  const shareDashboardLink = await testApp.mount(ShareDashboardLink, {
    props: { dashboard },
  })
  await shareDashboardLink.find('.header__filter-link').trigger('click')
  const context = shareDashboardLink.findComponent(Context)
  expect(context.isVisible()).toBe(true)
  return context
}

function findLogoOption(context) {
  return context
    .findAll('.dashboard-sharing__option')
    .filter((el) => el.text().includes('premiumDashboardShareOptions.hideLogo'))
    .at(0)
}

describe('Premium share dashboard link options', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
    mockServer = new MockPremiumServer(testApp.mock)
  })

  afterEach(() => testApp.afterEach())

  async function createSharedDashboard() {
    const workspace = { id: 1, name: 'testWorkspace' }
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)
    await testApp.getStore().dispatch('application/forceCreate', {
      id: DASHBOARD_ID,
      type: 'dashboard',
      name: 'Dashboard',
      workspace,
      public: true,
      slug: 'dashboard-slug',
      public_has_password: false,
      show_logo: true,
    })
    return testApp.getStore().getters['application/get'](DASHBOARD_ID)
  }

  test('User without premium sees the paid feature modal instead of hiding the logo', async () => {
    const dashboard = await createSharedDashboard()

    const context = await openShareDashboardLinkContext(testApp, dashboard)
    const logoOption = findLogoOption(context)

    expect(logoOption.classes()).toContain(
      'dashboard-sharing__option--disabled'
    )
    expect(logoOption.find('.iconoir-lock').exists()).toBe(true)

    await logoOption.find('.switch').trigger('click')

    expect(context.findAllComponents(PaidFeaturesModal)).toHaveLength(1)
    expect(
      testApp.getStore().getters['application/get'](DASHBOARD_ID).show_logo
    ).toBe(true)
  })

  test('User with premium can hide the logo on the shared dashboard', async () => {
    const dashboard = await createSharedDashboard()
    mockServer.expectPremiumDashboardUpdate(DASHBOARD_ID, {
      show_logo: false,
    })
    testApp.giveCurrentUserGlobalPremiumFeatures()

    const context = await openShareDashboardLinkContext(testApp, dashboard)
    const logoOption = findLogoOption(context)

    expect(logoOption.classes()).not.toContain(
      'dashboard-sharing__option--disabled'
    )
    expect(logoOption.find('.iconoir-lock').exists()).toBe(false)

    await logoOption.find('.switch').trigger('click')
    await flushPromises()

    expect(context.findAllComponents(PaidFeaturesModal)).toHaveLength(0)
    expect(
      testApp.getStore().getters['application/get'](DASHBOARD_ID).show_logo
    ).toBe(false)
  })
})
