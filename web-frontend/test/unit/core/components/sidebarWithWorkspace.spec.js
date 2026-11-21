import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import SidebarWithWorkspace from '@baserow/modules/core/components/sidebar/SidebarWithWorkspace'

describe('SidebarWithWorkspace', () => {
  let testApp, workspace, databaseType

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Workspace',
    })
    workspace = testApp.store.getters['workspace/get'](1)
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
    testApp.mock.onGet('/workspaces/1/roles/').reply(200, [])
    databaseType = testApp.$registry.get('application', 'database')
    vi.spyOn(databaseType, 'canBeCreated').mockReturnValue(false)
    vi.spyOn(databaseType, 'isVisible').mockReturnValue(true)
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test.each([
    [[], false],
    [[{ id: 2, name: 'Old', type: 'database', tables: [] }], true],
  ])(
    'shows a type that cannot be created only with existing applications %#',
    async (applications, shown) => {
      const wrapper = await testApp.mount(SidebarWithWorkspace, {
        props: {
          applications: applications.map((application) => ({
            ...application,
            workspace,
          })),
          selectedWorkspace: workspace,
        },
      })
      const heading = wrapper
        .findAll('.tree__heading')
        .find((item) => item.text() === databaseType.getNamePlural())

      expect(Boolean(heading)).toBe(shown)
      expect(heading?.find('.tree__heading-add').exists() ?? false).toBe(false)
    }
  )

  test('keeps an agent from realtime events hidden without its flag', async () => {
    vi.spyOn(
      testApp.$registry.get('application', 'agent'),
      'canBeCreated'
    ).mockReturnValue(false)
    await testApp.store.dispatch('application/forceCreate', {
      id: 2,
      name: 'Support',
      type: 'database',
      tables: [],
      workspace,
    })
    const agent = {
      id: 3,
      name: 'Ticket triage',
      order: 2,
      type: 'agent',
      workspace,
    }
    testApp.nuxtApp.$realtime._dispatchEvent({
      type: 'application_created',
      application: agent,
    })
    testApp.nuxtApp.$realtime._dispatchEvent({
      type: 'application_updated',
      application_id: agent.id,
      application: { ...agent, name: 'Renamed triage' },
    })

    const wrapper = await testApp.mount(SidebarWithWorkspace, {
      props: {
        applications:
          testApp.store.getters['application/getAllOfWorkspace'](workspace),
        selectedWorkspace: workspace,
      },
    })

    expect(testApp.store.getters['application/get'](3).name).toBe(
      'Renamed triage'
    )
    expect(wrapper.text()).toContain('Support')
    expect(wrapper.text()).not.toContain('triage')
  })

  test('folds groups independently for each workspace', async () => {
    const secondWorkspace = { ...workspace, id: 3, name: 'Second workspace' }
    const application = { id: 2, name: 'Data', type: 'database', tables: [] }
    const wrapper = await testApp.mount(SidebarWithWorkspace, {
      props: {
        applications: [
          { ...application, workspace },
          { ...application, id: 4, workspace: secondWorkspace },
        ],
        selectedWorkspace: workspace,
      },
    })
    const databases = wrapper
      .findAll('button.tree__heading-name')
      .find((button) => button.text() === databaseType.getNamePlural())
    const databaseList = wrapper.get('[data-highlight="applications-database"]')
    const builderList = wrapper.get('[data-highlight="applications-builder"]')

    expect(databases.attributes('aria-expanded')).toBe('true')
    await databases.trigger('click')
    expect(databases.attributes('aria-expanded')).toBe('false')
    expect(databaseList.element.closest('[inert]')).not.toBeNull()
    expect(builderList.element.closest('[inert]')).toBeNull()

    await wrapper.setProps({ selectedWorkspace: secondWorkspace })
    expect(databases.attributes('aria-expanded')).toBe('true')
    expect(databaseList.element.closest('[inert]')).toBeNull()

    await wrapper.setProps({ selectedWorkspace: workspace })
    expect(databases.attributes('aria-expanded')).toBe('false')
    await databases.trigger('click')
    expect(databaseList.element.closest('[inert]')).toBeNull()
  })

  test('keeps open application sublists when selection changes', async () => {
    const { store, $registry } = testApp
    vi.spyOn(
      $registry.get('application', 'builder'),
      'isVisible'
    ).mockReturnValue(true)
    const database = await store.dispatch('application/forceCreate', {
      id: 2,
      name: 'Data',
      type: 'database',
      tables: [],
      workspace,
    })
    const builder = await store.dispatch('application/forceCreate', {
      id: 3,
      name: 'Website',
      type: 'builder',
      pages: [],
      workspace,
    })
    await store.dispatch('application/select', database)
    const wrapper = await testApp.mount(SidebarWithWorkspace, {
      props: {
        applications: [database, builder],
        selectedWorkspace: workspace,
      },
    })
    const databaseTitle = wrapper.get('.tree__link[aria-label="Data"]')
    const builderTitle = wrapper.get('.tree__link[aria-label="Website"]')
    const databasePanel = wrapper.get('.tree__item .tree__group')
    expect(databaseTitle.attributes('aria-expanded')).toBe('true')
    expect(builderTitle.attributes('aria-expanded')).toBe('false')

    await builderTitle.trigger('click')
    expect(builderTitle.attributes('aria-expanded')).toBe('true')
    expect(store.getters['application/isSelected'](database)).toBe(true)

    await store.dispatch('application/select', builder)
    expect(builderTitle.attributes('aria-expanded')).toBe('true')
    expect(databaseTitle.attributes('aria-expanded')).toBe('true')
    expect(databasePanel.element.hasAttribute('inert')).toBe(false)

    await builderTitle.trigger('click')
    expect(builderTitle.attributes('aria-expanded')).toBe('false')
    expect(databaseTitle.attributes('aria-expanded')).toBe('true')
    expect(store.getters['application/isSelected'](builder)).toBe(true)
  })
})
