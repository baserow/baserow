import { TestApp } from '@baserow/test/helpers/testApp'

const entry = (type, subType, item) => ({
  type,
  sub_type: subType,
  last_viewed: '2026-01-01T10:00:00Z',
  application: { id: 7, name: 'CRM', type: 'database' },
  workspace: { id: 3, name: 'Acme' },
  item,
})

describe('lastViewedItem registry types', () => {
  let testApp = null
  let registry = null

  beforeEach(() => {
    testApp = new TestApp()
    registry = testApp.getRegistry()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('the four backend types are registered in application order', () => {
    expect(
      registry.getOrderedList('lastViewedItem').map((type) => type.getType())
    ).toEqual([
      'database_view',
      'builder_page',
      'dashboard',
      'automation_workflow',
    ])
  })

  test('database views delegate to the view type and route to the table', () => {
    const type = registry.get('lastViewedItem', 'database_view')
    const view = entry('database_view', 'form', {
      id: 11,
      name: 'Signup',
      table: { id: 5, name: 'Customers' },
    })

    // Translations resolve to their key in tests.
    expect(type.getName(view)).toBe('lastViewedItemType.databaseView')
    expect(type.getIconClass(view)).toBe('baserow-icon-form color-warning')
    expect(type.getIconColor(view)).toBeNull()
    expect(type.getParentPath(view)).toEqual(['CRM', 'Customers'])
    expect(type.getRoute(view)).toEqual({
      name: 'database-table',
      params: { databaseId: 7, tableId: 5, viewId: 11 },
    })
  })

  test('database views offer one filter option per view type', () => {
    const options = registry
      .get('lastViewedItem', 'database_view')
      .getFilterOptions()

    expect(options.map((option) => option.value)).toEqual([
      'database_view:grid',
      'database_view:gallery',
      'database_view:form',
      'database_view:kanban',
      'database_view:calendar',
      'database_view:timeline',
    ])
    expect(options[0]).toEqual({
      value: 'database_view:grid',
      name: 'lastViewedItemType.databaseView',
      iconClass: 'iconoir-menu color-primary',
    })
  })

  test('homogeneous types use the application icon and a single filter option', () => {
    const page = registry.get('lastViewedItem', 'builder_page')
    const pageEntry = entry('builder_page', null, { id: 4, name: 'Home' })
    expect(page.getName(pageEntry)).toBe('lastViewedItemType.builderPage')
    expect(page.getIconColor(pageEntry)).toBe('blue')
    expect(page.getParentPath(pageEntry)).toEqual(['CRM'])
    expect(page.getFilterOptions()).toEqual([
      {
        value: 'builder_page',
        name: 'lastViewedItemType.builderPage',
        iconClass: page.getIconClass(),
      },
    ])
    expect(page.getRoute(pageEntry)).toEqual({
      name: 'builder-page',
      params: { builderId: 7, pageId: 4 },
    })

    const dashboard = registry.get('lastViewedItem', 'dashboard')
    const dashboardEntry = entry('dashboard', null, { id: 9, name: 'KPIs' })
    expect(dashboard.getParentPath(dashboardEntry)).toEqual([])
    expect(dashboard.getRoute(dashboardEntry)).toEqual({
      name: 'dashboard-application',
      params: { dashboardId: 9 },
    })

    const workflow = registry.get('lastViewedItem', 'automation_workflow')
    const workflowEntry = entry('automation_workflow', null, {
      id: 2,
      name: 'Slack',
    })
    expect(workflow.getRoute(workflowEntry)).toEqual({
      name: 'automation-workflow',
      params: { automationId: 7, workflowId: 2 },
    })
  })
})
