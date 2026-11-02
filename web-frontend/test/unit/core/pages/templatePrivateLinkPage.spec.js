import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplatePrivateLinkPage from '@baserow/modules/core/pages/templatePrivateLink'

describe('template private link page', () => {
  let testApp = null
  let refresh = null

  beforeEach(() => {
    testApp = new TestApp()
    const dispatch = testApp.store.dispatch.bind(testApp.store)
    refresh = vi.fn().mockResolvedValue()
    vi.spyOn(testApp.store, 'dispatch').mockImplementation((type, ...args) =>
      type === 'auth/refresh' ? refresh(...args) : dispatch(type, ...args)
    )
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test.each([true, false])(
    'shows the template, signed in: %s',
    async (signedIn) => {
      if (signedIn) {
        testApp.authenticate({ id: 1 })
      }
      const wrapper = await mountSuspended(TemplatePrivateLinkPage, {
        global: { stubs: { TemplatePage: { template: '<div class="tp" />' } } },
      })
      await flushPromises()

      // Signed in, the permissions are refreshed with the token.
      expect(refresh).toHaveBeenCalledTimes(signedIn ? 1 : 0)
      expect(wrapper.find('.tp').exists()).toBe(true)
    }
  )
})
