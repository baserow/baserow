import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { defineComponent } from 'vue'
import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import ApplicationCard from '@baserow/modules/core/components/allWorkspaces/AllWorkspacesApplicationCard'
import {
  loadApplicationBundle,
  registerApplicationBundle,
} from '@baserow/modules/core/utils/applicationBundles'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(async () => {
  vi.restoreAllMocks()
  await testApp.afterEach()
})

test('application cards load controls only when their menu is opened', async () => {
  const coldApp = {}
  const database = vi.fn(async () => ({}))
  const dashboard = vi.fn(async () => ({}))
  registerApplicationBundle(coldApp, 'database', database)
  registerApplicationBundle(coldApp, 'dashboard', dashboard)
  const type = testApp.$registry.get('application', 'database')
  vi.spyOn(type, 'load').mockImplementation(() =>
    loadApplicationBundle(coldApp, 'database')
  )
  vi.spyOn(type, 'getApplicationContextComponent').mockReturnValue(
    defineComponent({
      template:
        '<div v-if="open" class="test-application-controls">Application controls</div>',
      data: () => ({ open: false }),
      methods: {
        toggle() {
          this.open = !this.open
        },
      },
    })
  )
  const wrapper = await testApp.mount(ApplicationCard, {
    props: {
      application: {
        id: 1,
        type: 'database',
        name: 'Database',
        _: { type: type.serialize() },
      },
      workspace: { id: 1 },
    },
    global: { mocks: { $nuxt: coldApp } },
  })
  expect(database).not.toHaveBeenCalled()
  expect(wrapper.find('.test-application-controls').exists()).toBe(false)

  await wrapper.find('.item-card__more').trigger('click')
  await flushPromises()
  expect(database).toHaveBeenCalledOnce()
  expect(dashboard).not.toHaveBeenCalled()
  expect(wrapper.find('.test-application-controls').text()).toBe(
    'Application controls'
  )
})
