import { TestApp } from '@baserow/test/helpers/testApp'
import RowHistoryEntry from '@baserow/modules/database/components/row/RowHistoryEntry'

describe('RowHistoryEntry', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.store.state.workspace.items = [
      { users: [{ user_id: 1, name: 'Colliding user' }] },
    ]
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('renders an Agent actor without resolving it as a colliding user', async () => {
    const wrapper = await testApp.mount(RowHistoryEntry, {
      propsData: {
        workspaceId: 1,
        fields: [],
        entry: {
          action_type: 'update_row',
          action_command_type: 'DO',
          timestamp: '2026-08-05T12:00:00Z',
          user: { id: 1, name: 'Current user' },
          actor: { id: 1, type: 'core.Agent', name: 'Row writer' },
          before: {},
          after: {},
          fields_metadata: {},
        },
      },
    })

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('translates an Anonymous User actor when rendering', async () => {
    const wrapper = await testApp.mount(RowHistoryEntry, {
      propsData: {
        workspaceId: 1,
        fields: [],
        entry: {
          action_type: 'submit_form',
          action_command_type: 'DO',
          timestamp: '2026-08-05T12:00:00Z',
          user: { id: null, name: 'Anonymous User' },
          actor: { id: null, type: 'anonymous', name: 'Anonymous User' },
          before: {},
          after: {},
          fields_metadata: {},
        },
      },
    })

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('resolves a User actor through its registered subject type', async () => {
    const wrapper = await testApp.mount(RowHistoryEntry, {
      propsData: {
        workspaceId: 1,
        fields: [],
        entry: {
          action_type: 'update_row',
          action_command_type: 'DO',
          timestamp: '2026-08-05T12:00:00Z',
          user: { id: 1, name: 'Stored user name' },
          actor: { id: 1, type: 'auth.User', name: 'Stored user name' },
          before: {},
          after: {},
          fields_metadata: {},
        },
      },
    })

    expect(wrapper.html()).toMatchSnapshot()
  })
})
