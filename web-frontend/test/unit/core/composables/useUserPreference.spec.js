import { defineComponent, nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import { useUserPreference } from '@baserow/modules/core/composables/useUserPreference'

const Preference = defineComponent({
  setup() {
    return { sortBy: useUserPreference('sort', 'fallback') }
  },
  template: '<div>{{ sortBy }}</div>',
})

describe('useUserPreference', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.store.dispatch('auth/forceSetUserData', {
      user: { id: 1, preferences: {} },
      access_token:
        `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6ImpvaG5AZXhhb` +
        `XBsZS5jb20iLCJpYXQiOjE2NjAyOTEwODYsImV4cCI6MTY2MDI5NDY4NiwianRpIjo` +
        `iNDZmNzUwZWUtMTJhMS00N2UzLWJiNzQtMDIwYWM4Njg3YWMzIiwidXNlcl9pZCI6M` +
        `iwidXNlcl9wcm9maWxlX2lkIjpbMl0sIm9yaWdfaWF0IjoxNjYwMjkxMDg2fQ.RQ-M` +
        `NQdDR9zTi8CbbQkRrwNsyDa5CldQI83Uid1l9So`,
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('reads the store value and falls back when the key is unknown', async () => {
    const wrapper = await testApp.mount(Preference)
    expect(wrapper.text()).toBe('fallback')

    testApp.store.dispatch('auth/forceUpdateUserData', {
      user: { preferences: { sort: 'name_asc' } },
    })
    await nextTick()
    expect(wrapper.text()).toBe('name_asc')
  })

  test('writes through the store, optimistically', async () => {
    testApp.mock
      .onPatch('/user/preferences/', { sort: 'created' })
      .reply(200, { sort: 'created' })
    const wrapper = await testApp.mount(Preference)

    wrapper.vm.sortBy = 'created'
    await nextTick()
    expect(wrapper.text()).toBe('created')
    await flushPromises()
    expect(testApp.store.getters['auth/getUserPreference']('sort')).toBe(
      'created'
    )
    expect(testApp.mock.history.patch).toHaveLength(1)
  })
})
