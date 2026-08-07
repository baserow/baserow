import { TestApp } from '@baserow/test/helpers/testApp'
import ViewsAdminTable from '@baserow/modules/database/components/admin/views/ViewsAdminTable'
import ViewsAdminContext from '@baserow/modules/database/components/admin/views/contexts/ViewsAdminContext'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import flushPromises from 'flush-promises'

// Mock out debounce so we dont have to wait or simulate waiting for the search
// debounce.
vi.mock('lodash/debounce', () => ({ default: vi.fn((fn) => fn) }))

describe('ViewsAdminTable component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    // The workspace filter dropdown fetches its options as soon as it is rendered,
    // so every test needs this whether or not it filters on a workspace.
    testApp.mock
      .onGet('/admin/workspaces/options/')
      .reply(200, { count: 1, results: [{ id: 30, value: 'Workspace' }] })
  })

  afterEach(async () => await testApp.afterEach())

  function aView(view = {}) {
    return {
      id: 1,
      name: 'Grid view',
      slug: 'view-slug',
      type: 'grid',
      table_id: 10,
      table_name: 'Table',
      database_id: 20,
      database_name: 'Database',
      workspace_id: 30,
      workspace_name: 'Workspace',
      public: true,
      public_view_has_password: false,
      owned_by_id: 40,
      owned_by_username: 'owner@baserow.io',
      ownership_type: 'collaborative',
      created_on: '2026-07-20T12:00:00.000000Z',
      ...view,
    }
  }

  function thereAreViews(views, params) {
    testApp.mock
      .onGet('/database/admin/views/', { params })
      .reply(200, { count: views.length, results: views })
  }

  test('public views are listed with the only public filter on by default', async () => {
    thereAreViews([aView()], { page: 1, only_public: 'true' })

    const viewsAdmin = await testApp.mount(ViewsAdminTable, {})
    await flushPromises()

    expect(viewsAdmin.find('.switch--active').exists()).toBe(true)
    const body = viewsAdmin.find('tbody')
    expect(body.text()).toContain('Grid view')
    expect(body.text()).toContain('Table')
    expect(body.text()).toContain('Workspace')
    expect(body.text()).toContain('owner@baserow.io')
    expect(body.find('.iconoir-globe').exists()).toBe(true)
  })

  test('toggling the only public filter fetches all views', async () => {
    thereAreViews([aView()], { page: 1, only_public: 'true' })
    thereAreViews(
      [aView(), aView({ id: 2, name: 'Private view', public: false })],
      { page: 1 }
    )

    const viewsAdmin = await testApp.mount(ViewsAdminTable, {})
    await flushPromises()
    expect(viewsAdmin.findAll('tbody tr').length).toBe(1)

    await viewsAdmin.find('.switch').trigger('click')
    await flushPromises()

    expect(viewsAdmin.find('.switch--active').exists()).toBe(false)
    expect(viewsAdmin.findAll('tbody tr').length).toBe(2)
    expect(viewsAdmin.find('tbody').text()).toContain('Private view')
  })

  test('the search route query is applied to the initial fetch', async () => {
    thereAreViews([aView()], { page: 1, only_public: 'true', search: 'Grid' })

    const viewsAdmin = await testApp.mount(ViewsAdminTable, {
      route: '/?search=Grid',
    })
    await flushPromises()

    expect(viewsAdmin.find('input').element.value).toBe('Grid')
    expect(viewsAdmin.find('tbody').text()).toContain('Grid view')
  })

  test('making a view private keeps the updated row visible', async () => {
    thereAreViews([aView()], { page: 1, only_public: 'true' })
    testApp.mock
      .onPatch('/database/admin/views/1/')
      .reply(200, aView({ public: false }))

    const viewsAdmin = await testApp.mount(ViewsAdminTable, {})
    await flushPromises()
    expect(viewsAdmin.find('tbody .iconoir-globe').exists()).toBe(true)

    await viewsAdmin.find('.data-table__more').trigger('click')
    const context = viewsAdmin.findComponent(ViewsAdminContext)
    const makePrivateLink = context
      .findAll('.context__menu-item-link')
      .find((link) => link.text().includes('viewsAdminContext.makePrivate'))
    await makePrivateLink.trigger('click')
    await flushPromises()

    // The row deliberately remains visible even though it no longer matches the
    // only public filter, so that the change can easily be undone if needed.
    expect(viewsAdmin.findAll('tbody tr').length).toBe(1)
    expect(viewsAdmin.find('tbody .iconoir-globe').exists()).toBe(false)
  })

  test('filter by workspace applies the workspace filter', async () => {
    thereAreViews([aView()], { page: 1, only_public: 'true' })
    thereAreViews([aView(), aView({ id: 2, name: 'Second view' })], {
      page: 1,
      only_public: 'true',
      workspace_id: '30',
    })

    const viewsAdmin = await testApp.mount(ViewsAdminTable, {})
    await flushPromises()

    await viewsAdmin.find('.data-table__more').trigger('click')
    const context = viewsAdmin.findComponent(ViewsAdminContext)
    await context
      .findAll('.context__menu-item-link')
      .find((link) => link.text().includes('viewsAdminContext.filterWorkspace'))
      .trigger('click')
    await flushPromises()

    // The only public filter is left alone, it narrows the workspace further.
    expect(viewsAdmin.find('.switch--active').exists()).toBe(true)
    expect(viewsAdmin.find('input').element.value).toBe('')
    expect(viewsAdmin.findAll('tbody tr').length).toBe(2)
    expect(viewsAdmin.find('tbody').text()).toContain('Second view')

    // The dropdown names the workspace the filter came from, so it is visible that
    // one is applied and which.
    expect(viewsAdmin.find('.dropdown__selected-text').text()).toBe('Workspace')
  })

  test('selecting a workspace in the dropdown keeps its name visible', async () => {
    thereAreViews([aView()], { page: 1, only_public: 'true' })
    thereAreViews([aView()], {
      page: 1,
      only_public: 'true',
      workspace_id: '30',
    })

    const viewsAdmin = await testApp.mount(ViewsAdminTable, {})
    await flushPromises()

    const dropdown = viewsAdmin.findComponent(PaginatedDropdown)
    await dropdown.find('.dropdown__selected').trigger('click')
    await flushPromises()
    await dropdown
      .findAll('.select__item-link')
      .find((link) => link.text() === 'Workspace')
      .trigger('click')
    await flushPromises()

    expect(viewsAdmin.find('.dropdown__selected').text()).toBe('Workspace')
  })
})
