import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplatePrivateLinkPage from '@baserow/modules/core/pages/templatePrivateLink'

const TOKEN = 'a'.repeat(64)

const useHead = vi.hoisted(() => vi.fn())

vi.mock('#app/composables/head', async (importOriginal) => ({
  ...(await importOriginal()),
  useHead,
}))

const unsignedToken = (payload) =>
  [{ alg: 'none', typ: 'JWT' }, payload]
    .map((part) => btoa(JSON.stringify(part)).replace(/=+$/, ''))
    .concat('')
    .join('.')

describe('template private link page', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test.each([true, false])(
    'shows the template, signed in: %s',
    async (signedIn) => {
      if (signedIn) {
        testApp.store.dispatch('auth/forceSetUserData', {
          user: { id: 1 },
          access_token: unsignedToken({ user_id: 1 }),
          refresh_token: unsignedToken({ user_id: 1 }),
        })
      }
      testApp.mock.onPost('/user/token-refresh/').reply(200, {
        user: { id: 1 },
        access_token: unsignedToken({ user_id: 1 }),
      })
      const wrapper = await mountSuspended(TemplatePrivateLinkPage, {
        route: `/template/crm/private-link/${TOKEN}`,
        global: { stubs: { TemplatePage: { template: '<div class="tp" />' } } },
      })
      await flushPromises()

      expect(
        testApp.mock.history.post.map(
          (request) => request.headers['Baserow-Template-Authorization']
        )
      ).toStrictEqual(signedIn ? [TOKEN] : [])
      expect(wrapper.find('.tp').exists()).toBe(true)
      expect(useHead).toHaveBeenCalledWith({
        meta: [{ name: 'referrer', content: 'no-referrer', tagPriority: 0 }],
      })
    }
  )
})
