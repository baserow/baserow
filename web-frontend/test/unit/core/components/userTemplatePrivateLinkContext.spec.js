import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import UserTemplatePrivateLinkContext from '@baserow/modules/core/components/template/UserTemplatePrivateLinkContext'

const TOKEN = 'a'.repeat(64)
const NEW_TOKEN = 'b'.repeat(64)

const userTemplate = (values = {}) => ({
  id: 3,
  slug: 'sprint-tracker',
  type: 'user',
  name: 'Sprint Tracker',
  state: 'private',
  private_link_token: null,
  ...values,
})

describe('UserTemplatePrivateLinkContext', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn() } })
  })

  afterEach(async () => {
    vi.unstubAllGlobals()
    await testApp.afterEach()
  })

  // Like the list, which replaces the template once it changed.
  const mountAndOpen = async (template) => {
    const wrapper = await testApp.mount(UserTemplatePrivateLinkContext, {
      props: {
        template,
        onChanged: (changed) => wrapper.setProps({ template: changed }),
      },
    })
    wrapper.vm.toggle(document.body, 'bottom', 'right', 4, 0, true)
    await flushPromises()
    return wrapper
  }

  const urlToken = (wrapper) => {
    const box = wrapper.find('.user-template-private-link__url-box')
    return box.exists() ? new URL(box.text()).pathname.split('/').pop() : null
  }

  const sentRequests = () =>
    [...testApp.mock.history.patch, ...testApp.mock.history.post].map(
      ({ method, url, data }) => [method, url, data && JSON.parse(data)]
    )

  test('creates the link and shows it', async () => {
    testApp.mock
      .onPatch('/templates/sprint-tracker/')
      .reply(200, userTemplate({ private_link_token: TOKEN }))
    const wrapper = await mountAndOpen(userTemplate())

    expect(urlToken(wrapper)).toBeNull()

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(sentRequests()).toStrictEqual([
      ['patch', '/templates/sprint-tracker/', { private_link: true }],
    ])
    const url = new URL(
      wrapper.find('.user-template-private-link__url-box').text()
    )
    expect(url.pathname).toBe(`/template/sprint-tracker/private-link/${TOKEN}`)
    expect(testApp.store.state.toast.items[0]).toMatchObject({
      type: 'success',
      title: 'userTemplatePrivateLink.createdTitle',
    })

    await wrapper.find('.user-template-private-link__action').trigger('click')
    await flushPromises()

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(url.toString())
  })

  const ROTATE_URL = '/templates/sprint-tracker/rotate-private-link-token/'

  test.each([
    [
      'regenerate',
      '.user-template-private-link__action:last-child',
      ['post', ROTATE_URL, undefined],
      NEW_TOKEN,
      'regeneratedTitle',
    ],
    [
      'remove',
      '.context__footer .button-text',
      ['patch', '/templates/sprint-tracker/', { private_link: false }],
      null,
      'removedTitle',
    ],
  ])(
    'sends %s without a confirmation',
    async (operation, selector, request, token, toastTitle) => {
      const answer = [200, userTemplate({ private_link_token: token })]
      testApp.mock.onPatch('/templates/sprint-tracker/').reply(...answer)
      testApp.mock.onPost(ROTATE_URL).reply(...answer)
      const wrapper = await mountAndOpen(
        userTemplate({ private_link_token: TOKEN })
      )

      await wrapper.find(selector).trigger('click')
      await flushPromises()

      expect(sentRequests()).toStrictEqual([request])
      expect(urlToken(wrapper)).toBe(token)
      expect(testApp.store.state.toast.items[0]).toMatchObject({
        type: 'success',
        title: `userTemplatePrivateLink.${toastTitle}`,
      })
      // It stays open, also to create a new link after turning it off.
      expect(wrapper.vm.isOpen()).toBe(true)
    }
  )
})
