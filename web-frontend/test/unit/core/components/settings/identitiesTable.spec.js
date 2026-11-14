import flushPromises from 'flush-promises'

import IdentitiesTable from '@baserow/modules/core/components/settings/identities/IdentitiesTable'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('IdentitiesTable', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('refreshes when an identity is restored in its workspace', async () => {
    testApp.mock
      .onGet('/identities/workspace/1/')
      .replyOnce(200, { count: 0, results: [] })
      .onGet('/identities/workspace/1/')
      .replyOnce(200, {
        count: 1,
        results: [
          {
            id: 10,
            name: 'Restored identity',
            last_active: null,
            role_uid: 'NO_ACCESS',
          },
        ],
      })
    const wrapper = await testApp.mount(IdentitiesTable, {
      props: {
        workspace: { id: 1, name: 'Workspace', _: { roles: [] } },
      },
    })

    expect(wrapper.text()).not.toContain('Restored identity')

    await testApp.store.dispatch('identity/forceCreate', {
      id: 10,
      workspace_id: 1,
      name: 'Restored identity',
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Restored identity')
  })

  test('uses the paginated response total in the heading', async () => {
    testApp.mock.onGet('/identities/workspace/1/').replyOnce(200, {
      count: 250,
      results: [
        {
          id: 10,
          name: 'First page identity',
          last_active: null,
          role_uid: 'NO_ACCESS',
        },
      ],
    })

    const wrapper = await testApp.mount(IdentitiesTable, {
      global: {
        mocks: {
          $t: (key, params) =>
            key === 'identities.title' ? `${params.count} identities` : key,
        },
      },
      props: {
        workspace: { id: 1, name: 'Workspace', _: { roles: [] } },
      },
    })
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('250 identities')
  })

  test('passes realtime updates to the selected editor through its identity prop', async () => {
    const identity = {
      id: 10,
      workspace_id: 1,
      name: 'Writer',
      teams: [{ id: 3 }],
    }
    await testApp.store.dispatch('identity/forceCreate', identity)
    const wrapper = await testApp.mount(
      {
        ...IdentitiesTable,
        computed: { ...IdentitiesTable.computed, canManage: () => true },
      },
      {
        props: { workspace: { id: 1, name: 'Workspace', _: { roles: [] } } },
        global: {
          stubs: {
            CrudTable: {
              name: 'CrudTable',
              template: '<div><slot name="menus" /></div>',
              methods: { refresh() {} },
            },
            IdentityContext: {
              name: 'IdentityContext',
              template: '<div />',
              methods: { show() {} },
            },
            ManageIdentityModal: {
              name: 'ManageIdentityModal',
              props: ['identity'],
              template: '<div />',
            },
          },
        },
      }
    )
    wrapper
      .findComponent({ name: 'CrudTable' })
      .vm.$emit('row-context', { row: identity, target: document.body })
    await flushPromises()
    const editor = () =>
      wrapper
        .findAllComponents({ name: 'ManageIdentityModal' })
        .find((modal) => modal.props('identity'))
    expect(editor().props('identity').teams).toEqual([{ id: 3 }])

    await testApp.store.dispatch('identity/forceUpdate', {
      ...identity,
      teams: [],
    })
    await flushPromises()
    expect(editor().props('identity').teams).toEqual([])
  })

  test.each([
    [['identity.create'], 1, 3, false, false],
    [['identity.update'], 0, 4, true, false],
    [['identity.delete'], 0, 4, false, true],
    [[], 0, 3, false, false],
  ])(
    'shows controls for independent Identity permissions: %s',
    async (
      permissions,
      createButtonCount,
      columnCount,
      showsEdit,
      showsDelete
    ) => {
      const identity = { id: 10, workspace_id: 1, name: 'Writer' }
      await testApp.store.dispatch('identity/forceCreate', identity)
      const wrapper = await testApp.mount(IdentitiesTable, {
        props: {
          workspace: { id: 1, name: 'Workspace', _: { roles: [] } },
        },
        global: {
          mocks: {
            $hasPermission: (operation) => permissions.includes(operation),
          },
          stubs: {
            CrudTable: {
              name: 'CrudTable',
              props: ['columns'],
              data: () => ({ identity }),
              template: `
                <div>
                  <slot name="empty" />
                  <slot name="primary-action" />
                  <span class="column-count">{{ columns.length }}</span>
                  <button class="open-row" @click="$emit('row-context', { row: identity, target: $el })">Open row</button>
                  <slot name="menus" />
                </div>
              `,
              methods: { refresh() {} },
            },
            Context: {
              template: '<div><slot /></div>',
              methods: { show() {}, hide() {} },
            },
            ManageIdentityModal: {
              name: 'ManageIdentityModal',
              props: ['identity'],
              template:
                '<div class="identity-modal">{{ identity ? "update" : "create" }}</div>',
              methods: { show() {} },
            },
          },
        },
      })

      expect(
        wrapper
          .findAll('button')
          .filter((button) => button.text() === 'identities.create')
      ).toHaveLength(createButtonCount)
      expect(wrapper.find('.column-count').text()).toBe(String(columnCount))

      await wrapper.find('.open-row').trigger('click')
      await flushPromises()
      expect(wrapper.text().includes('identities.edit')).toBe(showsEdit)
      expect(wrapper.text().includes('identities.delete')).toBe(showsDelete)
      expect(
        wrapper
          .findAll('.identity-modal')
          .some((modal) => modal.text() === 'update')
      ).toBe(showsEdit)
    }
  )
})
