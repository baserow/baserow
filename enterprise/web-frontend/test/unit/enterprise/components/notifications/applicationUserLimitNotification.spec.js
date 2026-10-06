import { mountSuspended } from '@nuxt/test-utils/runtime'

import ApplicationUserLimitNotification from '@baserow_enterprise/components/notifications/ApplicationUserLimitNotification'

const mountNotification = (data) =>
  mountSuspended(ApplicationUserLimitNotification, {
    props: {
      workspace: { id: 1 },
      notification: {
        type: 'application_user_limit',
        read: true,
        data,
      },
    },
  })

const notificationData = (overrides = {}) => ({
  workspace_id: 1,
  workspace_name: 'My workspace',
  threshold: 80,
  usage: 8,
  limit: 10,
  ...overrides,
})

describe('ApplicationUserLimitNotification', () => {
  test('renders the warning wording below the limit threshold', async () => {
    const wrapper = await mountNotification(
      notificationData({ threshold: 80, usage: 8, limit: 10 })
    )

    expect(wrapper.text()).toBe(
      'My workspace has used 8 of the 10 available application users.'
    )
  })

  test('renders the limit reached wording at the limit threshold', async () => {
    const wrapper = await mountNotification(
      notificationData({ threshold: 100, usage: 10 })
    )

    expect(wrapper.text()).toBe(
      'My workspace has reached the application user limit of 10. ' +
        'Once it goes over, no one can sign in to its published apps until ' +
        'you upgrade.'
    )
  })

  test('says the instance used the application users for an instance wide limit', async () => {
    const wrapper = await mountNotification(
      notificationData({
        threshold: 80,
        usage: 8,
        limit: 10,
        instance_wide: true,
      })
    )

    expect(wrapper.text()).toBe(
      'This instance has used 8 of the 10 available application users. ' +
        'The limit is shared by all workspaces, including My workspace.'
    )
  })

  test('says the instance reached the limit for an instance wide limit', async () => {
    const wrapper = await mountNotification(
      notificationData({ threshold: 100, usage: 10, instance_wide: true })
    )

    expect(wrapper.text()).toBe(
      'This instance has reached the application user limit of 10. ' +
        'Once it goes over, no one can sign in to the published apps of any ' +
        'workspace, including My workspace, until the license is upgraded.'
    )
  })
})
