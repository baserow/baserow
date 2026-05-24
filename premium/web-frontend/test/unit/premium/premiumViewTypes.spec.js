import ViewsContext from '@baserow/modules/database/components/view/ViewsContext'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import flushPromises from 'flush-promises'
import CreateViewModal from '@baserow/modules/database/components/view/CreateViewModal'
import CreateViewLink from '@baserow/modules/database/components/view/CreateViewLink'

async function openViewContextAndClickOnCreateKanbanView(
  testApp,
  { userWorkspaceId = 1 } = {}
) {
  const viewsContext = await testApp.mount(ViewsContext, {
    props: {
      database: { workspace: { id: userWorkspaceId } },
      views: [],
      table: {},
      readOnly: false,
    },
  })

  await viewsContext.vm.show(viewsContext)
  await flushPromises()

  const paidFeaturesModal = viewsContext.findComponent(PaidFeaturesModal)
  expect(paidFeaturesModal.vm.$refs.modal.open).toBe(false)

  const kanbanCreateLink = viewsContext
    .findAllComponents(CreateViewLink)
    .find((c) => c.vm.viewType.getType() === 'kanban')
  kanbanCreateLink.vm.select()
  await flushPromises()
  return viewsContext
}

describe('Premium View Type Component Tests', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
  })

  afterEach(() => testApp.afterEach())

  test('User without premium features cannot create Kanban view', async () => {
    const viewsContext =
      await openViewContextAndClickOnCreateKanbanView(testApp)
    expect(
      viewsContext
        .findAllComponents(CreateViewModal)
        .filter((m) => m.vm.$refs.modal.open)
    ).toHaveLength(0)
    expect(
      viewsContext.findComponent(PaidFeaturesModal).vm.$refs.modal.open
    ).toBe(true)
  })
  test('User with global premium features can create Kanban view', async () => {
    testApp.giveCurrentUserGlobalPremiumFeatures()

    const viewsContext =
      await openViewContextAndClickOnCreateKanbanView(testApp)

    const visibleCreateViewModals = viewsContext
      .findAllComponents(CreateViewModal)
      .filter((m) => m.vm.$refs.modal.open)
    expect(visibleCreateViewModals).toHaveLength(1)
    expect(
      viewsContext.findComponent(PaidFeaturesModal).vm.$refs.modal.open
    ).toBe(false)
  })
})
