import ViewsContext from '@baserow/modules/database/components/view/ViewsContext'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import flushPromises from 'flush-promises'
import CreateViewModal from '@baserow/modules/database/components/view/CreateViewModal'

async function openViewContextAndClickOnCreateKanbanView(
  testApp,
  { userWorkspaceId = 1 } = {}
) {
  const viewsContext = await testApp.mount(ViewsContext, {
    propsData: {
      database: { workspace: { id: userWorkspaceId } },
      views: [],
      table: {},
      readOnly: false,
    },
  })

  await viewsContext.vm.show(viewsContext)
  // Show runs some extra code in a nextTick so flush them now.
  await flushPromises()

  const paidFeaturesModal = viewsContext.findComponent(PaidFeaturesModal)
  expect(paidFeaturesModal.isVisible()).toBe(false)

  const kanbanLink = viewsContext
    .findAll('.select__footer-create-link')
    .filter((node) => node.text() === 'premium.viewType.kanban')
    .at(0)
  await kanbanLink.trigger('click')
  await flushPromises()
  return viewsContext
}

describe('Premium View Type Component Tests', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new PremiumTestApp()
  })

  afterEach(() => testApp.afterEach())

  test('User without premium features cannot create Kanban view', async () => {
    const viewsContext = await openViewContextAndClickOnCreateKanbanView(
      testApp
    )
    expect(
      viewsContext
        .findAllComponents(CreateViewModal)
        .filter((m) => m.isVisible())
    ).toHaveLength(0)
    expect(viewsContext.findComponent(PaidFeaturesModal).isVisible()).toBe(true)
  })
  test('User with global premium features can create Kanban view', async () => {
    testApp.giveCurrentUserGlobalPremiumFeatures()

    const viewsContext = await openViewContextAndClickOnCreateKanbanView(
      testApp
    )

    const visibleCreateViewModals = viewsContext
      .findAllComponents(CreateViewModal)
      .filter((m) => m.isVisible())
    expect(visibleCreateViewModals).toHaveLength(1)
    expect(viewsContext.findComponent(PaidFeaturesModal).isVisible()).toBe(
      false
    )
  })
})
