import { TestApp } from '@baserow/test/helpers/testApp'
import AutomaticSnapshotFailedNotification from '@baserow_enterprise/components/notifications/AutomaticSnapshotFailedNotification'
import { AutomaticSnapshotFailedNotificationType } from '@baserow_enterprise/notificationTypes'

describe('automatic snapshot failure notification', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('links to the workspace that owns the failed snapshot', () => {
    const type = new AutomaticSnapshotFailedNotificationType({ app: {} })
    expect(type.getRoute({ workspace_id: 42, application_id: 17 })).toEqual({
      name: 'workspace',
      params: { workspaceId: 42 },
    })
  })

  test('shows the application and safe error, and closes the panel on click', async () => {
    const wrapper = await testApp.mount(AutomaticSnapshotFailedNotification, {
      props: {
        workspace: { id: 42 },
        notification: {
          type: 'automatic_snapshot_failed',
          read: true,
          data: {
            workspace_id: 42,
            application_id: 17,
            application_name: '<script>CRM</script>',
            error: 'The snapshot could not be created.',
          },
        },
      },
      global: {
        mocks: {
          $t: (key, params) => `${key} ${JSON.stringify(params)}`,
        },
        stubs: {
          'i18n-t': {
            props: ['keypath'],
            template: '<span>{{ keypath }} <slot name="name" /></span>',
          },
        },
      },
    })

    expect(wrapper.html()).toMatchSnapshot()
    await wrapper.find('a').trigger('click')
    expect(wrapper.emitted('close-panel')).toHaveLength(1)
  })
})
