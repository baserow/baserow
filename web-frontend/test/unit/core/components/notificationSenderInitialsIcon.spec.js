import NotificationSenderInitialsIcon from '@baserow/modules/core/components/notifications/NotificationSenderInitialsIcon'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('NotificationSenderInitialsIcon', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('identifies identity senders with the shared identity avatar', async () => {
    const wrapper = await testApp.mount(NotificationSenderInitialsIcon, {
      props: {
        notification: {
          sender: { first_name: 'Row writer', user_type: 'identity' },
        },
      },
    })

    expect(wrapper.get('.identity-avatar .avatar__icon').classes()).toContain(
      testApp.$registry.get('subject', 'auth.User').identityIconClass
    )
    expect(wrapper.find('[role="img"]').attributes('aria-label')).toBe(
      'subjectType.identity'
    )
    expect(wrapper.attributes('title')).toBe('subjectType.identity')
    expect(wrapper.text()).toBe('')
  })

  test.each(['human', undefined])(
    'shows initials for a sender with user_type=%s',
    async (userType) => {
      const wrapper = await testApp.mount(NotificationSenderInitialsIcon, {
        props: {
          notification: {
            sender: { first_name: 'Jane Doe', user_type: userType },
          },
        },
      })

      expect(wrapper.text()).toBe('JD')
      expect(wrapper.find('.identity-avatar').exists()).toBe(false)
    }
  )

  test('handles a deleted sender', async () => {
    const wrapper = await testApp.mount(NotificationSenderInitialsIcon, {
      props: { notification: { sender: null } },
    })

    expect(wrapper.text()).toBe('')
    expect(wrapper.find('.identity-avatar').exists()).toBe(false)
  })
})
