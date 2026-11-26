import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import UserTemplateNotification from '@baserow/modules/core/components/notifications/UserTemplateNotification'

const data = {
  template_id: 3,
  template_name: 'Recipes',
  template_slug: 'recipes-a1b2c3',
}

let testApp = null

beforeEach(() => {
  testApp = new TestApp()
})

afterEach(async () => {
  await testApp.afterEach()
})

describe('UserTemplateNotification', () => {
  const templatePage = { name: 'template', params: { slug: 'recipes-a1b2c3' } }

  test.each([
    [
      'user_template_in_review',
      { name: 'admin-templates', query: { tab: 'in_review', template: 3 } },
    ],
    [
      'blocked_user_template_changed',
      { name: 'admin-templates', query: { tab: 'blocked', template: 3 } },
    ],
    ['user_template_approved', templatePage],
    ['user_template_rejected', templatePage],
    ['user_template_change_rejected', templatePage],
    ['user_template_unlisted', templatePage],
    ['user_template_blocked', templatePage],
    ['user_template_unblocked', templatePage],
  ])('%s opens its page', (type, route) => {
    const notificationType = testApp.getRegistry().get('notification', type)

    expect(notificationType.getRoute(data)).toEqual(route)
  })

  test.each([
    [undefined, null, null],
    ['a'.repeat(120), 'a'.repeat(120), null],
    ['a'.repeat(121), `${'a'.repeat(120)}…`, 'a'.repeat(121)],
  ])(
    'shows the template name and the reason cut to 120 characters',
    async (reason, shown, shownOnShowMore) => {
      const wrapper = await testApp.mount(UserTemplateNotification, {
        props: {
          workspace: { id: 1 },
          notification: {
            id: 5,
            type: 'user_template_rejected',
            read: true,
            data: { ...data, reason },
          },
        },
      })
      const description = wrapper.find(
        '.notification-panel__notification-content-desc'
      )

      expect(wrapper.find('strong').text()).toBe('Recipes')
      expect(description.exists() ? description.text() : null).toBe(shown)

      const showMore = wrapper.find('.user-template-notification__show-more')
      if (showMore.exists()) {
        await showMore.trigger('click')
      }
      expect(
        document
          .querySelector('.user-template-notification__full-reason')
          ?.textContent.trim() ?? null
      ).toBe(shownOnShowMore)

      await wrapper
        .find('.notification-panel__notification-link')
        .trigger('click')

      expect(wrapper.emitted('close-panel')).toHaveLength(1)
    }
  )
  test.each([
    [
      'user_template_in_review',
      'Maya submitted the template Recipes for review',
    ],
    [
      'blocked_user_template_changed',
      'Maya changed the blocked template Recipes. Check if it can be unblocked.',
    ],
  ])('%s names the author in bold', async (type, title) => {
    const wrapper = await testApp.mount(UserTemplateNotification, {
      props: {
        workspace: { id: 1 },
        notification: {
          id: 5,
          type,
          read: true,
          data: { ...data, author_name: 'Maya' },
        },
      },
    })

    expect(
      wrapper.find('.notification-panel__notification-content-title').text()
    ).toBe(title)
    expect(wrapper.findAll('strong').map((strong) => strong.text())).toEqual([
      'Maya',
      'Recipes',
    ])
  })
})
