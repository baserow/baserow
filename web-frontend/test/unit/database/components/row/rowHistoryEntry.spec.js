import { TestApp } from '@baserow/test/helpers/testApp'
import RowHistoryEntry from '@baserow/modules/database/components/row/RowHistoryEntry'
import { UserSubjectType } from '@baserow/modules/core/subjectTypes'

describe('RowHistoryEntry', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.store.state.workspace.items = [
      { users: [{ user_id: 1, name: 'Colliding user' }] },
    ]
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test('renders a deleted Identity from its recorded identity metadata', async () => {
    const wrapper = await testApp.mount(RowHistoryEntry, {
      propsData: {
        workspaceId: 1,
        fields: [],
        entry: {
          action_type: 'update_row',
          action_command_type: 'DO',
          timestamp: '2026-08-05T12:00:00Z',
          user: { id: 1, name: 'Current user' },
          actor: {
            id: 42,
            type: 'auth.User',
            user_type: 'identity',
            name: 'Row writer',
          },
          before: {},
          after: {},
          fields_metadata: {},
        },
      },
    })

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('shows an identity actor with the identity avatar of its subject type', async () => {
    vi.spyOn(
      UserSubjectType.prototype,
      'identityIconClass',
      'get'
    ).mockReturnValue('iconoir-identity-test')
    const wrapper = await testApp.mount(RowHistoryEntry, {
      propsData: {
        workspaceId: 1,
        fields: [],
        entry: {
          action_type: 'update_row',
          action_command_type: 'DO',
          timestamp: '2026-08-05T12:00:00Z',
          user: { id: 42, name: 'Row writer' },
          actor: {
            id: 42,
            type: 'auth.User',
            user_type: 'identity',
            name: 'Row writer',
          },
          before: {},
          after: {},
          fields_metadata: {},
        },
      },
    })

    expect(
      wrapper.find('.identity-avatar .iconoir-identity-test').exists()
    ).toBe(true)
  })

  test('shows the stored name of an actor whose type is not registered', async () => {
    const wrapper = await testApp.mount(RowHistoryEntry, {
      propsData: {
        workspaceId: 1,
        fields: [],
        entry: {
          action_type: 'update_row',
          action_command_type: 'DO',
          timestamp: '2026-08-05T12:00:00Z',
          user: { id: 1, name: 'Import token' },
          actor: { id: 1, type: 'core.Token', name: 'Import token' },
          before: {},
          after: {},
          fields_metadata: {},
        },
      },
    })

    expect(wrapper.find('.row-history-entry__name').text()).toContain(
      'Import token'
    )
    expect(wrapper.find('.row-history-entry__initials').text()).toBe('I')
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
